# FYP_Game

HKBU BCDA FYP：跨平台遊戲開發規劃與決策支援系統（研究方向暫定）。

目前完成 Steam／Android 資料可行性審核、研究設計草案及候選清理流程；尚未訓練模型或完成應用程式。所有分析文件是研究工作筆記，並非最後研究結論。

## 專案入口

- [目前進度](Program/PROJECT_STATUS.md)
- [原始專案背景](FYP_PROJECT_CONTEXT_FOR_CODEX.md)（保留 2026-09-14 版本；最新實際進度以上方進度紀錄為準）
- [程式環境、審核與重跑方法](Program/README.md)
- [資料來源與本機放置方法](Dataset/README.md)
- [候選清理報告](Program/reports/2026-10-06/cleaning_candidate_v1/cleaning_report.md)
- [資料字典](Program/reports/2026-10-06/cleaning_candidate_v1/data_dictionary.md)
- [GitHub 上傳與後續更新](GITHUB_SETUP.md)

## Repository 內容

`Program/src/`、`config/`、`tests/`、環境鎖定檔及研究報告納入版本管理。大型原始資料、生成的 Parquet 與 `.venv` 保留在本機，不會隨 clone 下載；請按照資料來源說明準備輸入。

在本機保留 `Dataset/` 與 `Program/` 並排的目錄結構。歷史審核檔可能記錄搬移前的本機絕對路徑，這些是當時的執行證據；目前程式從所在位置計算輸入目錄。不要把歷史 manifest 當成另一台電腦已成功執行的證明。

資料集及保存的第三方來源文件各自受其原始授權約束；本專案未新增涵蓋全部內容的統一授權。
