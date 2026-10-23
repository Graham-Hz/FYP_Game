# Executable analysis example

[01_understand_your_fyp.ipynb](01_understand_your_fyp.ipynb) demonstrates CSV loading, descriptive statistics, visualisation and reproduction of one existing Logistic Regression fold. The notebook includes Chinese explanatory text and saved outputs. It is an optional executable example, separate from the production cleaning pipeline and full experiment suite.

## Run

From `Program/`, open [START_WALKTHROUGH.cmd](../START_WALKTHROUGH.cmd). Keep the terminal open and use the JupyterLab URL it displays. Open the notebook and run cells in order, or select **Kernel > Restart Kernel and Run All Cells**.

The locked environment is `experiments/walkthrough_v1/`. When using another notebook editor, select its Python kernel rather than changing the model experiment environment. The first launch may download environment dependencies.

## Reproduced analysis

| Component | Scope |
|---|---|
| Input | 221,806 Android training rows exported from the prepared research data |
| Exploration | Missingness, value counts, grouped statistics and three Matplotlib figures |
| Model | Existing Android `P_C0.1_none` Logistic Regression configuration, fold 0 |
| Fold sizes | 147,902 fitting rows and 73,904 validation rows |
| Validation | Comparison with the saved out-of-fold probabilities |

The notebook does not tune new settings, evaluate calibration/test data or replace the saved research models. Figure outputs are written to `reports/2026-10-16/walkthrough_v1/`. It requires local prepared data and model reference artifacts that are not included in a source-only clone.

## Verification

From `Program/`:

```powershell
uv run --project experiments/walkthrough_v1 --locked python.exe -X utf8 -B notebooks/verify_walkthrough.py
```

The recorded fresh-kernel execution and prediction comparison are in [verification.json](../reports/2026-10-16/walkthrough_v1/verification.json). Run all prerequisite cells if a name is undefined; use the locked environment for missing dependencies; investigate source hash mismatches rather than removing the checks.
