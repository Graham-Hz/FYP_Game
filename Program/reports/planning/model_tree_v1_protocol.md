# Tree development comparison v1

Prespecified on 2026-10-10 before fitting tree candidates or inspecting their scores, after the completed linear development comparison. This is a small additional model-family experiment, not a new independent evaluation.

## Fixed design

Reuse analysis_v1 primary-cohort train rows, stored developer-group folds and the locked experiments/model_dev_v1 environment. PC: 51,152 rows; Mobile: 221,806. Fit on two folds and predict the third. Read no calibration/test outcomes for scoring or selection. Check original analysis/model dependencies and all source artifact hashes. Keep old results and implementation immutable. No fold reroll, silent failed-fit omission or search enlargement in response to scores.

Use RandomForestClassifier because it supports the existing sparse multi-hot planning representation and allows nonlinear interactions without adding a dependency. This is a resource-bounded representative tree comparison; it does not establish the best possible tree algorithm. Histogram boosting and other families are not tested in this run.

Grid: PC P, P+A, P_without_price; Mobile P, P+A. For each, maximum leaves {256, 1024} and class weight {None, balanced}: 20 configurations / 60 fold fits. Fix 100 trees, Gini criterion, maximum depth 20, minimum leaf size 20, sqrt feature subsampling, bootstrap enabled, seed 42, two workers, no OOB scoring. Complete settings are in config/model_tree_v1.json. The small grid limits compute and artifacts while contrasting two complexity caps and class imbalance handling. These settings were not chosen using test outcomes.

Reuse the frozen PlanningEncoder fitted separately within each fitting fold, including vocabulary, missing indicators and numeric statistics. Monotonic numeric transformations/scaling are retained for a consistent representation; there is no claim they improve forests. Class weights are fitted only from fitting-fold labels. Preserve label order, app/developer membership and checksummed checkpoints. A metadata file is the completion marker for each fold; verified completed folds can resume after interruption. A changed identity requires a new experiment version.

## Comparisons and diagnostics

Primary metric: equally weighted mean of three fold macro-F1 values; report sample fold SD as dispersion, not a confidence interval. Also save balanced accuracy, accuracy, log loss and summed multiclass Brier. Save OOF probabilities, pooled metrics, each class's precision/recall/F1/support, confusion matrices and Mobile free/paid/unknown support and fixed-three-label macro-F1. Select within each feature set by macro-F1; ties within 1e-6 prefer 256 leaves, then unweighted. Compare with the already selected linear configuration for the same feature set and same folds. This reuse of selection CV is not unbiased final performance; no significance claim or final model choice is made.

After tree selection, evaluate the saved OOF predictions of both selected families on age >=180 and >=365 subsets, and Mobile free/paid/unknown subsets. Report sample counts, class support and fixed-three-label macro-F1. Age subsets overlap. This measures how primary-cohort fits perform on those subgroups. It is NOT refitting on age-restricted cohorts, and does NOT complete the sensitivity registry's age-restricted training experiments. No new tuning uses these diagnostics. Wider PC cohorts, alternative Mobile tiers, group-vs-random evaluation, age-restricted refits, calibration, final test, deployment and actual user evaluation remain pending.

P contains historical snapshot attributes, not proven pre-release measurements. P+A includes elapsed observation age, not a controlled forecast horizon. Owner/install tiers are historical popularity proxies, not revenue or success probabilities. The PC source-price unit remains uncertain; retain the without-price comparison. No feature-importance ranking is supplied as causal planning advice.

## Verification and reproduction

Independently reconstruct saved prediction metrics and membership; replay saved pipelines and verify predictor allowlists, fitting-only vocabulary/numeric statistics, estimator settings and hashes. Include tests for held-out/group leakage rejection, incomplete fold matrices and deterministic tie handling. Verify comparison/diagnostic tables from saved OOF data. Keep code, config, environment and report hashes in manifests.

```powershell
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/run_tree_development.py
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/verify_tree_development.py
```

API behavior checked against official [RandomForestClassifier documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html), accessed 2026-10-10: sparse input, class weighting, leaf limits, parallel workers and seeded randomness. The installed version is pinned by the existing model environment. This working protocol is research evidence, not submission-ready Chapter 2 prose.
