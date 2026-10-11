# 年齡限制重新訓練：結果與限制

日期：2026-10-11。28 組模型／年齡條件、84 次固定分組擬合已完成，續跑及獨立研究核對全部通過。這是研究工作紀錄，不是可直接提交的報告正文。

## 這次回答的問題

上一輪只把既有 OOF 預測按年齡分組；這次在每個訓練折也排除未達 180／365 日的遊戲，重新擬合前處理及模型。然後把新舊模型放在**完全相同的、符合年齡條件的 validation IDs**上比較，避免把驗證樣本改變誤當成訓練改善。

沿用 analysis_v1 的 train、developer groups、folds、特徵與標籤。保留原主 cohort CV 選出的參數，不重新調參，也不按本輪結果重選最終模型。兩平台均包含 class-prior、age-only、P／P+A 的線性與樹模型；Steam 另有 P_without_price。詳見 [預先固定的 protocol](../../planning/model_age_v1_protocol.md)。

## 樣本及覆蓋

| 平台／最低觀察年齡 | 原 train | 保留 | 排除 | 保留 developer groups |
|---|---:|---:|---:|---:|
| Steam ≥180 日 | 51,152 | 45,734 | 5,418 | 26,894 |
| Steam ≥365 日 | 51,152 | 40,814 | 10,338 | 23,859 |
| Android ≥180 日 | 221,806 | 196,917 | 24,889 | 82,378 |
| Android ≥365 日 | 221,806 | 168,083 | 53,723 | 69,946 |

本輪四個 cohort 沒有缺失 age；排除均因未達門檻。365 日樣本包含在 180 日樣本內，兩者不是獨立資料集。保留原群組分配，不因刪掉部分遊戲而重新切分；developer groups 仍是資料標籤，不是已完成公司實體解析的結果。

## 重新訓練後的家族比較

數值為三折 **macro-F1 等權平均**，不是 accuracy 或最終 test 成績。P 是規劃可描述的歷史快照屬性，P+A 加入觀察年齡。

| 平台／年齡 | 特徵 | Logistic Regression | Random Forest | 樹－線性 |
|---|---|---:|---:|---:|
| Steam ≥180 日 | P | 0.4493 | 0.4563 | +0.0070 |
| Steam ≥180 日 | P+A | 0.4846 | 0.5047 | +0.0201 |
| Steam ≥180 日 | P_without_price | 0.4463 | 0.4467 | +0.0004 |
| Steam ≥365 日 | P | 0.4545 | 0.4598 | +0.0053 |
| Steam ≥365 日 | P+A | 0.4863 | 0.5088 | +0.0225 |
| Steam ≥365 日 | P_without_price | 0.4515 | 0.4552 | +0.0037 |
| Android ≥180 日 | P | 0.4873 | 0.4823 | −0.0051 |
| Android ≥180 日 | P+A | 0.5351 | 0.5396 | +0.0045 |
| Android ≥365 日 | P | 0.4943 | 0.4953 | +0.0010 |
| Android ≥365 日 | P+A | 0.5414 | 0.5465 | +0.0051 |

**重要觀察：**Android ≥180 日的 P 設定，重新訓練後由線性模型較高；原主 cohort 模型在相同 validation rows 上，樹模型則稍高（0.4759 對 0.4737）。因此不能概括為樹模型在所有樣本範圍均較好。Android ≥365 日 P 的家族差值只有約 0.0010，亦不足以單靠分數決定複雜模型較值得部署。

Steam P+A 的樹模型優勢在兩個年齡限制下仍存在，但其相對線性模型的差距會改變。Steam 無價格對照的增益較小；本輪沒有解決原始 PC 價格單位疑點。

## 重新訓練本身帶來甚麼變化

這裡的「原模型」也只在相同年齡合資格 validation rows 上計分，不能拿原本全 cohort 的分數來代替。

- Steam ≥365 日 P+A：線性模型 0.4608 → 0.4863（+0.0255）；樹模型 0.5083 → 0.5088（+0.0005）。重新訓練主要縮小了兩類模型的差距，並非兩者同幅度提升。
- Steam ≥180 日 P+A：線性模型 +0.0122；樹模型 −0.0022。限制年齡並不保證每個模型都改善。
- Android ≥365 日 P：線性模型 0.4702 → 0.4943（+0.0240）；樹模型 0.4720 → 0.4953（+0.0233）。這是在相同 validation rows 下改變 fitting population 的開發比較。
- Class-prior 的 macro-F1 沒有改變，因為擬合後仍預測同一個多數類別；各折的機率已按限制後樣本重新估計，所以 log loss／Brier 仍需另看。Age-only 基準亦已重新訓練，保存在完整表內。

所有 28 組的新舊比較及五種指標見 `matched_comparison.csv`；全部逐折、pooled、逐類及混淆矩陣也有保存。

## Android 付費子組仍須分開看

下表為 P+A 的**合併 OOF 固定三類 macro-F1**，與上方等權平均折分數的計算方式不同。

| 年齡／子組 | 樣本數 | 原線性 | 重訓線性 | 原樹模型 | 重訓樹模型 |
|---|---:|---:|---:|---:|---:|
| ≥180 日／免費 | 191,144 | 0.5336 | 0.5352 | 0.5372 | 0.5390 |
| ≥180 日／付費 | 5,769 | 0.4220 | 0.4278 | 0.4450 | 0.4449 |
| ≥365 日／免費 | 162,707 | 0.5373 | 0.5416 | 0.5411 | 0.5459 |
| ≥365 日／付費 | 5,372 | 0.4185 | 0.4263 | 0.4404 | 0.4385 |

樹模型在免費組改善，但付費組沒有跟隨改善；365 日付費組略降。兩組支持量及類別組成不同，不能只報整體平均。兩個年齡條件下 Free 未知均只有 4 筆，不作穩定性能解讀；完整支持量和所有基準／模型子組見 `mobile_subgroups.csv`。

## 完成範圍與限制

這完成 analysis_v1 sensitivity registry 中「兩平台 ≥180／365 日」的**固定參數重新訓練**部分；不是重新搜尋這些子集的最佳模型。原參數是在包含這些樣本的主 train CV 上選出，因此本輪仍非獨立性能估計。折間 SD 只表示折間差異，沒有顯著性或 confidence interval 主張。

年齡限制同時改變產品批次、標籤組成及資料支持範圍；不能推論遊戲年齡、功能或價格的因果效果。歷史 snapshot 也不會因重訓變成真正的 pre-release 特徵或固定一年預測期。主研究 cohort、split 及應用資料版本保持原位；本實驗不自動更改主分析範圍或部署模型。

仍待完成：Steam 較廣價格／software／demo cohort 檢查、Android 四級 target、群組／random 對照，之後才固定最終選型、全 train 擬合、校準、最後 test。相似遊戲參考、模型輸入與版本相容性、實際使用者評估也未完成。

## 重現及檔案

42 項單元／整合測試通過。獨立核對新模型 2,882,384 筆預測及原模型 2,882,384 筆匹配預測（同一遊戲可重複出現在不同模型／年齡條件），重播 1,008 筆模型輸出，並核對全部 84 個 folds、72 列 Android 子組、成員／群組隔離、fit-only 前處理與設定、匹配差值及所有指標。完成後重跑跳過 84 次擬合，252 個產物、11 個統計輸出及 run manifest 的 hash 均保持不變。Calibration／test 沒有作性能評估。

- `config/model_age_v1.json`：精確候選、年齡門檻及比較規則。
- `cohort_counts.csv`、`cohort_class_support.csv`：保留／排除、群組及各折類別支持量。
- `fold_metrics.csv`、`cv_summary.csv`、`matched_comparison.csv`、`family_comparison.csv`：兩種模式的逐折、平均及匹配差值。
- `pooled_oof_metrics.csv`、`per_class.csv`、`confusion_matrices.csv`、`mobile_subgroups.csv`：各層級結果，不只保存較高分設定。
- `preprocessing_audit.json`、`run_manifest.json`：84 次擬合的成員／參數／轉換及依賴、產物 hash。
- `verification.json`、`engineering_checks.json`：獨立核對、42 項工程測試、完成後重跑跳過 84 次擬合及 hash 保持不變的證據。
- `data/processed/model_age_v1/`：84 套模型、預測和完成標記，共 252 檔，約 228 MiB，Git 忽略；是重現證據，不是需清除的快取。

全部擬合沒有收斂重試或警告。記錄的 fold 工作時間合計約 13.0 分鐘，包括編碼、擬合、預測、coverage、計分及保存；不包含完整流程的前置檢查、彙整及獨立驗證，不能當作整個流程牆鐘時間。

```powershell
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/run_age_sensitivity.py
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/verify_age_sensitivity.py
```

沿用原鎖定模型環境，沒有新增依賴。Chapter 2 可引用本輪方法及核對證據來解釋敏感度設計；主要分數適合留待 Results／Discussion。學生自行撰寫，完整七項素材見 [Chapter 2 索引](../../planning/chapter2_evidence_map.md)。
