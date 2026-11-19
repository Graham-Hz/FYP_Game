# Methodology evidence map

This map connects the project methodology to its implementation and verification artifacts. It describes the current analytical system; proposed features and final evaluation are identified separately.

| Area | Method or implementation | Evidence |
|---|---|---|
| Method | Separate platform analyses, historical outcome-tier classification and functional system checks | [Analysis protocol](../2026-10-06/analysis_v1/analysis_protocol.md) |
| Proposed system | Python processing and model experiments connected to a browser-based historical comparison and CSV-update application | [Application guide](../../DEMO_GUIDE.md), [import specification](../../CSV_IMPORT_GUIDE.md) |
| Data sources | March 2025 Steam and June 2021 Google Play snapshots, with supplementary audit sources | [Dataset feasibility](../2026-10-05/dataset_feasibility_report.md), [source inventory](../2026-10-05/dataset_inventory.csv) |
| Acquisition and processing | Recorded source versions, conservative parsing, row-level inclusion records, feature policy and developer-group partitions | [Cleaning report](../2026-10-06/cleaning_candidate_v1/cleaning_report.md), [data dictionary](../2026-10-06/cleaning_candidate_v1/data_dictionary.md), [analysis verification](../2026-10-06/analysis_v1/verification.json) |
| Storage | Separate raw, interim, frozen research and versioned application data; hashes and manifests identify versions | [Program storage](../../README.md#code-and-storage), [CSV verification](../2026-10-10/csv_import_v1/verification_notes.md) |
| Descriptive analysis | Training-only distributions, missingness and platform-specific attribute/outcome comparisons | [EDA](../2026-10-07/train_eda_v1/eda_notes.md) |
| Independent market exploration | Verified active-snapshot enrichment, source-specific rankings and medians, release-cohort lines, group denominators and source-linked SVG/CSV/JSON export | [Market API](../../src/demo/market.py), [independent aggregate checks](../../tests/test_market.py), [browser checks](../../tests/check_market_browser.py), [walkthrough](../../DEMO_GUIDE.md#independent-market-analysis-walkthrough) |
| Chart design and interactions | Shared gameplay/source-label taxonomy, transformed histograms, Tukey boxplots, scatter exploration, row-percentage heatmaps and linked genre filtering | [Shared label mapping](../../src/analysis/game_taxonomy.py), [statistics](../../src/demo/market_analytics.py), [analytics checks](../../tests/test_market_analytics.py), [cross-page browser checks](../../tests/check_taxonomy_browser.py) |
| Selected-group comparison and record inspection | Same-source/year/tag baseline, complement or explicit comparison group, disclosed overlap, 100% outcome-tier bars, quartiles and matching-record search/pagination | [Comparison calculations](../../src/demo/market_cohorts.py), [independent denominator checks](../../tests/test_market_comparison.py), [interaction/export checks](../../tests/check_market_comparison_browser.py) |
| Model analysis | Fold-fitted preprocessing, simple baselines, Logistic Regression and Random Forest using developer-group CV | [Linear protocol](model_dev_v1_protocol.md), [tree protocol](model_tree_v1_protocol.md) |
| Sensitivity | Fixed-setting refits for observation age, cohort eligibility and outcome-tier definitions | [Age protocol](model_age_v1_protocol.md), [scope protocol](model_scope_v1_protocol.md) |
| Resource data acquisition | Ten manually curated public developer cases; per-observation definitions, source locations, currency uncertainty and coverage dates | [Cost-case method and source register](../../../Dataset/Development%20Cost%20Cases/README.md) |
| Resource analysis | Transparent user-input cash/unpaid-labour budgeting, fixed-rate delay scenarios and conditional break-even requirements | [Calculation method](../../README.md#development-cost-cases-and-budget-scenarios), [implementation](../../src/demo/planning.py), [tests](../../tests/test_development_planning.py) |
| Resource visualisation and evaluation | Source-linked tables and exportable SVG cost, delay, cash/resource and break-even charts; formative user tasks prepared but not conducted | [Shared chart renderer](../../src/demo/static/charts.js), [application and user tasks](../../DEMO_GUIDE.md#development-planning), [browser checks](../../tests/check_planning_browser.py) |
| Integrated planning workflow | Explicit comparison choice, optional Steam reference selection, restored budget drafts and combined source-checked export; Android references marked unavailable | [Workflow implementation](../../src/demo/static/workflow.js), [summary interface](../../src/demo/static/plan.js), [end-to-end browser checks](../../tests/check_workflow_browser.py), [demonstration](../../DEMO_GUIDE.md#connected-planning-walkthrough) |
| Analysis-to-planning evidence | Compact, version-checked market findings with user interpretation; source-labelled summary before or after selecting a historical condition | [Market capture](../../src/demo/static/market.js), [finding checks](../../tests/check_market_findings_browser.py), [combined workflow checks](../../tests/check_planning_workspace_browser.py) |
| Resource alternative comparison | Saved A/B server-calculated budgets, changed-input tables, cost-component and equal-delay comparisons; missing values, currencies and fee revisions handled explicitly | [Alternative comparison](../../src/demo/static/budget_scenarios.js), [browser checks](../../tests/check_budget_scenarios_browser.py) |
| Visualisation | Historical A/B distributions in the application, supporting Power BI views and executable notebook figures | [Power BI material](../powerbi/), [notebook](../../notebooks/README.md) |

## Course concepts used in the explorer

The following references were checked against the locally supplied lecture files. Course materials are not redistributed with this repository.

| Local course material | Teaching evidence | Application and limits |
|---|---|---|
| COMP3115, `Lecture 5_BasicDataVisualization.pdf`, pp. 16–30 | Histograms and the effect of bin width (p. 27) | Distribution plots with explicit bins and original-value boundaries; transformed bins are labelled |
| Same lecture, pp. 31–37, especially p. 32 | Median, quartiles and 1.5 IQR outlier definition | Gameplay-group boxplots with Tukey whiskers, group counts and disclosed outlier display limits |
| Same lecture, pp. 49–55; COMP1016 `Lab/Lab3/examples/corr-01.py` | Scatter diagrams, scatter matrices and a correlation example | Price/outcome or age/outcome scatter plots; rank correlation is a project choice for skewed data, not a claim that the cited Pearson example taught Spearman |
| COMP1016 `Lab/Lab3/lab3-ex3.py`; COMP3925 `Topic4_DesignReport.pdf`, pp. 7–8 | Crosstab/pivot operations and report matrices | A row-percentage outcome heatmap with explicit cell counts and denominators. COMP3115 Lecture 3, p. 26, names heatmaps as a library capability; it is not treated as a full heatmap-method lesson |
| COMP3925 `Topic4_DesignReport.pdf`, p. 14, steps 7–12 | Cross-filtering, tooltips, focus mode and data export | Click a gameplay bar to filter the analysis, inspect scatter points, and export plot data. Tier segments also open the corresponding record table; this is a custom browser interaction, not an embedded Power BI drill-through page |
| COMP3115 `Lecture 6_Advanced_Data_Visualization.pdf`, pp. 74, 78 | Colour accessibility and avoiding excessive labels | Colour is supplemented by numeric labels/tables, focused views and tooltips |

COMP1016 stock examples contain genuine repeated daily observations and operations such as resampling and percentage change. Those growth calculations are not transferred to the game's single-snapshot release cohorts. The interface preserves that distinction.

## Evaluation boundaries

Completed model measurements are development cross-validation results. Calibration and test partitions remain reserved; final model selection, group-versus-random comparison and user-task evaluation are pending. The application currently provides descriptive comparisons and validated data updates, not deployed predictive probabilities. Historical snapshot attributes are not verified pre-release measurements, and outcome proxies do not measure revenue or causal effects.
