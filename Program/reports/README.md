# 報告與研究紀錄索引

更新：2026-10-10。這個索引用來區分目前入口和歷史證據；保留原本日期及路徑，避免破壞引用或固定 manifest。

## 平日優先打開

| 檔案 | 用途 |
|---|---|
| [FYP_v1.docx](FYP_v1.docx) | 學生目前的報告；本輪清理不修改正文 |
| [PROJECT_STATUS](../PROJECT_STATUS.md) | 已完成／待完成工作及未知事項 |
| [產品範圍](planning/product_scope_v1.md) | 可更新資料、CSV 匯入與功能验收 |
| [首輪模型結果](2026-10-07/model_dev_v1/results_notes.md) | 現有開發 CV 比較，並非最終 test |
| [Chapter 1 最新核對](planning/fyp_v1_review_2026-10-08.md) | 對 10 月 8 日版本的修改清單，不代表已審閱學生之後的改稿 |
| [References 核對](planning/chapter1_verified_references_2026-10-08.md) | 正文引用所需書目與版本說明 |

## 需要寫 Method 或重現實驗時

| 目錄／文件 | 用途 |
|---|---|
| [2026-10-05 可行性報告](2026-10-05/dataset_feasibility_report.md) | 為何選擇目前資料；各來源的品質與限制 |
| [研究設計](2026-10-05/research_design/research_design_v1.md) | RQs 與研究設計背景；數量及已落實規則以之後的 analysis_v1 為準 |
| [候選清理報告](2026-10-06/cleaning_candidate_v1/cleaning_report.md) | 清理步驟、資料字典、逐列 ledger 及檢查 |
| [固定分析 protocol](2026-10-06/analysis_v1/analysis_protocol.md) | cohort、特徵、developer groups、split 與資料洩漏控制 |
| [文獻比較](2026-10-06/analysis_v1/literature_review_notes.md) | 原先閱讀深度及比較；出版 metadata 更新見上方 References 核對 |
| [初步 EDA](2026-10-07/train_eda_v1/eda_notes.md) | 訓練資料描述統計與缺失情况 |
| [原型驗證](2026-10-07/demo_v1/verification_notes.md) | 介面及工程測試證據 |
| [模型實驗規格](planning/model_dev_v1_protocol.md) | 首輪模型設定、前處理與執行方式 |
| [AI 協助紀錄](planning/ai_assistance_log.md) | 實際協助範圍；供學生核對披露 |

## 歷史檔案與快取的區別

日期資料夾、JSON manifest、驗證紀錄、統計 CSV 不是暫存：它們支持研究選擇、數據核對及重現。早期的 Chapter 1 review 和導師討論工作紙也保留作決策紀錄，閱讀時以上方最新入口為先。

`maintenance/` 僅保存清理／維護證據，不是 report 章節；本輪紀錄：[cleanup_2026-10-10.json](maintenance/cleanup_2026-10-10.json)。Word 的 `~$...` 和 `~WRL*.tmp` 是暫存名稱，已加入 Git 忽略規則；不要將它們當作報告版本。
