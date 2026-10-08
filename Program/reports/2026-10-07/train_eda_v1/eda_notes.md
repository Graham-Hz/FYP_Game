# Training-only EDA v1

Generated descriptive working notes, not submission prose. No model fitted; no holdout performance evaluated.

Source scope: Steam March 2025 positive-observed-price primary cohort; Android June 2021 conservative game cohort. Rows below are TRAIN only.

## Outcome balance

| Platform | Train n | Tier | Count | Percent |
|---|---:|---|---:|---:|
| pc | 51,152 | O1_source_interval_up_to_20k | 38,428 | 75.13% |
| pc | 51,152 | O2_source_intervals_20k_to_100k | 8,527 | 16.67% |
| pc | 51,152 | O3_source_intervals_100k_plus | 4,197 | 8.20% |
| mobile | 221,806 | M1_under_1k | 103,908 | 46.85% |
| mobile | 221,806 | M2_1k_to_under_100k | 81,403 | 36.70% |
| mobile | 221,806 | M3_100k_plus | 36,495 | 16.45% |

## Age at observation by outcome tier

| Platform | Tier | Median days | P25 | P75 |
|---|---|---:|---:|---:|
| pc | O1_source_interval_up_to_20k | 1022.0 | 374.8 | 1972.2 |
| pc | O2_source_intervals_20k_to_100k | 1808.0 | 945.0 | 2900.0 |
| pc | O3_source_intervals_100k_plus | 2492.0 | 1283.0 | 3433.0 |
| mobile | M1_under_1k | 598.0 | 305.0 | 1164.0 |
| mobile | M2_1k_to_under_100k | 900.0 | 402.0 | 1622.0 |
| mobile | M3_100k_plus | 1373.0 | 733.0 | 2096.0 |

## Interpretation and next experiments

- Class counts motivate a majority/class-prior baseline and macro-F1 alongside class-specific results; these counts are not cross-validation scores.
- Age summaries motivate the prespecified age-only and P versus P+A comparisons; they do not establish a causal effect or a fixed-horizon forecast.
- `distributions.csv` covers all prespecified genres/functions or categories/monetization groups, rather than reporting only favorable examples. Within-group percentages have group_n as denominator. Multi-valued PC groups overlap; their totals do not sum to train_n.
- The descriptive age bins (0-179, 180-364, 365-1094, 1095+ days) are display groupings, not newly chosen outcome cutoffs or changes to the frozen split.
- Unknown free is separate from false; missing USD prices are not zero. Missing/empty feature counts are recorded in `missingness.csv`.
- Empty planning_categories can mean no whitelisted planning feature, rather than missing source categories. The empty_or_missing bucket and missingness.csv count structural emptiness; consult categories_unavailable for source unavailability.
- No cross-platform market ranking, significance test, confounder adjustment, revenue inference or causal claim is supported by these tables. Both cohorts have selection limitations; unknown outcomes excluded upstream are not represented here.
- Before candidate fitting, finalize preprocessing and the small parameter grid. Use existing train group-CV, preserve calibration/test, and keep imported application snapshots separate from the research experiment.

Reproduce: `uv run --locked python.exe src/analysis/profile_training.py`
