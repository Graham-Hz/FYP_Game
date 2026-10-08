# FYP_v1：Chapter 1 與 repository 核對

核對日期：2026-10-08（Asia/Hong_Kong）。這是修改工作清單，不是提交用報告正文。

原稿：`../FYP_v1.docx`。SHA-256：`818b2fd0924308c52310dfae80e6994ed3bc49c48b8dde741923c19778150434`。本輪沒有修改 Word；只核對文字、程式、已保存的實驗紀錄及文獻資料，沒有重新訓練，也沒有完成 Word 排版驗收。以下以段落開首定位，避免把 XML 段落序號當成頁碼。

**總評：Chapter 1 方向正確，已有實質 related work 和 significance，不需要推倒重寫。主要缺口是 CSV 更新範圍、完整 References、引用版本，以及文末過時的內部提示。**

## 1. Steam + Android 範圍

- **Confirmed**：兩平台仍是目前工作範圍；目標使用者是獨立遊戲開發者／小型工作室，支援早期規劃。工作題目是 *A Data-Driven Decision Support System for Early-Stage Game Development Planning*。
- **Unknown / not yet confirmed**：沒有找到導師批准兩平台或正式批准題目的紀錄。學生同意方向不等於導師批准。
- **Needs report update**：保留 Introduction 的 “The current working scope considers Steam and Android game data.”；不要改成已获批准。題目已有工作版本，文末 “Project title: unknown…” 過時。

## 2. Demo 真正做到甚麼

**Confirmed**：`../../src/demo/server.py` 及 `../../src/demo/static/` 已有本機比較原型；`../../DEMO_GUIDE.md` 有操作說明。

- Steam genre／功能篩選；Android category／Free／ads／IAP 篩選。
- 兩組條件比較：樣本數、outcome 分級分布、重疊數、少量／零結果提示。
- JSON 匯出包含條件、結果及來源版本資訊。
- 只讀固定 train 資料：PC 51,152、Mobile 221,806；不是全 cohort。

**尚未完成**：CSV 上傳／驗證／匯入、資料版本切換／回復、模型接入、逐款具名相似遊戲推薦。程式中的 POST API 是 `/api/compare`，不能因有 POST 就當成支援上傳。


**Needs report update（可選）**：Introduction 可由學生補一句初步比較原型已存在。正文的 “aims to develop” 和 Objectives 的 “To develop” 仍可保留：它們描述整個專案目標，不是進度完成聲明。

## 3. 模型狀態

**Confirmed**：首輪模型開發已完成，共 26 組設定、78 次擬合，使用固定 train 的三折 developer-group CV。

- Class-prior／多數類別基準。
- 只用觀察年齡的 Logistic Regression。
- 規劃特徵 P、P 加觀察年齡 P+A 的 Logistic Regression。
- PC 另有移除價格的 P_without_price 對照。
- 前處理在每個訓練折內擬合；已保存模型、預測、逐類及子群結果。
- 已保存的獨立驗證通過：78 folds、3,207,146 筆預測及 936 筆模型重播。

證據：`../2026-10-07/model_dev_v1/run_manifest.json`、`verification.json`、`results_notes.md`；實作在 `../../src/models/`。

**Outdated**：文末 “no model fitted” 必須刪除／更正。

**未完成**：樹模型比較、完整穩健性分析、最終選模／全 train 重擬合、機率校準、最終 test 評估及部署。現有 CV 同時用於調參與比較，不是獨立最終成績；不能寫成已證明預測商業成功。

## 4. Dataset、樣本及 outcome

**Confirmed**：Chapter 1 的 Steam March 2025、Google Play June 2021，以及分平台分析的說法正確。

| 項目 | Steam / PC | Android / Mobile |
|---|---|---|
| 實际主資料來源 | Artemiy Ermilov，Kaggle `artermiloff/steam-games-dataset` | Gautham Prakash，Kaggle `gauthamp10/google-playstore-apps` |
| 本地原始檔 | `Dataset/Steam Games Dataset 2025/games_march2025_full.csv` | `Dataset/Google Play Store Apps/Google-Playstore.csv` |
| 原始總數 | 94,948 | 2,312,944（所有 apps，不是全都是遊戲） |
| 目前主分析 cohort | 73,527 | 318,300 |
| Train / calibration / test | 51,152 / 11,435 / 10,940 | 221,806 / 48,297 / 48,197 |
| Outcome | 來源的 estimated-owner intervals | Minimum Installs，下界而非精確安裝量 |

上表 Dataset 路徑相對於 `My_FYP/`。Steam 的 Hugging Face 下載檔和其他 cleaned CSV 並非目前主分析輸入。

方法章要交代：

- PC 廣義 base 89,454；依序互斥排除未知 owners 8,295、未知 developer 11、非正觀察價格 6,908、software-only heuristic 713，得到 73,527。不可把各規則独立命中數重複相加。
- PC 只限快照觀察價格 >0，不代表首發價格或終身付費狀態；軟件類別排除是啟發式。owners `0-0` 當作未知。價格幣別尚未核實，不能標成 USD。
- Mobile 保守納入 16 個遊戲類別，排除含意不清的 Sports；328,513 個候選遊戲中，10,213 缺少 release date，保留 318,300。
- Mobile 5 筆 Free／price 矛盾的 Free 設 unknown；214 筆非 USD／未知幣別的 USD price 保持缺失。
- PC 三級按來源 interval：O1 upper ≤20,000；O2 lower ≥20,000 且 upper ≤100,000；O3 lower ≥100,000。這是區間映射，不是精確 owners 邊界估計。
- Mobile 三級：M1 lower bound <1,000；M2 1,000 至 <100,000；M3 ≥100,000。
- Steam metadata 更新日為 2025-03-13；這是 age 計算代理日期，不是已證明每列都在同日採集。Google Play 的資料採集月份是 June 2021；Kaggle 版本更新日 June 17 不等於每列 scraped time。

本地證據：`../2026-10-06/analysis_v1/analysis_protocol.md`、`cohort_flow.csv`、`manifest.json`、`split_class_counts.csv`，以及 `../../data/raw/source_metadata/2026-10-05/` 的兩個 Kaggle metadata 檔。

**Needs report update**：Background 應補兩個資料來源引用，並簡短指出是經篩選的歷史樣本；目前 PC 正觀察價格的範圍可加短句，避免讓讀者以為覆蓋所有 Steam 遊戲。精確數量、分級邊界、排除流程及 split 放 Method/Data；不必塞進 Chapter 1。完整來源格式見同目錄 `chapter1_verified_references_2026-10-08.md`。

## 5. Outcome 的解讀

**Confirmed**：“The outcome measures also need careful interpretation…” 這段正確，應保留。Owners／install 下界不等於收入、利潤或開發者的商業成功；關聯不代表因果；兩平台不同年期、母體及標籤不能用來直接比較市場大小。

**Needs report update**：首段關於小型團隊取得市場資訊的困難，若當作普遍經驗事實，應補支持文獻／需求研究，或由學生收窄成專案動機。沒有證據可以新增「缺乏資源」「提升收入」「首次提出此系統」。也不要把 snapshot 屬性當成已保存的 pre-release 屬性。

## 6. 文獻與 References

**Confirmed**：正文已引用五項研究，不再只有 related-work placeholder，但未有正式 References section。文末 “Literature review evidence and citations were not supplied here” 不能繼續當作目前 repository 的描述。

- De Luisa et al. (2021)：期刊原文核實；首月玩家資料用於後續 popularity，與真正上市前預測不同。
- Kerim and Genç：2022 online publication；正式卷頁為 37, 543–557 (2025)。建議正文及 References 一致採用 **2025**。2022 不是憑空錯誤，但不要把 online 年份和 2025 卷頁混成未解釋的引用。
- Kapoor and Narayanan (2023)：Patterns 4(9), Article 100804；metadata 核實。
- Tintarev and Masthoff (2012)：UMUAI 22, 399–439；metadata 核實。
- **新發現／Needs report update**：Wardatzky et al. 不再只有 2024 預印本。已核實 **2025 ACM Transactions on Recommender Systems 3(4)** 版本，DOI `10.1145/3716394`。旧 matrix 實際閱讀的是 arXiv v1 (2024)。保留 2024 時必須明確引用 v1；改用正式出版版時，應核對所引用內容並改成 2025，不能只改年份冒充重讀。完整雙版本資料及出版者登錄來源見 references 工作檔。

**Needs report update**：“The design of the analysis…” 把兩篇 explanation 文獻合在一句，略為籠統。Tintarev／Masthoff 支持分開看決策效果與滿意度；Wardatzky 等人著重受試者特徵、代表性及可推廣性。應分清各自支援的論點，不能說它們驗證了我們的介面。

**Confirmed（檢索限制）**：repository 仍是 targeted 六篇 matrix；沒有新增並完成核實的直接 Android installs 實證研究。已有 Muhtasim／Hossen 候選，但平台、樣本與方法描述有疑點，不應採用其高準確率作比較標準。這不等於宣稱世上沒有 Android 研究。本輪是既有引用核對，沒有完成新的 Android 系統性搜尋。

## 7. Project significance

**Confirmed**：“Based on these points, the intended contribution…” 已有 significance。可以把「使用者能比較甚麼」提得更直接，不必再加一段重複內容。

以下是對你現有段落意思的兩句精簡編輯示例，供你修改現有文字；不是新增已驗證成效的聲明：

> The system aims to support early-stage planning by making historical game comparisons easier to inspect. It will show the sample sizes, outcome distributions and data limitations behind each comparison.

保留 aims／will，避免宣稱已證明提升決策品質。若要寫已完成的功能，應另外描述原型，不能把預期用途當成 user-study 結論。提交時按 handbook 保留 AI editing 披露，並由學生確認最後措辭。

## 8. 五項 Objectives

| Objective | 狀態／證據 | 措辭建議 |
|---|---|---|
| 1. 整理及驗證兩平台資料 | **Confirmed：當前研究快照已完成**；analysis_v1 protocol、manifest、verification | 保留；後續新 CSV 匯入驗證不是已完成成果 |
| 2. 分析屬性與 outcome 關聯 | **Confirmed：初步完成**；`../2026-10-07/train_eda_v1/`、模型結果 | 保留 historical relationships；深度解釋／混淆因素分析仍需進行 |
| 3. 比較分類與 baselines | **Confirmed：第一輪已完成，整體未完成**；model_dev_v1 三折 group CV | 保留；separate final test 是後續目標，不能說已完成 |
| 4. 整合決策支援程式 | **Needs report update**；已有比較 demo，學生已確認可更新資料的方向 | 加入 specified-format CSV import、validation 及 data-version management；結果匯出也可列入系統需求。避免承諾任意 CSV 自動理解 |
| 5. 可靠性與實際用途評估 | **Confirmed：部分完成**；功能測試、artifact verification、PC without-price 對照；尚無使用者研究 | 保留 “if feasible”；功能測試不等於已證明 practical usefulness |

## 9. 使用者評估

**Confirmed**：已有初步任務構想，見 `../2026-10-05/research_design/experiment_protocol_v1.md`：找可比作品、比較兩個構想、理解分級／樣本不足、識別不受支持的收入／因果說法；另有任務完成率、時間、理解正確率等建議。

**Unknown / not yet confirmed**：未找到已完成的 participant study、招募樣本數／名單、確定日程或收集到的使用者結果。方案仍需細化，例如把「找作品」任務與目前群組比較介面對齊。不能說完全沒有 evaluation plan，也不能說已完成 user validation。現有 “if feasible, a small user-task evaluation” 合適。

## 10. 系統技術

**Confirmed**：現有原型用 Python standard-library `ThreadingHTTPServer`、DuckDB、HTML/CSS/JavaScript，本機運行。

**Unknown / not yet confirmed**：最終應用框架未有已定案紀錄。不要寫成已選 Streamlit／Flask／React，也不要說完全沒有技術實作。Chapter 1 不必列框架；Methods/System Design 再交代。

## 11. RQ1–RQ4

四題仍有用途，見 `../2026-10-05/research_design/research_design_v1.md`。

| RQ | 現況及解讀 |
|---|---|
| RQ1：歷史屬性與 outcome 關係 | 對應 Objective 2；已有初步 EDA，但不能直接回答因果策略 |
| RQ2：未見 developer groups 的分類比較 | 對應 Objective 3；已有開發 CV，最終 test 未做；developer groups 是資料標籤分組，不是已完全核實公司實體 |
| RQ3：cohort／target／split 敏感度 | 對應 Objective 5；已有資料診斷與 without-price 對照，其餘仍待做 |
| RQ4：比較介面是否支持規劃與理解限制 | 對應 Objectives 4–5；已有功能可行性，沒有使用者成效結論 |

不自動加進 Chapter 1。建議在 Research Design／Methodology 逐題對應實驗與證據；若導師希望 Introduction 提研究問題，才在 objectives 附近加入精簡版本。CSV 可更新性屬系統需求／驗收，毋須為每項工程功能硬加新 RQ。

## 12. 按優先次序修改

1. **移走整段 Internal drafting notes**，另存工作筆記；特別是 unknown title、no model fitted、prototype 未確認、文獻未提供等過時提示。
2. **補正式 References 及兩個 dataset 引用**；統一 Kerim 年份；處理 Wardatzky 預印本／期刊版本。
3. **Objective 4 補指定格式 CSV、驗證及資料版本管理**，讓報告與已確認產品方向一致；不能描述成已完成。
4. **輕修 Background**：交代篩選樣本及 PC 價格範圍；分清兩篇 explanation 文獻的作用；保留 outcomes／因果限制。
5. **精簡 significance**；若保留小型工作室普遍困難的事實陳述，補證據或收窄措辭。
6. **最後更新目錄及章節編號**：文字抽取中的目錄未顯示 Objectives；請在 Word 更新整個目錄並檢查 1.1／1.2、頁碼、標題 “Table of Contents”。本輪未用排版預覽確認頁面外觀。

仍未知：導師批准、正式 deadline、最終框架、實際招募、系統效用證據。

暫不要放入 Chapter 1：完整清理流水帳、hash、CV 超參數／逐類分數、最終模型成果或不存在的用戶研究。數據與方法放 Method/Data，原型設計放 System Design，模型及使用者結果放 Results/Evaluation。

本次核對採用新實驗產物判斷目前進度；保留 10 月 5–6 日歷史文件原樣，避免改動凍結研究紀錄。文獻出版 metadata 的新發現另記下，未將其冒充原先已閱讀的版本。
