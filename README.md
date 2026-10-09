# FYP_Game

HKBU BCDA FYP：**A Data-Driven Decision Support System for Early-Stage Game Development Planning**（工作題目；Steam＋Android 方向仍待導師確認）。

目前已有資料審核、清理、固定特徵與群組切分、初步分析、歷史比較原型，以及首輪模型比較（26 組設定／78 次擬合）。CSV 匯入與應用資料版本切換、後續模型比較及最終評估尚未完成。研究筆記和開發 CV 結果不等於最後研究結論。

## 專案入口

- [目前進度](Program/PROJECT_STATUS.md)
- [啟動比較原型](Program/START_DEMO.cmd)／[操作指引](Program/DEMO_GUIDE.md)
- [目前報告 FYP_v1](Program/reports/FYP_v1.docx)
- [報告與研究紀錄索引](Program/reports/README.md)
- [產品範圍與待辦](Program/reports/planning/product_scope_v1.md)
- [程式環境、審核與重跑方法](Program/README.md)
- [資料來源與本機放置方法](Dataset/README.md)
- [候選清理報告](Program/reports/2026-10-06/cleaning_candidate_v1/cleaning_report.md)
- [資料字典](Program/reports/2026-10-06/cleaning_candidate_v1/data_dictionary.md)
- [首輪模型結果](Program/reports/2026-10-07/model_dev_v1/results_notes.md)

原始 `FYP_PROJECT_CONTEXT_FOR_CODEX.md` 目前放在此 repository 外的上一層 FYP 工作目錄。這裡不建立重複副本；最新進度以 `Program/PROJECT_STATUS.md` 為準。舊入口中不存在的 `GITHUB_SETUP.md` 連結已移除。

## 檔案保留與清理

| 位置 | 用途與保留原則 |
|---|---|
| `Dataset/` | 已解壓的原始資料、來源說明；保留，完整審核仍會讀取非主分析資料 |
| `Program/src/`、`config/`、`tests/` | 程式、固定規則及測試；保留路徑 |
| `Program/data/raw/` | 來源 metadata、固定版本下載及原始 hash 證據；保留 |
| `Program/data/interim/` | 清理／診斷輸入和中間產物；仍被研究流程引用，不當成無用快取 |
| `Program/data/processed/` | 固定分析資料、切分、模型與預測；保留，避免重訓或失去實驗證據 |
| `Program/reports/` | 學生報告、歷史實驗證據與目前計劃；按索引閱讀 |
| `Program/.venv/`、`Program/experiments/model_dev_v1/.venv/` | 資料／原型環境和獨立模型環境；各有用途，保留 |
| `.git/` | GitHub Desktop 所需版本歷史；保留 |
| `__pycache__/`、Word 暫存檔 | 自動產生，不是交付成果；Git 忽略不代表會自動從磁碟刪除 |

2026-10-10 清理：5 個下載 ZIP 的 17 個成員逐一與保留原檔核對 SHA-256 後，刪除重複 ZIP，約釋放 **1.58 GiB**。17 個原始資料檔亦與原始來源清單 hash 相符。Python 快取約 40.6 MiB 的批次刪除被工具安全規則拒絕，本輪保留；沒有刪除 `.venv`、研究檔案或 Git 歷史。詳見 [核對及清理紀錄](Program/reports/maintenance/cleanup_2026-10-10.json)。

以後下載資料，確認解壓檔齊全且內容一致後，才移除 ZIP；不要按「日期較舊」刪除研究資料。新增實驗需有用途、版本和結果摘要，避免把臨時草稿當成永久成果。保留現有路徑，讓程式和歷史紀錄繼續可用。

## Repository 內容

`Program/src/`、`config/`、`tests/`、環境鎖定檔及研究報告納入版本管理。大型原始資料、生成的 Parquet 與 `.venv` 保留在本機，不會隨 clone 下載；請按照資料來源說明準備輸入。

在本機保留 `Dataset/` 與 `Program/` 並排的目錄結構。歷史審核檔可能記錄搬移前的本機絕對路徑，這些是當時的執行證據；目前程式從所在位置計算輸入目錄。不要把歷史 manifest 當成另一台電腦已成功執行的證明。

資料集及保存的第三方來源文件各自受其原始授權約束；本專案未新增涵蓋全部內容的統一授權。
