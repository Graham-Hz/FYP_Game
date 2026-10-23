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
| Model analysis | Fold-fitted preprocessing, simple baselines, Logistic Regression and Random Forest using developer-group CV | [Linear protocol](model_dev_v1_protocol.md), [tree protocol](model_tree_v1_protocol.md) |
| Sensitivity | Fixed-setting refits for observation age, cohort eligibility and outcome-tier definitions | [Age protocol](model_age_v1_protocol.md), [scope protocol](model_scope_v1_protocol.md) |
| Visualisation | Historical A/B distributions in the application, supporting Power BI views and executable notebook figures | [Power BI material](../powerbi/), [notebook](../../notebooks/README.md) |

## Evaluation boundaries

Completed model measurements are development cross-validation results. Calibration and test partitions remain reserved; final model selection, group-versus-random comparison and user-task evaluation are pending. The application currently provides descriptive comparisons and validated data updates, not deployed predictive probabilities. Historical snapshot attributes are not verified pre-release measurements, and outcome proxies do not measure revenue or causal effects.
