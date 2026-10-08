# First development model comparison

Prespecified on 2026-10-07 before fitting candidates or inspecting their scores. This implements the first linear-model development portion of the existing research protocol, not the entire experiment matrix.

## Data and evaluation

Use analysis_v1 train rows only: PC 51,152 and Mobile 221,806. Reuse the three stored developer-group folds. For each fold, fit on the other two and predict that fold. Fit vocabularies, numeric medians/scales, class priors and class weights from the fitting subset only. Confirm no app ID or developer group crosses each fold boundary. Verify frozen inputs first. Calibration and test are not used to choose or score these models.

The majority baseline outputs the fitting fold's class proportions; its predicted class is their argmax. Compare age-only Logistic Regression (C=1, unweighted/balanced) and feature sets P, P+A and PC P_without_price. Candidate grid for each feature set: C in {0.1, 1}, class weight in {None, balanced}. These are 15 configurations for PC and 11 for Mobile, each evaluated on three folds (78 fits total). No tree search in this first run.

The machine-readable settings are in `config/model_dev_v1.json`. Logistic Regression uses multinomial loss, L2 regularization, lbfgs, 1,000 iterations and tolerance 1e-4. A convergence warning permits one prespecified retry at 3,000 iterations; persistent failure is recorded and disqualifies that configuration from selection. Do not silently drop failed folds. Use two numeric-library threads and seed 42.

## Preprocessing

Use the frozen feature allowlist; exclude names, IDs, developer identity, outcome-related columns and split metadata. Numeric price/age: log1p, fitting-fold median imputation, fitting-fold mean/std scaling and an explicit missing indicator. All-missing numeric columns use 0 in transformed space, constant columns use scale 1. Nonfinite/negative numeric input is rejected (missing is permitted). Strings and booleans are categorical; unknown free is not false. Genre/function/language lists are binary token presence. Empty planning-feature lists are empty, not evidence that all source categories are missing. DictVectorizer learns token vocabulary only from fitting rows; validation unknown tokens do not enlarge it and are counted.

P contains historical snapshot properties that can describe planning choices; it is not validated pre-release measurement. P+A uses observed age and is not a fixed-horizon forecast. PC source-price currency remains unverified, making P_without_price a required comparison.

## Outputs and interpretation

- Primary comparison: equal-weight mean fold macro-F1, with fold SD explicitly labelled as dispersion, not a confidence interval. Also report balanced accuracy, accuracy, log loss and multiclass Brier (sum of squared probability errors across three classes, averaged over rows).
- Save all out-of-fold predictions, probabilities, fold models/encoders and metadata in ignored processed storage; keep aggregate metrics, per-class metrics, confusion matrices, fold coverage, timings, convergence notes and hashes in tracked reports.
- Report pooled OOF metrics separately from mean-fold values; they answer slightly different aggregation questions. Include Mobile free/paid/unknown descriptive subgroup metrics and support counts.
- Select a development configuration within each prespecified feature set by mean fold macro-F1; ties within 1e-6 prefer lower C, then unweighted. This reused selection CV is not unbiased final evaluation and does not justify a final model or significance claim.
- Independently reconstruct class-wise and aggregate metrics from saved predictions. Unit checks target fold-fitted encoding, missing/unknown handling and forbidden predictors.

No current user-facing model, automatic retraining, model calibration, final test scores or claim of business success probability is delivered by this run. Tree candidates, robustness, group-vs-random comparison and final evaluation remain subsequent research work.

## Reproduction and sources

Use a separate locked environment at `experiments/model_dev_v1/` to avoid changing the dependency lock already hashed by analysis_v1:

```powershell
uv sync --project experiments/model_dev_v1 --locked
uv run --project experiments/model_dev_v1 --locked python.exe src/models/run_development.py
uv run --project experiments/model_dev_v1 --locked python.exe src/models/verify_development.py
uv run --project experiments/model_dev_v1 --locked python.exe -m unittest discover -s tests -p test_model_preprocessing.py -v
```

Implementation checked against official [LogisticRegression documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [DictVectorizer documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.DictVectorizer.html) and [data-leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html), accessed 2026-10-07. The environment pins scikit-learn 1.9.1; its resolved dependencies are recorded by the separate uv.lock.
