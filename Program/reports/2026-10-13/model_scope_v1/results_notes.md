# Cohort／target 敏感度：結果與限制

日期：2026-10-13。30 組模型／條件、90 次擬合完成，獨立驗證及完成後續跑檢查全部通過。這是研究工作紀錄及學生寫作的證據索引，不是提交用的章節正文。

## 實驗回答甚麼

延續年齡限制重訓，本輪檢查 Steam 的價格、software scope、人工保留例外，以及 Android 四級安裝量定義。沿用既有 developer groups／train folds 及先前選定的模型參數，每折重新擬合前處理與模型。沒有重新調參。設定見 [protocol](../../planning/model_scope_v1_protocol.md)。

P 表示規劃可描述的歷史快照屬性；P+A 加入觀察年齡；P_without_price 為 Steam 移除觀察價格的對照。以下主比較均為三折 macro-F1 等權平均；子組及逐類召回率則使用合併的 OOF 預測。不同定義的數值不可混用。

## 樣本範圍

| 平台／條件 | Train 筆數 | 相對原主 cohort | Developer groups |
|---|---:|---|---:|
| Steam 放寬價格 | 55,775 | 加入 4,623 筆；仍排除 software-only | 32,954 |
| Steam 納入 software-only | 51,621 | 加入 469 筆；仍要求觀察價格 >0 | 30,391 |
| Steam 移除 demo 例外 | 51,151 | 刪除 app_id 1129080 一筆 | 30,136 |
| Android 四級 | 221,806 | 原 train IDs／特徵完全不變，只拆分最高級 | 91,721 |

Steam 的 train ledger 共 62,289 筆，其中 5,854 筆 target 未知、133 筆 developer 未知；這些排除原因可能重疊，不能直接相加作流程總數。放寬價格仍要求已知 target／developer；不是把未知 outcomes 補成零。這個已知標籤樣本不能代表免費與付費遊戲的完整市場，先前發現的零價格／未知 owners 關聯仍然存在。software-only 是歷史欄位上的 heuristic，並非已核實的產品分類。

移除例外只改變樣本資格，沒有重建 developer graph，也沒有移除它在原分組形成時的連接作用。四個條件均未使用 calibration／test 作性能評估。

## Steam：完整新範圍的結果

| 條件 | 特徵 | Logistic Regression | Random Forest |
|---|---|---:|---:|
| 放寬價格 | P | 0.4615 | 0.4615 |
| 放寬價格 | P+A | 0.4997 | 0.5180 |
| 放寬價格 | P_without_price | 0.4576 | 0.4529 |
| 納入 software-only | P | 0.4398 | 0.4469 |
| 納入 software-only | P+A | 0.4845 | 0.5058 |
| 納入 software-only | P_without_price | 0.4358 | 0.4372 |
| 移除 demo 例外 | P | 0.4398 | 0.4477 |
| 移除 demo 例外 | P+A | 0.4845 | 0.5068 |
| 移除 demo 例外 | P_without_price | 0.4361 | 0.4362 |

此表的樣本範圍不同，不能把新總分減去原主 cohort 總分當成重新訓練的效果。放寬價格的 P 兩家族幾乎相同（未四捨五入差約 0.000016），無價格對照則由線性模型較高；不能概括為樹模型在所有條件都較好。

### 同一批原主 cohort 遊戲上的比較

下表是新模型分數減去原模型分數，兩者均只在完全相同的 validation IDs 計分。前兩組共 51,152 筆；移除例外為 51,151 筆。

| 條件 | 特徵 | 線性模型差值 | 樹模型差值 |
|---|---|---:|---:|
| 放寬價格 | P | +0.010159 | +0.001418 |
| 放寬價格 | P+A | +0.009329 | +0.002192 |
| 放寬價格 | P_without_price | +0.010959 | +0.002899 |
| 納入 software-only | P | −0.000528 | +0.001494 |
| 納入 software-only | P+A | −0.000250 | +0.000404 |
| 納入 software-only | P_without_price | −0.000748 | +0.000525 |
| 移除 demo 例外 | P | −0.000264 | +0.001904 |
| 移除 demo 例外 | P+A | −0.000010 | +0.000583 |
| 移除 demo 例外 | P_without_price | −0.000129 | −0.000570 |

放寬價格後，P 線性模型在共同樣本上的分數為 0.4502，樹模型為 0.4473；原模型在這批樣本則為 0.4401／0.4458。家族排序會隨訓練範圍改變。P+A 的樹模型在共同樣本為 0.5084，相對原本 0.5062 的改善遠小於完整擴大範圍總分表面上的差距。

納入軟件及移除一筆例外造成的整體差值較小，但不能由此斷言沒有任何子組影響。新增 469 筆 software-only 的 P+A pooled macro-F1 為線性 0.4388、樹模型 0.3736；新增樣本沒有原模型的對應 OOF，不能聲稱它們的性能「改善」了。移除例外時，fold 0 的訓練 IDs 完全不變，八個模型的共同驗證預測亦在浮點精度內重現原結果；另兩折會少一筆訓練資料，Random Forest 的 bootstrap／分裂可能隨之改變。

## Android：四級與可比較的三級結果

四級為 <1k、[1k,100k)、[100k,1m)、≥1m，支持量分別為 103,908、81,403、23,366、13,129。來源仍是安裝量下界，不是精確安裝次數。

「合併三級」先相加四級模型的兩個高級機率，再重新 argmax。不是直接把已選出的類別名稱合併。四級 macro-F1 與三級 macro-F1 的平均類別集合不同，不能直接比較高低。

| 模型／特徵 | 四級 macro-F1 | 合併三級 | 原三級模型 | 合併後減原三級 |
|---|---:|---:|---:|---:|
| Class-prior | 0.1595 | 0.2127 | 0.2127 | 0.000000 |
| Age-only LR | 0.2539 | 0.2445 | 0.3697 | −0.125238 |
| LR P | 0.2999 | 0.4745 | 0.4758 | −0.001279 |
| LR P+A | 0.3784 | 0.5316 | 0.5322 | −0.000568 |
| RF P | 0.2907 | 0.4769 | 0.4785 | −0.001607 |
| RF P+A | 0.3688 | 0.5373 | 0.5376 | −0.000325 |

四級模式中，P 與 P+A 均是線性模型較高；合併回三級時則是樹模型較高。主要 P／P+A 模型合併後接近原三級結果，不能據此認定細分高級的預測可靠。

Age-only 是明顯例外：其合併後分數大幅下降。該設定使用 balanced class weights；把原最高級拆成兩級，亦令兩級合計的平衡訓練權重由原三分之一變成二分之一。這是目標及損失權重結構改變的合理解釋之一，並非已隔離驗證的唯一原因。不能把「合併機率」當成重新訓練三級模型的數學等價操作。

### 高安裝量兩級的 pooled recall

| P+A 模型 | [100k,1m) recall | ≥1m recall |
|---|---:|---:|
| Logistic Regression | 4.76%（1,112／23,366） | 16.44%（2,158／13,129） |
| Random Forest | 3.90%（912／23,366） | 11.97%（1,572／13,129） |

兩模型把高級遊戲主要判入第二級，細分類別的辨識能力不足。此輪固定的是原三級實驗選出的參數，不代表已找出最好的四級模型，也不代表四級分類在任何方法下都不可行。這個證據支持目前保留三級主分析，四級留作敏感度結果；沒有把新門檻寫入 app 或 Power BI。

免費／付費另報：P+A 四級 pooled macro-F1，線性為免費 0.3784／付費 0.3103，樹模型為 0.3686／0.3234。付費組只有 5,850 筆，免費有 215,952 筆；Free 未知 4 筆不作穩定性能解讀。合併回三級的付費組，線性 0.4250 對原 0.4228，樹模型 0.4456 對原 0.4455；總體微降並不表示每一子組均下降。

## 實作與證據

- 新程式：`src/models/scope_data_v1.py`、`run_scope_sensitivity.py`；新設定 `config/model_scope_v1.json`。四個 train-only 資料檔及 90 組模型／預測／metadata 保存在 Git 忽略的 `data/processed/model_scope_v1/`。
- 48 項測試通過；新測試包含確切分級邊界、無效安裝量、合併後 winning class 改變、absent-class macro-F1、cohort masks 及共同樣本匹配。見 `unit_test_summary.json`。
- 90 次模型擬合沒有 convergence warnings，也沒有使用預設允許的一次 retry。極小子組缺少真實類別時，sklearn balanced accuracy 可發出提示；另以獨立算術核對，並保留 classes_present 及固定類別的 macro-F1。
- `run_manifest.json`／`preprocessing_audit.json` 記錄來源、設定、逐折 IDs、前處理、模型和輸出 hashes。`cohort_counts.csv`／`cohort_class_support.csv`／`metadata_coverage.csv` 記錄樣本與特徵覆蓋。
- `fold_metrics.csv`／`cv_summary.csv`／`pooled_oof_metrics.csv` 保存五種指標；`per_class.csv`／`confusion_matrices.csv` 保存逐類結果；`matched_comparison.csv`／`family_comparison.csv`／`subgroups.csv` 保存上述比較。
- [獨立驗證](verification.json)：重建及逐欄比較 6,180,936 個資料格；核對 2,599,212 筆新預測、2,558,476 筆匹配原模型預測、1,080 筆保存模型重播，以及全部 342 個子組紀錄。包含各折、pooled、逐類、混淆矩陣、子組和差值的獨立 NumPy 算術核對，以及 train-only membership、fit-only 前處理與固定模型設定。
- [工程驗證](engineering_checks.json)：完成後重跑跳過全部 90 次擬合，274 個實驗資料／模型檔、12 個彙總輸出與 run manifest 的 SHA-256 及修改時間均不變。[舊檔完整性](frozen_integrity.json) 同時核對先前 666 個模型產物、分析資料／依賴及 29 個保護檔；Power BI CSV、app 資料／程式與學生 DOCX 保持原有 hash。

## 下一步與解讀限制

本輪完成剩餘預定的 cohort／target 敏感度。接著另行預先訂定 developer-group 與隨機切分對照，檢查評估方式對結果的影響；其後才凍結最終模型／樣本／目標選擇，執行 full-train refit、calibration 及最後 test。原三級主分析、Power BI CSV 和產品行為目前維持原規格。

開發 CV 曾用於參數選擇，也重複用於這些敏感度比較；以上不是獨立最終成績。Fold SD 是折間變化，不是 confidence interval；沒有顯著性結論。Steam 價格單位、歷史快照、平台年份不同、developer 名稱歸組的不確定性，以及規劃屬性未經驗證為上市前已知等限制仍然存在。這些模型研究不證明能提高實際開發收益或預測新遊戲成功。
