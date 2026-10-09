# 本機資料與來源

大型資料不放進 Git repository。此目錄保留下載來源與還原位置；不要用 `git add -f` 強制加入資料檔。

| 本機資料夾 | 來源 |
|---|---|
| Steam Games Dataset | https://www.kaggle.com/datasets/fronkongames/steam-games-dataset |
| Steam Games Dataset 2025 | https://www.kaggle.com/datasets/artermiloff/steam-games-dataset |
| Google Play Store Apps | https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps |
| Steam Store Games (Clean dataset) | https://www.kaggle.com/datasets/nikdavis/steam-store-games |
| Game Recommendations on Steam | https://www.kaggle.com/datasets/antonkozyriev/game-recommendations-on-steam |

下載／解壓後保留上述資料夾名稱及來源檔名。兩個主要候選輸入是 `Steam Games Dataset 2025/games_march2025_full.csv` 和 `Google Play Store Apps/Google-Playstore.csv`；完整審核還會讀取其他資料集，詳見 [Program README](../Program/README.md)。

原本下載的 Kaggle 精確版本仍未全部確定。現在下載的最新版本可能與審核用版本不同；請使用 [原始檔案大小及 SHA-256 清單](../Program/data/raw/existing_local_sources.json) 核對，不要將不同版本當作相同資料。完整版本與來源紀錄見 [dataset inventory](../Program/reports/2026-10-05/dataset_inventory.csv)。

[HuggingFace.txt](HuggingFace.txt) 保存補充來源連結。已使用的 Steam Hugging Face Parquet 有固定 revision，由 `Program/src/data/fetch_sources.py` 下載到被 Git 忽略的 `Program/data/raw/huggingface/`。RAWG 及完整評論資料不屬本次核心下載範圍。

新 clone 只會取得程式、報告和來源說明。準備原始資料後，依 Program README 重建審核 Parquet，再執行候選清理；GitHub 不是此專案所有本機資料的備份。

## 2026-10-10 清理紀錄

已刪除 5 個重複下載 ZIP；其 17 個成員均逐檔解壓串流讀取並核對 SHA-256，與現有解壓檔完全一致。所有 CSV／JSON 原始資料、資料夾名稱及來源連結保留。原檔 hash 亦與 `existing_local_sources.json` 相符。

2026-10-05 的來源清單及審核報告仍記錄當時 ZIP 存在的事實，不回寫歷史清單。刪除 ZIP 不影響資料分析，但日後重新盤點時 ZIP 數量自然不同。核對證據在 [cleanup_2026-10-10.json](../Program/reports/maintenance/cleanup_2026-10-10.json)。

非主分析 dataset 仍是完整審核、來源比較和清理決定的證據；不是因暫時沒有進模型便可以當作快取刪除。
