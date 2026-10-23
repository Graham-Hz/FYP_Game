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

## Supplementary revenue sources

These original downloads are audited separately and are not part of the frozen modelling cohort. Keep their filenames and contents unchanged. Revenue estimates are not developer profit.

| Expected local input | Source | Intended role |
|---|---|---|
| `Steam Revenue Top 1500 2024/Steam_2024_bestRevenue_1500.csv` | [Steam revenue top 1500](https://www.kaggle.com/datasets/alicemtopcu/top-1500-games-on-steam-by-revenue-09-09-2024) | Candidate for descriptive estimated-revenue analysis within the selected 2024 releases |
| `Highest Grossing Mobile Games/mobile-games.csv` | [Highest-grossing mobile games](https://www.kaggle.com/datasets/mattop/highest-grossing-mobile-games) | Historical high-grossing cases; not Android-only revenue labels |
| `Steam Launch Lever Panel 2026/steam-launch-lever-panel-2026.csv` | [Steam launch panel](https://huggingface.co/datasets/steamforecast/steam-launch-lever-panel-2026) | Supplementary revenue-proxy methodology; not observed first-week sales |

The [source audit](../Program/reports/2026-10-23/revenue_sources/audit.json) records local file hashes, quality checks and matching candidates. The 1,500-row Steam source contains no duplicate Steam IDs and matches 1,406 IDs in the March 2025 raw source (1,294 in the primary cohort). Its 85 zero-price, positive-revenue rows need source-definition review. Later metadata must not be presented as features known before the September 2024 revenue snapshot.

The mobile file contains 104 titles. Conservative name matching finds 50 with one candidate and five with multiple candidates in the Google Play source; these are not verified joins. Per-title revenue observation dates and platform breakdowns are absent. The 10,403-row launch panel matches 8,540 raw Steam IDs; its logged target matches natural logarithms, whereas the dataset card describes base-10 logarithms. These limitations prevent treating all three sources as interchangeable revenue observations.

## Restore local inputs

Keep the folder names and original filenames above, with `Dataset/` beside `Program/`. Check the [source file inventory](../Program/data/raw/existing_local_sources.json) for recorded sizes and SHA-256 hashes, and the [dataset inventory](../Program/reports/2026-10-05/dataset_inventory.csv) for provenance and audit coverage.

The original Kaggle download versions are not fully established. A current download may differ from the recorded files and should not be treated as the same research snapshot. Follow the [pipeline guide](../Program/README.md) after restoring compatible inputs.

The two source snapshots represent different observation periods. Steam owner intervals and Android installation lower bounds are proxies, not exact sales or revenue. Dataset licences and attribution requirements remain those of their original providers.
