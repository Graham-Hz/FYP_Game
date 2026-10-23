# Program setup and research pipeline

This directory contains the Python data pipeline, model experiments and local web application for the game-planning decision-support system. See the [project overview](../README.md) for its purpose, implemented capabilities and limitations.

## Environments

Install `uv` and run commands from this directory. The data/application environment requires Python 3.14 and is defined by `pyproject.toml` and `uv.lock`.

```powershell
uv sync --locked
```

Model experiments have a separate locked environment in `experiments/model_dev_v1/`. The executable notebook uses `experiments/walkthrough_v1/`. Use each environment's lock file; `requirements.txt` is an export of the main environment, not the model environment.

## Launch the local application

The application requires the four frozen analysis files in `data/processed/analysis_v1/`: `pc_features.parquet`, `pc_labels_splits.parquet`, `mobile_features.parquet` and `mobile_labels_splits.parquet`. It checks their hashes against the recorded analysis version. These large files are not included in Git.

On Windows, double-click [START_DEMO.cmd](START_DEMO.cmd), or run:

```powershell
uv run --locked python src/demo/server.py --open
```

Keep the process running while using `http://127.0.0.1:8765/`. Press Ctrl+C to stop. A different port can be selected with `--port 8766`. The service binds to localhost and is not configured as a public web deployment.

See the [demonstration guide](DEMO_GUIDE.md) and [CSV import specification](CSV_IMPORT_GUIDE.md). Imported application snapshots are stored separately in `data/application/v1/`; they do not replace the frozen research data.

## Prepare the research inputs

Keep `Dataset/` and `Program/` as sibling directories. Restore the source files described in [Dataset/README.md](../Dataset/README.md) and compare their sizes and hashes with the recorded source inventory. Newer downloads may not reproduce the existing analysis version.

The complete audit reads supplementary datasets as well as the two principal sources. Its acquisition and audit commands are:

```powershell
uv run --locked python src/data/fetch_sources.py --date 2026-10-05 --download-steam
uv run --locked python src/data/validate_structure.py
uv run --locked python src/data/profile_datasets.py
uv run --locked python src/data/compare_and_targets.py
uv run --locked python src/data/build_reports.py
uv run --locked python src/data/verify_audit.py
uv run --locked python src/data/target_design_diagnostics.py
```

The acquisition command reuses the stored source lock and downloads the pinned Steam Hugging Face Parquet. It does not download the full RAWG or Steam review collections. The date identifies the existing audit version, not a request for current data. A new source audit needs a separately versioned configuration and outputs.

After the audit inputs are available, prepare and verify the candidate and analysis tables:

```powershell
uv run --locked python src/data/clean_candidates.py
uv run --locked python src/data/verify_clean_candidates.py
uv run --locked python src/data/freeze_analysis.py
uv run --locked python src/data/verify_analysis.py
uv run --locked python src/data/review_analysis_questions.py
uv run --locked python src/analysis/profile_training.py
uv run --locked python src/analysis/verify_training_eda.py
```

These commands rebuild research outputs; they are not required for an ordinary demonstration when verified local files already exist. Preserve the fixed source versions and analysis rules when reproducing saved results. A changed input hash requires investigation rather than bypassing validation. Large audit stages can require substantial time and temporary disk space; the DuckDB profiler uses a 4 GB memory limit and two threads, with additional memory used by Python and Arrow.

## Model experiments and checks

Each experiment protocol documents its inputs, model settings, execution commands and independent verification:

| Experiment | Protocol | Results |
|---|---|---|
| Baselines and Logistic Regression | [Linear model protocol](reports/planning/model_dev_v1_protocol.md) | [Development results](reports/2026-10-07/model_dev_v1/results_notes.md) |
| Random Forest comparison | [Tree model protocol](reports/planning/model_tree_v1_protocol.md) | [Tree results](reports/2026-10-10/model_tree_v1/results_notes.md) |
| Observation-age sensitivity | [Age protocol](reports/planning/model_age_v1_protocol.md) | [Age results](reports/2026-10-11/model_age_v1/results_notes.md) |
| Sample and target sensitivity | [Scope protocol](reports/planning/model_scope_v1_protocol.md) | [Scope results](reports/2026-10-13/model_scope_v1/results_notes.md) |

Run the unit/integration suite in the model environment:

```powershell
uv run --project experiments/model_dev_v1 --locked python -B -m unittest discover -s tests -v
```

Some integration checks require the frozen local artifacts. Browser checks require Microsoft Edge and the additional test dependency:

```powershell
uv run --locked --with playwright python.exe tests/check_demo_browser.py
```

This launches a separate headless browser and stores outputs in ignored local QA storage. The commands are documented reproduction paths; a clean clone without the required data cannot complete every check.

## Code and storage

| Location | Responsibility |
|---|---|
| `src/data/` | Source acquisition, auditing, cleaning, feature preparation and fixed partitions |
| `src/analysis/` | Training-set descriptive analysis and verification |
| `src/features/` | Feature preparation and predictor policy |
| `src/models/` | Model fitting, evaluation and experiment verification |
| `src/demo/` | Local HTTP service, historical comparison queries and browser interface |
| `src/imports/` | CSV contracts, validation, preview and application version management |
| `config/` | Versioned rules and experiment parameters |
| `data/raw/` | Source metadata and original downloads |
| `data/interim/` | Audit and candidate-cleaning tables |
| `data/processed/` | Frozen analysis tables, fitted artifacts and predictions |
| `data/application/` | Independent imported application versions |
| [reports](reports/README.md) | Methods, aggregate outputs and verification evidence |

Raw inputs remain separate from processed outputs. Model features exclude identifiers and outcome fields; calibration and test data remain reserved. Historical audit counts can differ from the primary analysis sample because the stages apply different eligibility rules. The [analysis protocol](reports/2026-10-06/analysis_v1/analysis_protocol.md) defines the fixed modelling cohort.
