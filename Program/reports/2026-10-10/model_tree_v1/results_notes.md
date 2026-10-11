# 樹模型開發比較與分組診斷

日期：2026-10-10。20 組設定／60 次固定 train-group-CV 擬合完成，獨立核對與續跑檢查全部通過。本文件是研究工作紀錄，不是提交用的報告正文。

## 本輪完成的比較

兩平台分開建模，沿用原有 train、developer groups、三個 folds、特徵白名單及 fold 內前處理。新增 Random Forest；每個特徵集合只有四組預先寫明的設定，沒有根據結果擴大搜尋。設定理由、選擇及平手規則見 [protocol](../../planning/model_tree_v1_protocol.md)。原有線性模型、研究切分、來源資料和依賴鎖均保留。

以下是各家族在同一特徵集合內選出的**三折 macro-F1 等權平均**，不是 accuracy，也不是最終 test 成績。P 是規劃可描述的歷史快照屬性；P+A 再加觀察年齡。兩平台 outcome 不同，不直接比較其分數高低來判斷哪個市場較好。

| 平台／特徵 | Logistic Regression | Random Forest | 差值（樹－線性） | 樹模型折間 SD |
|---|---:|---:|---:|---:|
| Steam P | 0.4401 | 0.4458 | +0.0058 | 0.0030 |
| Steam P+A | 0.4845 | 0.5062 | +0.0217 | 0.0028 |
| Steam P_without_price | 0.4363 | 0.4368 | +0.0006 | 0.0026 |
| Android P | 0.4758 | 0.4785 | +0.0028 | 0.0023 |
| Android P+A | 0.5322 | 0.5376 | +0.0054 | 0.0064 |

Steam 三個特徵集合均選出 balanced、最多 256 leaves；Android P 選出 unweighted／256 leaves，P+A 選出 unweighted／1,024 leaves。其他固定參數為 100 trees、max_depth=20、min_samples_leaf=20、sqrt feature sampling、bootstrap、seed 42、兩個 workers。這是開發階段的家族內選擇，不是最終部署決定。部分 leaf 上限設定得出相同分數；在既定深度、最小葉樣本等限制下，放寬上限未必改變分類結果，沒有為追求較高分而追加搜尋。

目前較明顯的觀察是 Steam P+A 的增益；Steam 無價格及 Android P 的增益很小。CV 被用於選擇設定，再用來比較選中設定，不能把表中的差值或折間 SD 當成顯著性證明／獨立測試／信賴區間。價格對照也不能證明定價具有因果效果或已解決 PC 價格單位疑點。

## 整體分數掩蓋的限制

以下為選中配置的**合併 OOF 子組 macro-F1**，不是上表的平均折分數；固定三類計算。

| Android 特徵／子組 | 樣本數 | 線性模型 | 樹模型 |
|---|---:|---:|---:|
| P／免費 | 215,952 | 0.4758 | 0.4785 |
| P／付費 | 5,850 | 0.3957 | 0.3930 |
| P+A／免費 | 215,952 | 0.5324 | 0.5373 |
| P+A／付費 | 5,850 | 0.4228 | 0.4455 |

Android P 的付費子組沒有跟隨整體小幅提升；P+A 付費組有改善，但仍低於免費組，且兩組類別組成不同。Free 未知僅 4 筆，保存於完整診斷表，不能解讀為穩定性能。

逐類結果也不足以支持直接部署：Steam P+A 樹模型的中間 owners tier F1 約 0.2919；高 tier precision 約 0.2980，recall 約 0.6598。Android P+A 的最高 install tier recall 約 0.3286。不能把輸出直接包裝成可靠的成功／營收機率。完整逐類指標、支持量與混淆矩陣另存 CSV。

## 年齡診斷做了甚麼

對**既有主 cohort 模型的 OOF 預測**，分別只取觀察年齡至少 180／365 日的紀錄；沒有在這些子組上重訓或重調參。

| 平台／P+A 子組 | 樣本數 | 線性 pooled macro-F1 | 樹 pooled macro-F1 |
|---|---:|---:|---:|
| Steam ≥180 日 | 45,734 | 0.4727 | 0.5071 |
| Steam ≥365 日 | 40,814 | 0.4612 | 0.5085 |
| Android ≥180 日 | 196,917 | 0.5334 | 0.5377 |
| Android ≥365 日 | 168,083 | 0.5371 | 0.5416 |

兩個年齡子組互相重疊；P 和 Steam 無價格的對照也保存在 `selected_oof_subgroups.csv`。這些結果不能取代 sensitivity registry 所列的年齡限制重新訓練，也不能證明固定上市後天數的前瞻預測能力。

## 檔案、驗證與重現

37 項單元／整合測試通過；獨立核對 2,388,272 筆 OOF 預測、720 筆儲存模型重播、60 個 fold 的成員／群組隔離、fit-fold 詞彙與數值統計、森林設定、全部指標及五列家族比較／32 列子組診斷。續跑實測跳過全部 60 次擬合；180 個產物及 10 個統計輸出 hash 均不變。研究 calibration／test 沒有作性能評估。

- `cv_summary.csv`／`fold_metrics.csv`：全部配置、逐折指標及工作時間；不是只保存較高分配置。
- `linear_tree_comparison.csv`：上述五組與原有線性模型的比較。
- `pooled_oof_metrics.csv`、`per_class.csv`、`confusion_matrices.csv`、`mobile_subgroups.csv`：整體、逐類及全部樹配置的 Android 子組。
- `selected_oof_subgroups.csv`：兩家族選中配置的 32 列年齡／免費／付費／未知子組診斷及支持量。
- `preprocessing_audit.json`、`development_choices.json`、`run_manifest.json`：前處理、選擇、輸入／程式／環境／產物 hash。
- `verification.json`、`engineering_checks.json`：獨立算術／成員／模型重播，以及工程測試／續跑的檢查結果；以實際 status 為準。
- `data/processed/model_tree_v1/`：60 組模型、預測及完成標記，共 180 檔，約 251 MiB，Git 忽略；這些是重現證據，不是無用快取。

各 fold 記錄的工作時間合計約 16.2 分鐘，包含該折前處理、擬合、預測、計分和模型保存；不等於整個流程的牆鐘時間，也不是純擬合 benchmark。未新增依賴或更改原本鎖定環境。

從 Program 目錄執行（可續用已完成且 hash 相符的 checkpoints）：

```powershell
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/run_tree_development.py
uv run --project experiments/model_dev_v1 --locked python.exe -B src/models/verify_tree_development.py
```

## 下一步與 Chapter 2 對應

下一個研究里程碑是預先固定並執行年齡限制重新訓練、剩餘 cohort／target 敏感度和群組／random 切分對照；沿用既定群組分配，不從不同 split 中挑最高分。之後才凍結最終選型、在全部 train 擬合、使用 calibration 校準及最後評估 test。類似遊戲參考、應用端模型契約／支援範圍和實際使用者評估亦未完成。

本輪可支持 Chapter 2 的 Method、Proposed method、Data analysis approaches 及 Data storage：有限搜尋、fold 內前處理、分组隔離、指標定義、檢查點與獨立核對。七項要求的完整素材索引見 [Chapter 2 evidence map](../../planning/chapter2_evidence_map.md)。學生自行撰寫方法章；主要分數及解釋適合留待 Results／Discussion，依導師格式調整。
