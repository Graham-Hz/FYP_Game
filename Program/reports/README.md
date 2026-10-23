# Reports and research evidence

This directory contains the project reports, data definitions, experimental protocols, aggregate results and verification records. Dates identify experiment or document versions, not dataset observation dates.

## Project reports

| Document | Contents |
|---|---|
| [Project report draft](FYP_v1.docx) | Working report manuscript |
| [First Progress Report](2026-10-23/first_progress/First_Progress_Report_HsiehLungKwun_24221546.docx) | Editable progress report |

These are report files, not evidence of institutional submission.

## Data and methodology

| Evidence | Purpose |
|---|---|
| [Dataset feasibility](2026-10-05/dataset_feasibility_report.md) | Source comparison, quality and coverage |
| [Target feasibility](2026-10-05/target_feasibility.md) | Outcome proxies and interpretation limits |
| [Supplementary revenue audit](2026-10-23/revenue_sources/audit.json) | Source hashes, quality issues and identifier/name matching coverage; no model integration |
| [Steam revenue analysis](2026-10-23/revenue_sources/analysis.json) | Selected-sample distribution, concentration and group summaries; preparation counts, provenance and explorer artifact hash |
| [Cleaning report](2026-10-06/cleaning_candidate_v1/cleaning_report.md) | Parsing, exclusions and quality checks |
| [Data dictionary](2026-10-06/cleaning_candidate_v1/data_dictionary.md) | Prepared field definitions |
| [Analysis protocol](2026-10-06/analysis_v1/analysis_protocol.md) | Primary cohorts, feature policy, developer groups and fixed partitions |
| [Literature comparison](2026-10-06/analysis_v1/literature_review_notes.md) | Related methods and the recorded depth of source review |
| [Reference verification](planning/chapter1_verified_references_2026-10-08.md) | Bibliographic details and publication versions |
| [Methodology evidence map](planning/chapter2_evidence_map.md) | Connection between system components, methods and supporting artifacts |

## Analysis and model results

| Experiment | Results | Protocol |
|---|---|---|
| Descriptive analysis | [Training EDA](2026-10-07/train_eda_v1/eda_notes.md) | [Analysis design](2026-10-06/analysis_v1/analysis_protocol.md) |
| Baselines and linear models | [Development results](2026-10-07/model_dev_v1/results_notes.md) | [Linear protocol](planning/model_dev_v1_protocol.md) |
| Tree comparison | [Random Forest results](2026-10-10/model_tree_v1/results_notes.md) | [Tree protocol](planning/model_tree_v1_protocol.md) |
| Observation age | [Age sensitivity](2026-10-11/model_age_v1/results_notes.md) | [Age protocol](planning/model_age_v1_protocol.md) |
| Cohort and outcome tiers | [Scope sensitivity](2026-10-13/model_scope_v1/results_notes.md) | [Scope protocol](planning/model_scope_v1_protocol.md) |

The model results use training developer-group validation. Final model selection, calibration and reserved-test evaluation are not complete. CSV summaries, manifests and verification files alongside these notes support the measurements; they are research evidence rather than temporary files.

## Application and visual evidence

- [Local application checks](2026-10-07/demo_v1/verification_notes.md)
- [CSV import and version checks](2026-10-10/csv_import_v1/verification_notes.md)
- [Executable notebook verification](2026-10-16/walkthrough_v1/verification.json)
- [Power BI material](powerbi/), including the report file and historical-overview screenshots

Power BI screenshots provide supporting descriptive views. They do not establish that all PBIX calculations or interactions have been independently validated.

## Attribution and reproducibility

The [AI assistance statement](planning/ai_assistance_log.md) describes contributions to implementation, analysis and documentation. Large raw data, prepared tables, fitted models and per-row predictions remain in local storage outside Git. The [program guide](../README.md) documents the required inputs and execution paths.
