# Chapter 2 寫作證據索引

更新：2026-10-13。按學生提供的七項要求整理。這是查證／寫作提綱，不是可直接提交的章節正文；學生需理解方法、以自己的文字撰寫並核對 AI 使用披露。`FYP_v1.docx` 沒有改動。最新完成狀態以 [PROJECT_STATUS](../../PROJECT_STATUS.md) 和各實驗的 verification 為準。

| 要求 | 自己撰寫時需要交代 | 可核對的本地證據 | 邊界／仍待完成 |
|---|---|---|---|
| Method | 研究問題、兩平台分開分析、歷史分級分類與系統工程評估；研究流程和產品功能如何相連 | [研究設計](../2026-10-05/research_design/research_design_v1.md)、[固定分析 protocol](../2026-10-06/analysis_v1/analysis_protocol.md)、[產品範圍](product_scope_v1.md) | 舊研究設計內的數量由 analysis_v1 更新；雙平台方向仍待導師確認 |
| Proposed method | 從來源追溯、清理、分組切分、fold 內前處理、基準／候選比較，到應用快照匯入和歷史比較的流程；區分研究資料與應用資料兩條流程 | [線性模型 protocol](model_dev_v1_protocol.md)、[樹模型 protocol](model_tree_v1_protocol.md)、[CSV 指引](../../CSV_IMPORT_GUIDE.md) | 模型機率尚未接入介面；相似產品功能、校準及最後測試仍屬計劃 |
| Data source | Steam March 2025 與 Google Play June 2021 的來源、平台、年份、範圍、授權和 target 意義；其他已審核來源為何沒有成為主樣本 | [來源可行性](../2026-10-05/dataset_feasibility_report.md)、[來源清單](../2026-10-05/dataset_inventory.csv)、[資料疑點](../2026-10-06/analysis_v1/data_questions.md) | owners 為來源估算區間；installs 為下界；不能當收入、精確銷量或跨平台相同 outcome |
| Data acquisition and processing approaches | 使用者下載的 Kaggle CSV、固定 revision 的 HF 輔助來源、hash／metadata；缺失、名稱、developer、price、software scope、標籤及排除 ledger；更新資料的指定格式驗證 | [候選清理](../2026-10-06/cleaning_candidate_v1/cleaning_report.md)、[資料字典](../2026-10-06/cleaning_candidate_v1/data_dictionary.md)、[固定分析規則](../2026-10-06/analysis_v1/analysis_protocol.md)、[匯入驗證](../2026-10-10/csv_import_v1/verification_notes.md) | 不描述成自行爬取整個市場；HF 已下載資料不等於主模型使用的資料；任意 CSV 不保證可直接匯入 |
| Data storage | raw／interim／processed 的用途、features 與 labels/splits 分檔、Parquet、manifest／SHA-256、模型及 OOF 保存；獨立 application snapshots、active registry、切回舊版本 | [Program README](../../README.md)、[CSV 指引](../../CSV_IMPORT_GUIDE.md)、`src/imports/repository.py`、各日期資料夾的 manifest | 大型原始資料與生成模型保留本機、Git 忽略；應用版本切換不會更新研究模型；首版為單程序本機系統 |
| Data analysis approaches | train-only EDA；class-prior、age-only、Logistic Regression、Random Forest；P／P+A／PC 無價格；developer group folds、fold 內編碼、有限參數搜尋；固定參數的年齡／cohort 重訓、同樣本比較及 Android 四級／合併三級；macro-F1 等指標及支持量 | [EDA](../2026-10-07/train_eda_v1/eda_notes.md)、[線性結果](../2026-10-07/model_dev_v1/results_notes.md)、[樹模型 protocol](model_tree_v1_protocol.md)、[年齡重訓結果](../2026-10-11/model_age_v1/results_notes.md)、[cohort／target 方法](model_scope_v1_protocol.md)、[cohort／target 結果](../2026-10-13/model_scope_v1/results_notes.md) | 開發 CV 曾用於調參，不能當最終性能；年齡、價格／軟件／例外及四級敏感度均完成；群組／random 對照、校準及最終 test 仍未完成 |
| Data visualization | 兩組規劃條件、樣本數／分級比例、重疊、來源年份／版本、空／小樣本提示、匯出一致性；視覺表達怎樣支援指定使用者任務 | [原型指引](../../DEMO_GUIDE.md)、[原型驗證](../2026-10-07/demo_v1/verification_notes.md)、[匯入及版本 UI 驗證](../2026-10-10/csv_import_v1/verification_notes.md)、`src/demo/static/` | 工程／瀏覽器測試不是使用者研究；尚未證明可提升獨立開發者的決策質素 |

## 方法數值核對

- 主分析 cohort：PC 73,527；Android 318,300。Train／calibration／test：PC 51,152／11,435／10,940；Android 221,806／48,297／48,197。
- Train 內固定三個 developer-group folds，seed 42；不為類別分布重新抽樣。P+A 多加入觀察年齡，不是統一追蹤期或新遊戲未來成功預測。
- 線性實驗：26 組設定／78 次擬合，含基準。樹模型：20 組／60 次，已完成並獨立核對 2,388,272 筆預測，見 [結果與限制](../2026-10-10/model_tree_v1/results_notes.md)。完成證據以對應 `run_manifest.json`、`verification.json` 為準，不能只憑程式檔存在判定完成。
- 年齡重訓：28 組模型／年齡條件、84 次擬合，已獨立核對。≥180／365 日分別保留 PC 45,734／40,814、Android 196,917／168,083 筆 train；原模型與重訓模型必須在同一批 validation IDs 上比較，不拿不同母體的分數差當成訓練效果。參數來自主 train CV，沒有重新調參。
- Cohort／target 敏感度：30 組／90 次固定參數擬合，獨立核對完成。Steam 放寬價格 55,775、納入 software-only 51,621、移除例外 51,151 筆；Android 四級維持原 221,806 筆。Steam 對照使用共同 validation IDs；Android 先加總兩個高級機率再 argmax，與原三級模型比較。四級與三級 macro-F1／log loss／Brier 不直接比較。
- 主比較為三折 macro-F1 等權平均；fold SD 是折間差異，並非 confidence interval。另報逐類指標、混淆矩陣、balanced accuracy、accuracy、log loss、multiclass Brier；Brier 定義為每筆所有目標類別（三級或四級）的平方誤差相加後取平均。
- Android train：免費 215,952、付費 5,850、Free 未知 4。逐組報支持量；未知組太小，不作穩定性能結論。
- CSV 匯入版本用於描述比較，未包含完整模型輸入契約或自動重訓。

## 寫作安排

課堂對照補充（2026-10-11）：[三科方法對照](course_to_fyp_review_2026-10-11.md) 可協助自己解釋 preprocessing、統計假設、CV 和 visualization 的學習基礎；它不取代學術文獻。新增 [Power BI 任務](powerbi_handoff_v1.md) 及已驗證的 train CSV 匯出（`src/analysis/export_powerbi_v1.py`、`verify_powerbi_v1.py`），可作 Data storage／visualization 的介面證據。現在尚未有完成的 PBIX、DAX 執行驗證或使用者測試，不把操作計劃寫成完成成果；原 app 與研究評估維持原流程。

1. Method 交代研究設計及評估理由；Proposed method 交代具體流程，避免兩節重複同一段。
2. 已實作的處理規則可寫為實際方法；尚未執行的穩健性、校準、test、使用者研究明確列為 planned work。
3. 方法章交代為何及如何比較；主要模型分數、差異、失敗／限制的分析放在 Results／Discussion，依導師要求調整。
4. 外部資料及方法引用使用正式 dataset／paper／官方文件來源；本索引用來查證實作，不取代 bibliography。`chapter1_verified_references_2026-10-08.md` 記錄的是已核對出版資料，不表示所有全文已讀完。
5. 需要流程圖時，至少清楚分開「固定研究資料 → CV／後续 calibration/test」與「新 CSV → 驗證 → 應用版本 → 描述比較」；不可畫成匯入後自動訓練／部署。
