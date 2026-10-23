# A Data-Driven Decision Support System for Early-Stage Game Development Planning

A final-year project in Business Computing and Data Analytics at Hong Kong Baptist University.

## Project purpose

This project develops a decision-support system for independent game developers and small studios during early development planning. It uses historical game data to help users explore how attributes such as genre, platform support and monetisation relate to observed outcome groups.

The intended use is to compare planning options with evidence from existing games, understand the available sample, and inspect the limits of the comparison. Steam and Android are analysed separately because their datasets, observation dates and outcome measures differ.

The system combines a reproducible Python analysis pipeline with an interactive web interface. It also supports data updates through validated CSV imports, allowing the application to analyse new compatible snapshots.

## Current application

The implemented application runs locally in a browser.

| Capability | Current behaviour |
|---|---|
| Platform selection | Separate Steam and Android analysis with platform-specific attributes and outcome tiers |
| Planning-condition comparison | Compare two sets of conditions within a platform using sample counts, outcome distributions and sample overlap |
| Interpretation support | Display data provenance and feedback for small or empty samples |
| Result export | Export comparison results and their conditions as JSON |
| CSV data updates | Validate a specified schema, preview accepted/excluded records, save an application version, activate it and return to the original research version |

For example, a user can compare two Android category and monetisation configurations, inspect the historical install-tier distributions, and export the evidence behind that comparison.

CSV imports update the descriptive application. They do not automatically retrain research models or modify the fixed research partitions. The current interface does not serve model predictions.

## Data and analysis

| Platform | Principal source snapshot | Primary analysis sample | Outcome proxy |
|---|---|---:|---|
| Steam | Steam Games Dataset 2025, March 2025 | 73,527 games | Tiers derived from estimated-owner intervals |
| Android | Google Play Store Apps, June 2021 | 318,300 games | Tiers derived from installation lower bounds |

The Steam primary sample uses positive observed prices and additional eligibility rules. The Android sample uses 16 clearly identified game categories and excludes ambiguous Sports records. These are defined research samples, not complete or representative measurements of either market. Source links and file requirements are documented in [Dataset](Dataset/README.md).

The research pipeline covers source auditing, conservative data cleaning, row-level inclusion records, feature preparation, descriptive analysis and outcome-tier classification. Developer groups are kept separate across training, calibration and test partitions, and across the three training validation folds. Preprocessing is fitted within each training fold to reduce leakage.

## Model experiments

Completed development experiments compare class-prior baselines, age-only models, Logistic Regression and Random Forest. Additional experiments examine observation age, Steam sample eligibility and Android outcome-tier definitions.

The following results are mean macro-F1 over three training developer-group folds. They are development cross-validation results, not final test performance.

| Platform | Feature set | Prior baseline | Logistic Regression | Random Forest |
|---|---|---:|---:|---:|
| Steam | Planning attributes | 0.2860 | 0.4401 | 0.4458 |
| Steam | Planning attributes and age | 0.2860 | 0.4845 | 0.5062 |
| Android | Planning attributes | 0.2127 | 0.4758 | 0.4785 |
| Android | Planning attributes and age | 0.2127 | 0.5322 | 0.5376 |

Planning attributes are observed snapshot properties, not verified pre-release measurements. Development settings were selected using these folds, so the scores are not independent estimates of final performance. See the [comparison data](Program/reports/2026-10-10/model_tree_v1/linear_tree_comparison.csv) and [research evidence index](Program/reports/README.md).

## Implementation status

Data preparation, fixed partitions, descriptive analysis, development model comparisons, sensitivity checks and the local comparison/import application are implemented. The latest recorded research verification includes 48 passing unit and integration tests.

The integrated overview, searchable data explorer, similar-game references, group-versus-random diagnostic, final model selection and reserved-set evaluation remain to be completed. Public deployment and user-task evaluation are also pending. Power BI files provide supporting visual material; the main application does not require Power BI.

The project supports historical comparison. Owner intervals and install lower bounds do not measure revenue or profit, and observed associations do not establish causal effects or guarantee future commercial success.

## Run the application

With `uv` installed and the required local analysis files available, open `Program/START_DEMO.cmd` on Windows. Alternatively, run from `Program/`:

```powershell
uv sync --locked
uv run --locked python src/demo/server.py --open
```

The application opens at `http://127.0.0.1:8765/`. Large datasets and generated model artifacts are excluded from Git, so cloning this repository alone is insufficient to run the complete application. See the [setup and reproduction guide](Program/README.md) and [demonstration guide](Program/DEMO_GUIDE.md).

## Repository structure

| Location | Contents |
|---|---|
| [Dataset](Dataset/README.md) | Dataset sources and expected local input locations |
| [Program](Program/README.md) | Environment setup and pipeline execution |
| `Program/src/` | Data processing, analysis, modelling, comparison service and CSV import code |
| `Program/config/` | Versioned analysis rules, feature policy and experiment settings |
| `Program/tests/` | Automated checks for data, models and application behaviour |
| [Program/reports](Program/reports/README.md) | Reports, aggregate results, protocols and verification evidence |
| [Program/notebooks](Program/notebooks/README.md) | An executable example of data exploration and model reproduction |

## Attribution

ChatGPT and Codex assisted with planning, implementation, analysis workflows, verification and documentation, including report drafting. The [AI assistance statement](Program/reports/planning/ai_assistance_log.md) describes this contribution. Third-party datasets and source materials remain subject to their original licences.
