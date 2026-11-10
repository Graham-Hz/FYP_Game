# Development cost and resource cases

A manually curated pilot for early game-development planning. It contains **10 cases, 37 observations and 10 public developer sources**, checked on **23 October 2026**. The website presents individual cases alongside a separate calculator driven entirely by user assumptions.

This is secondary-source curation, not an original survey or an independent audit of developers' accounts. It supports inspecting resource commitments and cost definitions. It does not estimate average industry budgets, predict development costs or provide profit labels for the research models.

## Files and sources

| File | One row represents | Key |
|---|---|---|
| [cases.csv](cases.csv) | A named game/project and its context at the source date | `case_id` |
| [observations.csv](observations.csv) | One reported amount, duration, headcount or effort observation with its scope | `observation_id` |
| [sources.csv](sources.csv) | A source publication with author, URL and dates | `source_id` |

`source_id` connects both case descriptions and individual observations to the source register. `case_id` connects observations to games. Repeated rows for one game are different observations, not additional independent games. Publication date is not automatically the year of expenditure or release.

| Source | Project | Primary publication |
|---|---|---|
| S01 | Eastshade | [Eastshade Studios, 2020](https://eastshade.com/postmortem-eastshade/) |
| S02 | Shipwreck | [Nick Gravelyn, 2014](https://www.gamedeveloper.com/business/shipwreck-post-mortem) |
| S03 | FOMOGRAPHY | [Brendan Keesing, 2025](https://brendankeesing.com/blog/fomography_postmortem/) |
| S04 | TOEM | [Lucas Gullbo and Niklas Mikkelsen, 2021](https://www.gamedeveloper.com/production/postmortem-toem) |
| S05 | Hang Line | [Ed Kay, 2020](https://www.gamedeveloper.com/business/hang-line-postmortem-part-3-production-data-and-tools-used-in-development) |
| S06 | The Fall of Lazarus | [Jonathan Prat, 2018](https://www.gamedeveloper.com/business/this-is-not-another-postmortem) |
| S07 | Immortal Darkness | [Chris Shrigley, 2019](https://www.gamedeveloper.com/business/a-postmortem-making-games-is-easy-selling-them-not-so-much-) |
| S08 | Shovel Knight | [Yacht Club Games, 2014](https://old.yachtclubgames.com/2014/08/sales-one-month/) |
| S09 | Nightshift Galaxy | [Max Kaufmann, 2024](https://blog.littlepolygon.com/posts/announcement/) |
| S10 | Monsters & Memories | [Niche Worlds Cult, undated page covering 2020–2025 costs](https://monstersandmemories.com/costs) |

The CSV register provides the full titles, authors, publication dates and access dates. Each observation's `locator` identifies a heading or paragraph in the linked article. Public sources remain the property of their authors. The tables contain selected facts and short curation notes, not copies of the articles.

## Acquisition and inclusion

The pilot was found through targeted searches for developer postmortems, production budgets, development time and cost disclosures, followed by reading the original publications. Searches included `indie game postmortem development budget actual cost`, `site.gamedeveloper.com postmortem budget`, and developer-site searches. Existing Eastshade, Shipwreck and FOMOGRAPHY leads were checked directly.

Include a case when a named developer or studio publicly describes an identifiable project and at least one resource observation can be located in the original publication. An exact monetary total is not mandatory: a documented duration or logged work time can support a useful reference case. Include partial production stages and ongoing work only with explicit stage labels. Missing monetary scope, conflicting values and unresolved currencies remain visible instead of being silently repaired.

Generic budget-advice pages, unsourced industry averages, unnamed projects and secondary summaries without a checked original were not extracted. For example, the Steam Page Analyzer cost summary and an AI-labelled unnamed-game account found in the search were not used as cost evidence. Searches were exploratory, not a systematic review or a comprehensive census. No claim is made about source popularity or download counts.

AI assisted discovery, extraction and implementation. The retained records were checked against the linked publications within this workflow, but **independent human re-extraction has not been completed**. Recheck each original before using a claim in a report, especially values marked as contextual or conflicting.

## Observation definitions

| Field | Meaning |
|---|---|
| `metric` | Distinguishes `cash_cost`, `reported_cost`, `reported_budget`, `planned_budget`, `economic_estimate`, `funding_received`, `funding_request`, `development_duration`, `team_size`, `logged_hours`, `planned_effort` |
| `value` | Numeric reported value or boundary; never a guessed midpoint |
| `qualifier` | `reported` retains the source figure without asserting exactness; `approx`, `less_than` and `greater_than` preserve approximations and bounds |
| `unit` | `money`, `months`, `people`, `hours` or `person_months` |
| `currency` | ISO currency code only where explicit or supported by article context; otherwise blank |
| `currency_basis` | `explicit`, `article_context`, `unspecified`, or `not_applicable` for non-monetary observations |
| `scope` | What the observation covers; distinguishes total, component, phase and hypothetical valuation |
| `period` | Source-described expenditure or development coverage; may be relative when no dates are given |
| `source_id`, `locator` | Trace the individual claim to the source and section |
| `notes` | Exclusions, conflict, transformation or interpretation needed for this value |

`reported_cost` and `reported_budget` do not imply verified cash expenditure. Funding raised or requested is not cost. Component amounts must not be added to a total that already includes them. A zero-budget statement is preserved as a reported-budget observation with a scope warning, not converted into zero economic cost.

Years explicitly stated by an author are multiplied by 12 for month units, with the conversion recorded. Approximate years remain approximate months. Calendar duration is not person-month effort. Different prototype/production/release windows remain separate observations. Headcounts describe the cited team definition, not an assumed constant full-time staffing level. There is no currency conversion, inflation adjustment or inferred labour valuation in the case tables.

## What the pilot establishes

The 37 observations comprise 22 monetary observations and 15 time/headcount/effort observations. Of the monetary observations, two have explicit currency codes, five use article context and 15 leave the currency unresolved. A dollar sign alone is not silently interpreted as USD. Nine sources have publication dates spanning 2014–2025; the tenth is an undated page describing 2020–2025 spending as of 2026.

The pilot establishes that traceable individual references can be assembled. It does **not** establish comparability of budgets or adequate coverage for a predictive model. In particular:

- Historical and self-disclosed cases are subject to publication and selection bias. Including disappointing commercial outcomes does not remove that bias.
- Only one retained source explicitly covers an Android/iOS project. There is insufficient mobile evidence for platform-level cost comparisons.
- The body and headline totals for The Fall of Lazarus disagree. Both remain recorded; neither is chosen as a reconciled total.
- Some projects disclose cash excluding unpaid work, while others describe hypothetical economic costs or funding plans. No aggregate cost distribution is produced.
- No automatic Steam/Android identifier matching or cost-to-revenue merge is performed. Platform scope, timing and gross/net definitions would require a separate review.

The appropriate initial product is a case library plus user-entered budget scenarios. A cost-prediction model, cost averages by genre and inferred ROI are outside this evidence base.

## Updating and checking

Preserve existing identifiers. Add a source record and then its case/observations, or add another source and observation to an existing case. Keep exact headers and UTF-8 CSV encoding. Use blank cells for unknown currency/publication dates and explanatory scope notes for missing information. If a source changes, inspect the claim and update its access date; do not replace disputed figures without recording the reason.

From `Program/`:

```powershell
uv run --locked python src/demo/planning.py
uv run --locked python -B -m unittest discover -s tests -p test_development_planning.py -v
```

The first command validates identifiers, references, source URLs/dates, numeric values, metric/unit pairs, currency rules and claim locations. It prints counts and SHA-256 hashes. These checks validate structure, not the truth of a disclosure. Snapshot hashes are included in the case API for traceability; they are not independent source verification.

Restart the local application after a reviewed CSV update. This pilot uses maintainers' reviewed CSV files; it is separate from the main page's end-user Steam/Android snapshot importer. Small curated tables are included in Git, while downloaded bulk datasets remain excluded.
