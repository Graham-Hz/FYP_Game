# Cohort and target sensitivity v1

Prespecified 2026-10-13 before fitting or inspecting new scores. This completes the remaining cohort/target entries in analysis_v1, following model_age_v1. No new family search or retuning. Independent final evaluation remains reserved.

## Cohorts and fixed assignments

Use only records already assigned to train by the frozen cohort ledger. Retain each developer_group and cv_fold, including groups formed using excluded bridge products. Never recompute groups after changing eligibility. Existing primary train: PC 51,152; Mobile 221,806.

- PC all_price: known target/developer, retain software-only exclusion, relax positive-price requirement only (55,775 train rows). This is known-label scope sensitivity, NOT a representative free-versus-paid success comparison: unknown owner labels are associated with zero observed price.
- PC include_software: known target/developer and positive observed price; relax software-only exclusion only (51,621).
- PC no_demo_exception: original primary minus reviewed exception app_id 1129080 (51,151). The removed game is train fold 0. Keep the original group graph, including this game; do not claim a regrouping experiment. Fold-0 fitting rows are unchanged, while folds 1/2 lose one fitting row.
- Mobile four_tiers: exactly original primary train IDs/features/groups/folds; replace M3 with M3_100k_to_under_1m and M4_1m_plus. Other tiers unchanged. Thresholds <1k, [1k,100k), [100k,1m), >=1m follow the 2026-10-05 design, not score optimization. Derive labels from the frozen candidate minimum_installs column.

Rebuild extra PC planning features using the original frozen rules and verify all shared primary cells against analysis_v1. Use already-frozen primary features for the reviewed exception. Assert source targets and group assignments agree. Save new train-only experiment datasets separately, together with IDs/groups/folds and flags; no calibration/test output or scoring. Record train scope flow including unknown-label exclusions and added/removed rows, class/fold/group support and metadata coverage.

## Models and comparisons

Use the same family-specific selected configurations as model_age_v1, checked against original development_choices: PC eight candidates per scope (prior, age-only LR, LR and RF P/P+A/P_without_price); Mobile six (prior, age-only LR, LR and RF P/P+A). Total 30 scenario/configuration combinations and 90 fold fits. Refit preprocessing and classifier using only each scenario's fitting folds. Keep seed 42, two workers, original estimator settings and the locked model_dev_v1 environment. Existing LR convergence retry at 3,000 iterations is allowed once after 1,000; otherwise fail the run. Fixed hyperparameters originally selected under three tiers remain fixed under four tiers: this measures target sensitivity of these settings, not an optimally tuned four-class model.

For PC report full scenario OOF metrics. Separately, compare refit and original model on the intersection of scenario validation IDs and original primary validation IDs. Recompute both sets of metrics on these SAME games; record original prediction hashes. Extra-only strata are descriptive and have no original-OOF counterpart. Never interpret a full expanded-scope score minus a primary-scope score as a training effect.

For Mobile report four-class metrics independently. For a compatible three-class diagnostic, sum new probabilities p2+p3, retain p0/p1, map the two upper labels back to original M3 and recompute argmax AFTER probability summation. Compare with original three-class OOF on the same IDs. Four-class macro-F1/log loss/Brier are not directly comparable to three-class scores. Report high-tier confusion/recall and support. No tuning based on collapsed scores.

Metrics: equal-weight mean-fold macro-F1 (primary), fold SD (dispersion, not CI), balanced accuracy, accuracy, log loss and summed multiclass Brier. Also preserve each fold, pooled scores, per-class precision/recall/F1/support and confusion matrices. Fixed class lists in macro-F1, including absent subgroup classes. Subgroups: PC original-primary versus added-only and software-only versus other; Mobile free/paid/unknown for four-tier and collapsed outputs. Counts and absent classes accompany subgroup scores; no stable conclusion from tiny groups. Report family differences only within identical scenario/mode/features/labels. No significance claims.

## Completion and validation

Versioned new config/data/runner/protocol; frozen earlier files and model environments unchanged. A run identity binds sources and dependencies. Each fold writes model/predictions atomically, then completion metadata last. Resume requires identity, membership and artifact hashes. A completed-run replay verifies outputs without rewriting them. Training interruption resumes missing folds, not the whole experiment.

Independent verification must reconstruct cohorts/features/targets without calling the new dataset builder, compare all exported cells and assignments, check absence of held-out IDs and group overlap, recompute metrics using NumPy, validate matched/collapsed comparison arithmetic, numeric fit statistics and vocabularies, estimator settings, full OOF coverage and saved-model replay. Test exact four-tier boundaries, probability collapsing (including changed winning class), cohort masks and rejection of invalid inputs. Results are development evidence, not final test or deployment approval. Power BI CSVs/app active versions and the student DOCX remain unchanged.

Next after this experiment: separately prespecified group-versus-random diagnostic; then final protocol/selection, full-train refit, calibration and final test. Do not automatically deploy the highest scope score.

Run in Program:

```powershell
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/run_scope_sensitivity.py
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/verify_scope_sensitivity.py
```

Uses unchanged estimator APIs and references from model_dev_v1/model_tree_v1/model_age_v1. No new dependency or algorithm is introduced.
