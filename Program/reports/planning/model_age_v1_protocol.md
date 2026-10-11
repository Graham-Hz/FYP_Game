# Age-restricted refitting v1

Prespecified 2026-10-11 before running age-restricted fits or viewing their scores. This implements the two age-cohort checks in the frozen analysis_v1 sensitivity registry. It is distinct from the 2026-10-10 diagnostic that only filtered previously saved predictions.

## Question and fixed design

For each platform, does fitting only games observed for at least 180 or 365 days change the descriptive model-family/feature conclusions? Does such refitting improve or worsen predictions compared with the original primary-cohort fits, when evaluated on exactly the same age-eligible validation games?

Use only the original analysis_v1 train partition. Apply age_days >= threshold to both fitting and validation rows, excluding missing ages. Preserve stored developer groups, CV folds and outcome definitions. Never reassign a group when some of its games are excluded. Primary train counts: Steam 51,152; Android 221,806. Retained age cohorts: Steam 45,734 / 40,814; Android 196,917 / 168,083 for 180 / 365 days. The two cohorts overlap and are not independent experiments. Do not score calibration or test.

Keep the family-specific configurations selected in the original primary-cohort CV: class-prior and selected age-only baseline on each platform; selected linear and forest models for P/P+A, plus Steam P_without_price. Exact candidates/parameters are listed in config/model_age_v1.json and checked against the source development_choices and fold metadata. There is no new tuning or family selection. Steam has eight configurations per cutoff; Android six: 28 configuration/cohort combinations and 84 fold fits total, including 30 forest, 42 logistic and 12 class-prior fits. Refit encoders, imputation/scaling, vocabulary, class priors and class weights from the age-eligible fitting rows only. Original encoders are not reused for new fits.

All estimator settings, seed 42, two workers and the locked model environment remain as in model_dev_v1/model_tree_v1. Logistic convergence handling is the existing prespecified 1,000-iteration fit plus one retry at 3,000, otherwise fail without dropping the fold. Source files and prior model artifacts are immutable. Save a new pipeline, probabilities and fold metadata for every fit. Write completion metadata and the run manifest by temporary file plus atomic replacement; a verified completion marker is required to resume a fold. An incomplete model/prediction write without a marker may be replaced by recomputing that same fold. A completed unchanged run verifies hashes and returns without training or rewriting results.

## Matched comparisons

For every original saved out-of-fold prediction file, filter by the exact validation IDs retained for the new age-restricted fold, verify one-to-one membership/targets/groups/fold, and recompute original-model metrics on those rows. Compare refit minus original using these matched rows. Do not subtract full-cohort metrics from restricted-cohort metrics and attribute the difference to training: that also changes the evaluated population.

Report equal-weight mean-fold macro-F1 and fold SD (dispersion, not confidence interval), balanced accuracy, accuracy, log loss and summed multiclass Brier. Preserve each fold, pooled OOF metrics, per-class precision/recall/F1/support and confusion matrices for both modes. Include retained/excluded/missing-age counts, class/group support, and Android free/paid/unknown descriptive subgroup metrics and support in each mode. Report restricted-refit forest minus restricted-refit linear for the same feature set; include the matched original difference for context. Baselines are also refitted so changed target prevalence is visible.

These are descriptive development comparisons. Hyperparameters were selected using the original training CV, which includes these age subsets, so the new scores are not independent performance estimates. No bootstrap significance claim, retuning or deployment decision is made here. Older cohorts have different label distributions and historical composition; this does not identify a causal age effect or a fixed-horizon forecast. P remains post-release snapshot attributes. PC price units remain uncertain, and Mobile paid support is much smaller than free support.

## Verification and scope

Independently reconstruct age eligibility and exact fold membership from frozen features/labels; verify all hashes, fold/group isolation, original matched predictions, three-class probabilities, fold means/SDs, pooled/class/confusion/subgroup arithmetic and estimator parameters. Verify refit-only numeric statistics/vocabulary, prior frequencies and saved-model replay. Unit checks cover exact age boundaries/missing values, prevention of fold reassignment and incorrect matched comparison IDs, and safe checkpoint completion behavior. Record tests, resume evidence and protected-file hashes separately.

This completes age-cohort refitting only. Broader Steam price/software/demo cohorts, Mobile alternative install tiers, group-versus-random diagnostics, final selection/refit/calibration/test, model integration, similar-game references and user evaluation remain separate work. Results support student-authored Chapter 2 methodology and later Results/Discussion; no report prose is inserted into the student's DOCX.

```powershell
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/run_age_sensitivity.py
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/verify_age_sensitivity.py
```

Reuses the implementations and official API references already recorded in [linear protocol](model_dev_v1_protocol.md) and [forest protocol](model_tree_v1_protocol.md); no new estimator API or environment dependency.
