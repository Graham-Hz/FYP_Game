# Dataset sources

This directory holds the local source datasets used to audit and prepare historical Steam and Android game data. Large downloaded files are excluded from Git; the repository contains source documentation and version evidence.

## Principal analysis sources

| Expected local input | Source | Role |
|---|---|---|
| `Steam Games Dataset 2025/games_march2025_full.csv` | [Steam Games Dataset 2025](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset) | March 2025 Steam snapshot |
| `Google Play Store Apps/Google-Playstore.csv` | [Google Play Store Apps](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps) | June 2021 Google Play collection; game categories are selected during processing |

## Supplementary audit sources

The complete source audit also reads these datasets. They are not all merged into the primary modelling samples.

| Local folder | Source |
|---|---|
| `Steam Games Dataset` | [FronkonGames Steam dataset](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) |
| `Steam Store Games (Clean dataset)` | [Steam Store Games](https://www.kaggle.com/datasets/nikdavis/steam-store-games) |
| `Game Recommendations on Steam` | [Game Recommendations on Steam](https://www.kaggle.com/datasets/antonkozyriev/game-recommendations-on-steam) |

[HuggingFace.txt](HuggingFace.txt) records supplementary links. The acquired Steam Parquet has a pinned revision and is downloaded by `Program/src/data/fetch_sources.py` into ignored local storage under `Program/data/raw/huggingface/`. Full RAWG and Steam review collections are outside the core download scope.

## Restore local inputs

Keep the folder names and original filenames above, with `Dataset/` beside `Program/`. Check the [source file inventory](../Program/data/raw/existing_local_sources.json) for recorded sizes and SHA-256 hashes, and the [dataset inventory](../Program/reports/2026-10-05/dataset_inventory.csv) for provenance and audit coverage.

The original Kaggle download versions are not fully established. A current download may differ from the recorded files and should not be treated as the same research snapshot. Follow the [pipeline guide](../Program/README.md) after restoring compatible inputs.

The two source snapshots represent different observation periods. Steam owner intervals and Android installation lower bounds are proxies, not exact sales or revenue. Dataset licences and attribution requirements remain those of their original providers.
