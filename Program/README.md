# Program setup and research pipeline

This directory contains the Python data pipeline, model experiments and local web application for the game-planning decision-support system. See the [project overview](../README.md) for its purpose, implemented capabilities and limitations.

## Environments

Install `uv` and run commands from this directory. The data/application environment requires Python 3.14 and is defined by `pyproject.toml` and `uv.lock`.

```powershell
uv sync --locked
```

Model experiments have a separate locked environment in `experiments/model_dev_v1/`. The executable notebook uses `experiments/walkthrough_v1/`. Use each environment's lock file; `requirements.txt` is an export of the main environment, not the model environment.

## Launch the local application

For a new computer, the [distribution guide](distribution/README.md) describes the prepared Demo package, installation and verification. The package supplies the seven required/enrichment data artifacts and source-linked reference tables. GitHub's source ZIP alone does not contain those generated artifacts. Ordinary demonstration users do not need to rerun cleaning or model training.

The application requires the four frozen analysis files in `data/processed/analysis_v1/`: `pc_features.parquet`, `pc_labels_splits.parquet`, `mobile_features.parquet` and `mobile_labels_splits.parquet`. It checks their hashes against the recorded analysis version. These large files are not included in Git.

On Windows, double-click [START_DEMO.cmd](START_DEMO.cmd), or run:

```powershell
uv run --locked python src/demo/preflight.py
uv run --locked python src/demo/server.py --open
```

The Windows launcher first synchronises the locked environment and runs complete-demo checks. [CHECK_DEMO.cmd](CHECK_DEMO.cmd) performs those checks without opening the website; use `--no-pause` in automated terminal runs. `--skip-port-check` checks files while another instance is running, and `START_DEMO.cmd --port 8766` uses an alternative port. Missing data, checksum failures and unwritable import storage produce an actionable diagnostic before the server opens.

Keep the process running while using `http://127.0.0.1:8765/market`, the default independent analysis page. The comparison page remains at `/`. Press Ctrl+C to stop. A different port can be selected with `--port 8766`. The service binds to localhost and is not configured as a public web deployment.

See the [demonstration guide](DEMO_GUIDE.md) and [CSV import specification](CSV_IMPORT_GUIDE.md). Imported application snapshots are stored separately in `data/application/v1/`; they do not replace the frozen research data.

### Independent market analysis and charts

All application routes use `static/shell.js` and `shell.css` for the same left navigation. **Data analysis** contains overview, distributions, relationships, release cohorts, rankings, the supplementary revenue view and guided CSV import. **Development planning** contains Steps 1–4: condition comparison, reference retrieval, budget comparison and summary. Market sections have direct fragment links such as `/market#distribution`; small screens use an accessible menu drawer. The analysis and planning contexts remain separate.

`/market` loads charts automatically without a planning context. `src/demo/market.py` implements the read-only `GET /api/market/options`, `POST /api/market` and `POST /api/market/records` queries. Steam and Android use the active application version selected on the comparison page; the supplementary revenue source has its own independent version. Reload source versions on the market page after activating a different CSV snapshot. No model is fitted or used to generate these descriptive charts.

The research data are enriched from `data/interim/cleaning_candidate_v1/pc_candidates.parquet` and `mobile_candidates.parquet`, checked against the trusted analysis manifest. Only IDs already present in the research **train** tables are retained. One approved Steam exception lacks candidate details; count/tier charts retain it, while date and numeric-detail charts disclose the missing record. Missing or modified enrichment files make that source unavailable without disabling other application modules. Strict v1 imports retain their original eligible-ID join. Guided imports use a separately validated `exploration.parquet` for market charts and `data.parquet` for stricter planning comparison; all saved files are hash-checked by `SnapshotRepository.load`. Frozen research files and the legacy validator remain unchanged.

`/import` provides guided field mapping through `POST /api/import/inspect` and `/api/import/guided-preview`, followed by the existing preview commit and activation endpoints. `src/imports/guided.py` normalises only confirmed formats, preserves unknowns and reports per-analysis coverage. Extra columns are retained in `source.csv`; `normalized.csv`, `mapping.json`, validation and a row ledger document the interpretation. Version identity includes the confirmed mapping/options, and a changed preview invalidates the previous token. Optional browser-local mapping profiles require fresh semantic confirmation. A guided snapshot may have useful market rows and zero planning-comparison rows. It remains a game snapshot importer, not arbitrary revenue/time-series ingestion or automatic model training. See [CSV_IMPORT_GUIDE.md](CSV_IMPORT_GUIDE.md).

The explorer presents sample counts, summed and median outcome proxies by group, high-tier proportions with a minimum displayed group size of 30, distributions, release-cohort lines, business attributes and title rankings. Steam owner estimates retain their lower and upper bounds; they are not exact purchases. Android values are installation lower bounds. The independent revenue view uses all 1,500 selected records, including zero observed prices, whereas `/revenue` defaults to the 1,415 positive-price records. Revenue charts include estimated copies, gross revenue and concentration; neither selection represents the whole current market.

`src/analysis/game_taxonomy.py` separates eight supported Steam gameplay genres from production labels (Indie), release stage (Early Access), pricing labels, play form (Massively Multiplayer), content descriptions and software/media uses. Market analysis, planning-condition comparison and Steam reference retrieval share this mapping; `market_taxonomy.py` provides compatible imports. This is an explicit project presentation mapping, not a newly verified official Steam taxonomy. Unknown source labels remain selectable in an unclassified-label group. The separate gameplay and additional-label filters combine with AND; genre charts use gameplay groups only. Android retains the existing Google Play game categories. Source labels, eligibility rules, model features and frozen partitions are not rewritten. The mapping and coverage are included in exported provenance.

The page organises its charts into overview, distribution, relationships, release cohorts and rankings. Users choose a focused plot instead of scrolling through every chart at once. Selecting a gameplay bar filters the analysis, while scatter-point selection exposes the individual displayed record. Full-analysis exports retain all chart definitions, even when a different plot is selected on screen.

`market_availability.py` checks each chart against the actual filtered records and adds `availability` metadata: `status`, `reason`, `action`, `valid_rows`, `total_rows` and `requirements`. Missing dates, incomplete numeric pairs, unmapped groups, existing group display thresholds and undefined percentage denominators receive specific explanations. One-point or constant-value scatter views may remain visible with a warning; they do not fabricate correlation. A single release cohort is labelled as insufficient for a multi-period comparison. These checks establish whether the descriptive view can be produced, not statistical reliability or representativeness.

The sidebar indicates partial or unavailable sections while keeping their explanations accessible. Unavailable charts cannot be saved as findings or downloaded as blank SVGs; JSON retains their original descriptors and readiness, while CSV retains their metadata without treating unavailable bins as observations. Pending filters invalidate previous readiness. Short reading notes explain sample sizes, medians, quartiles and platform-specific outcome proxies. Existing CSV field validation is unchanged; this is not an arbitrary-schema chart generator or a new regression model.

Selecting one gameplay group opens a comparison with the remaining records, excluding the selected IDs. Users can instead choose another group; overlapping Steam membership is counted and disclosed. Both groups use the same source/version, release-year range and additional tag. `market_cohorts.py` reports sample counts, outcome-tier percentages and Q1/median/Q3, with unknown outcomes retained in the denominator. Android and Steam tier comparisons use 100% stacked bars; the revenue source compares estimated-revenue medians and reports quartiles. These are descriptive comparisons, not significance tests or success predictions.

Hover or focus a chart mark for its values. Clicking a tier segment (or pressing Enter/Space) opens the matching records, with literal name/ID search, sorting and pagination; both groups also have full-record buttons. Changing analysis conditions hides stale results. JSON and CSV exports retain the comparison definition, overlap, both denominators and statistics. Existing references saved under the older genre method must be reselected; manual budget fields are preserved for review.

`market_analytics.py` adds histogram, Tukey boxplot, scatter and row-percentage heatmap summaries. Histograms use equal-width bins in `log1p(value)` space, with original-value bounds retained. Boxplots show actual observations at the whiskers within 1.5 IQR fences, group sizes and outlier counts; a limited set of outliers is displayed. PC distribution plots use observed prices, Android plots use installation lower bounds, and revenue plots use estimated gross revenue. No owner-interval midpoint is invented. Scatter diagrams use observed price versus owner lower bound (PC), observation age versus installation lower bound (Android), and observed price versus estimated revenue (the independent revenue source). At most 800 deterministically selected complete records are plotted; rank-correlation statistics use the full complete-pair sample. A log/linear display switch does not change those raw observations. A descriptive correlation is not a causal estimate or evidence for a pricing intervention.

Time axes represent **release cohorts**, not repeated sales/download measurements. Steam genres can overlap. Counts, per-title medians and sums answer different questions; high-volume groups are not automatically the best development opportunity. The original Steam observed-price currency is unresolved and is labelled accordingly. No midpoint owner estimate or price-times-copies revenue is reconstructed.

`static/charts.js` and `charts.css` render local, accessible SVG charts, numeric tables and self-contained SVG downloads without a network chart dependency. Market exports include a complete JSON evidence record and a UTF-8 chart-data CSV with provenance and formula-safe text. Budget charts use the existing calculator outputs only: cost composition, delay cash requirements, cash versus resource budgets and break-even unit requirements. These are assumption-based scenarios rather than market observations.

The market page can save the currently selected chart view as a finding, with a user title/note, original source hashes, filters, statistics and comparison denominators. Each finding stores at most two charts and 40 aggregate rows per chart; raw scatter points and individual outliers are omitted with explicit metadata. At most five findings are retained. Before saving and summary export, active source versions, hashes and analysis/taxonomy methods are checked. No historical planning condition is silently inferred from a finding.

`static/workflow.js` preserves the existing selected-condition state and adds a separate `gamescope.planning.workspace.v1` session-storage record for findings and budget A/B snapshots. Both work before a legacy planning context exists. `static/budget_scenarios.js` compares saved server outputs rather than recalculating costs in the browser. Supported manual and optional-fee methods can be compared, but currencies must match and selected fee revisions must pass verification. Missing funds/contribution retain null outputs. Editing the live form invalidates its calculation without changing either saved alternative; replacement is explicit. Summary exports include both snapshots, input differences, source checks and any selected-condition plan, while a workspace-only export remains incomplete as a full plan. Data lives in the current browser tab and is not an importable saved project or server account.

Saved A/B assumptions can be loaded into the live budget form after explicit confirmation. The loader validates the saved request and any fee revision before replacing inputs; failed validation or persistence leaves the previous form and result intact. A successful load clears the current calculation and requires recalculation. It preserves both saved alternatives and the current historical/reference context. The form and summary identify matching alternatives by their inputs, calculation method and fee revision, rather than by equal totals alone.

Run the targeted checks from `Program/`:

```powershell
uv run --locked python -B -m unittest discover -s tests -p "test_market.py" -v
uv run --locked python -B -m unittest discover -s tests -p "test_market_analytics.py" -v
uv run --locked python -B -m unittest discover -s tests -p "test_market_comparison.py" -v
uv run --locked python -B -m unittest discover -s tests -p "test_market_availability.py" -v
uv run --locked --with playwright python -B tests/check_shell_browser.py
uv run --locked --with playwright python -B tests/check_market_readiness_browser.py
uv run --locked --with playwright python -B tests/check_market_layout_browser.py
uv run --locked --with playwright python -B tests/check_market_browser.py
uv run --locked --with playwright python -B tests/check_market_comparison_browser.py
uv run --locked --with playwright python -B tests/check_market_findings_browser.py
uv run --locked --with playwright python -B tests/check_budget_scenarios_browser.py
uv run --locked --with playwright python -B tests/check_budget_restore_browser.py
uv run --locked --with playwright python -B tests/check_planning_workspace_browser.py
uv run --locked --with playwright python -B tests/check_planning_browser.py
```

Browser captures and chart exports are written to ignored `data/processed/market_qa/` and `planning_qa/`. Test application versions use disposable storage and do not change the user's active data.

### Connected planning workflow

After a comparison, choose condition A or B to create a planning context. Steam proceeds to `/revenue#reference-panel`, where the supported genre is carried over and the user supplies a price, selects up to five references or records a skip reason. Android proceeds directly to `/planning#budget-section`. The `/plan` page combines the historical evidence, reference choices, budget scenarios and decision notes, and exports a provenance-preserving JSON summary. The input price for reference retrieval is never copied into net contribution or other budget fields.

`src/demo/static/workflow.js` manages a versioned `sessionStorage` record for one browser tab. `plan.js` renders the combined summary and rechecks the active comparison version, reference metadata and fee revision before export. The new `/api/revenue/metadata` read-only endpoint supplies reference provenance without returning all game records. No new server database, model training, or change to frozen partitions is involved.

The draft retains empty numeric fields as empty strings. Editing a budget clears its saved calculation; reference-query changes clear saved reference choices. Choosing an unchanged comparison preserves downstream work, while a changed context requires renewed review. A changed or unavailable fee catalogue blocks restoration of selected costs until the user explicitly removes them or restores the compatible catalogue. JSON export is an evidence record, not a supported saved-project import format. A closed tab or changed application origin may lose the working draft.

Run the end-to-end checks with the existing optional browser-test dependency:

```powershell
uv run --locked --with playwright python -B tests/check_workflow_browser.py
```

This uses a separate headless Edge session and the real local comparison, reference and budget APIs. Captures, example exports and the check summary are saved under ignored `data/processed/workflow_qa/`. Source-version failures are simulated in the browser; source datasets and active application versions are not modified. These are automated task-path checks, not a human usability study.

## Prepare the research inputs

Keep `Dataset/` and `Program/` as sibling directories. Restore the source files described in [Dataset/README.md](../Dataset/README.md) and compare their sizes and hashes with the recorded source inventory. Newer downloads may not reproduce the existing analysis version.

The complete audit reads supplementary datasets as well as the two principal sources. Its acquisition and audit commands are:

```powershell
uv run --locked python src/data/fetch_sources.py --date 2026-10-05 --download-steam
uv run --locked python src/data/validate_structure.py
uv run --locked python src/data/profile_datasets.py
uv run --locked python src/data/compare_and_targets.py
uv run --locked python src/data/build_reports.py
uv run --locked python src/data/verify_audit.py
uv run --locked python src/data/target_design_diagnostics.py
```

The acquisition command reuses the stored source lock and downloads the pinned Steam Hugging Face Parquet. It does not download the full RAWG or Steam review collections. The date identifies the existing audit version, not a request for current data. A new source audit needs a separately versioned configuration and outputs.

After the audit inputs are available, prepare and verify the candidate and analysis tables:

```powershell
uv run --locked python src/data/clean_candidates.py
uv run --locked python src/data/verify_clean_candidates.py
uv run --locked python src/data/freeze_analysis.py
uv run --locked python src/data/verify_analysis.py
uv run --locked python src/data/review_analysis_questions.py
uv run --locked python src/analysis/profile_training.py
uv run --locked python src/analysis/verify_training_eda.py
```

These commands rebuild research outputs; they are not required for an ordinary demonstration when verified local files already exist. Preserve the fixed source versions and analysis rules when reproducing saved results. A changed input hash requires investigation rather than bypassing validation. Large audit stages can require substantial time and temporary disk space; the DuckDB profiler uses a 4 GB memory limit and two threads, with additional memory used by Python and Arrow.

## Audit supplementary revenue data

After placing the three original CSVs in the folders listed in [Dataset/README.md](../Dataset/README.md), run:

```powershell
uv run --locked python src/data/audit_revenue_sources.py
```

This checks source hashes, missing values, duplicate keys, numeric/date fields and overlap with the existing Steam IDs and Google Play names. It writes [audit.json](reports/2026-10-23/revenue_sources/audit.json); `--output` selects another report path for a new download version. The original files, frozen cohorts and application snapshots are unchanged. Name matches are review candidates, not accepted revenue joins. The historical audit remains restricted to its original source folders.

Prepare the separate Steam revenue explorer after reviewing the audit:

```powershell
uv run --locked python src/analysis/build_revenue_analysis.py
```

This preserves all 1,500 source rows and joins March 2025 genres by unique Steam ID. It writes the ignored `data/processed/revenue_v1/explorer.json` and the aggregate [analysis report](reports/2026-10-23/revenue_sources/analysis.json). Start or restart the application, then open `http://127.0.0.1:8765/revenue`. The page defaults to 1,415 positive-price records; zero-price records are separately selectable. It provides distributions, concentration, price/genre comparisons, searchable paginated rows and JSON export. The revenue page is independent of the main page's CSV version selection and does not train or evaluate models.

The source is a selected high-revenue cohort. Its cumulative gross estimates, provider publisher classes, mixed observation ages and later genre metadata support descriptive comparisons only. Currency follows provider conventions; the source has no explicit currency field, and its exact 2024 estimation-method version is unavailable. The mobile compilation and launch panel are not incorporated into this explorer.

The revenue page also includes **comparable-game references**. Select supported gameplay genres, a proposed USD price (0–1,000), an optional price-ratio bound and 5, 10 or 20 results. Positive and zero observed-price cohorts are separate. Candidates must share a supported gameplay genre. Ranking uses genre Jaccard similarity first, absolute price difference second and numeric Steam ID for ties. Provider labels such as Indie and Early Access, software categories, revenue and publisher classes do not participate in ranking. The eight supported gameplay genres are declared in `src/analysis/game_taxonomy.py`; reference method `genre_price_references_v2` records this shared mapping. The revenue analysis's original-label dropdown remains separate and groups its labels explicitly.

This is deterministic reference retrieval, not a fitted KNN predictor or a validated recommendation model. It reuses the existing local revenue artifact and requires no additional build. Results include matching reasons, coverage counts, source metadata and a versioned method definition in their JSON export. Fewer eligible candidates produce fewer results. These controls are independent of the explorer filters and the main page's CSV version selection.

Verify the revenue module, reference retrieval and interface:

```powershell
uv run --locked python -B -m unittest discover -s tests -p "test_revenue*.py" -v
uv run --locked --with playwright python.exe tests/check_revenue_browser.py
```

The builder validates the audited source hash before processing. A changed download requires a reviewed source audit and a separately considered analysis version; rebuilding is not automatic activation of an arbitrary new revenue CSV.

## Development cost cases and budget scenarios

Open `/planning` from the application navigation. The source-linked case library reads the small, Git-tracked CSV tables in `../Dataset/Development Cost Cases/`; the [source and method guide](../Dataset/Development%20Cost%20Cases/README.md) explains scope, unresolved values and updates. `src/demo/planning.py` validates the tables and implements budget arithmetic. No research cohort, model or revenue record is modified by this module.

Budget inputs include constant monthly staffing/allocation, cash costs, additional unpaid-labour valuation, one-off costs, contingency, optional available funds and optional net contribution per sale. Figures are user assumptions. Case values do not fill the calculator. Changing inputs invalidates the displayed result until recalculation.

Cash budget equals manual monthly cash outflow times months, plus one-off costs and selected reference fees, plus the specified reserve on those cash costs. Unpaid-labour valuation is added separately to show total resource commitment. Delay scenarios add three or six months at unchanged manual monthly rates and one-off spending, while selected subscriptions renew in complete terms. Break-even unit requirements divide the relevant budget by positive user-supplied net contribution and round up. They do not predict sales.

`src/demo/fees.py` validates the Git-tracked [fee catalogue](../Dataset/Development%20Fee%20References/README.md), resolves source records and computes selected fee components. `/api/planning/fees` returns the catalogue; `/api/planning/fees/csv/fees` and `/api/planning/fees/csv/sources` serve the checked CSV bytes. The frontend searches by tool/category/currency and permits one plan per product. Amounts come from the server snapshot, with user inputs for quantity, eligibility confirmation and FX. Unknown monthly commitment requires a clearly labelled flexible-monthly assumption; royalty/quote/non-game references remain unselectable. Requests include the catalogue revision so a stale selection cannot silently use changed prices.

Yearly subscriptions charge `ceil(months / 12)` full years. Monthly-paid annual contracts include all committed instalments, including those beyond development completion. Other one-time fees are counted once; free base licences remain zero subject to eligibility. Fees start at development month 1; existing subscriptions, cancellations, prorating, taxes and usage overages are not modelled. FX is explicitly supplied by the user, not fetched or inferred. Changing the budget currency invalidates previous FX confirmation. Manual currency inputs are never automatically converted.

Runway reserves one-off spending and the full contingency upfront and assumes no income. With selected paid references it additionally reserves those costs in full, and caps the displayed months at the scenario horizon, so annual payment timing is not mistaken for constant monthly spending. JSON exports include original fee/source snapshots, hashes, selected quantities/FX and separate calculation lines for every scenario. Missing fee files disable the fee library, while manual budgeting remains available.

From this directory:

```powershell
uv run --locked python src/demo/planning.py
uv run --locked python -B -m unittest discover -s tests -p "test_fee_planning.py"
uv run --locked --with playwright python.exe -B tests/check_planning_browser.py
```

The case audit prints structural validation, coverage and CSV hashes. The browser check uses headless Edge and saves local QA captures in ignored `data/processed/planning_qa/`. It covers fee filters, source links/downloads, quantities/FX, required confirmations, full-term renewals, JSON evidence, invalidated results and a missing-catalogue fallback. Case and fee CSV updates require source review and application restart; the main Steam/Android CSV import screen does not import these tables.

## Model experiments and checks

Each experiment protocol documents its inputs, model settings, execution commands and independent verification:

| Experiment | Protocol | Results |
|---|---|---|
| Baselines and Logistic Regression | [Linear model protocol](reports/planning/model_dev_v1_protocol.md) | [Development results](reports/2026-10-07/model_dev_v1/results_notes.md) |
| Random Forest comparison | [Tree model protocol](reports/planning/model_tree_v1_protocol.md) | [Tree results](reports/2026-10-10/model_tree_v1/results_notes.md) |
| Observation-age sensitivity | [Age protocol](reports/planning/model_age_v1_protocol.md) | [Age results](reports/2026-10-11/model_age_v1/results_notes.md) |
| Sample and target sensitivity | [Scope protocol](reports/planning/model_scope_v1_protocol.md) | [Scope results](reports/2026-10-13/model_scope_v1/results_notes.md) |

Run the unit/integration suite in the model environment:

```powershell
uv run --project experiments/model_dev_v1 --locked python -B -m unittest discover -s tests -v
```

Some integration checks require the frozen local artifacts. Browser checks require Microsoft Edge and the additional test dependency:

```powershell
uv run --locked --with playwright python.exe tests/check_demo_browser.py
```

This launches a separate headless browser and stores outputs in ignored local QA storage. The commands are documented reproduction paths; a clean clone without the required data cannot complete every check.

## Code and storage

| Location | Responsibility |
|---|---|
| `src/data/` | Source acquisition, auditing, cleaning, feature preparation and fixed partitions |
| `src/analysis/` | Training-set descriptive analysis and verification |
| `src/features/` | Feature preparation and predictor policy |
| `src/models/` | Model fitting, evaluation and experiment verification |
| `src/demo/` | Local HTTP service, historical comparison queries and browser interface |
| `src/imports/` | CSV contracts, validation, preview and application version management |
| `config/` | Versioned rules and experiment parameters |
| `data/raw/` | Source metadata and original downloads |
| `data/interim/` | Audit and candidate-cleaning tables |
| `data/processed/` | Frozen analysis tables, fitted artifacts and predictions |
| `data/application/` | Independent imported application versions |
| [reports](reports/README.md) | Methods, aggregate outputs and verification evidence |

Raw inputs remain separate from processed outputs. Model features exclude identifiers and outcome fields; calibration and test data remain reserved. Historical audit counts can differ from the primary analysis sample because the stages apply different eligibility rules. The [analysis protocol](reports/2026-10-06/analysis_v1/analysis_protocol.md) defines the fixed modelling cohort.
