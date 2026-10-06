# 候選資料清理 v1 — 2026-10-06

工作筆記，不是提交用論文章節；尚未定案研究問題或 target，也未開始模型訓練。

## 中斷檢查

上次的可行性審核與研究設計診斷已完成，輸出及 passed manifest 已在 2026-10-05 目錄，檢查時沒有仍在執行的 Python / uv 工作。本次接續候選清理，不重做已完成的審核，不覆寫上次的數字。

## 此次完成

- 可重跑清理程式、版本設定及資料字典；產物放在 `data/interim/cleaning_candidate_v1/`。
- 每個輸入 app_id 都有篩選 ledger；排除原因與獨立旗標分開統計。
- 保留 `None` / `NULL` / `none` 等字面名稱，標記待核對，避免通用 missing-token 規則造成資料損失。
- 不把 owners `0 - 0` 當作商業失敗；非 USD Mobile 價格保持未知；軟件類產品保留並標記。
- 5 個回歸測試通過；以 SQL 獨立重算**每列** cohort eligibility、標籤及 age，與 Python 產物一致；輸入、程式、設定、產物雜湊檢查通過。

| 平台 | 審核輸入 | 基本候選 cohort | 可用候選標籤 | cohort 內無標籤 | 排除 |
|---|---:|---:|---:|---:|---:|
| PC / Steam | 94,948 | 89,453 | 81,158 | 8,295 | 5,495 |
| Android | 328,513 | 318,300 | 318,300 | 0 | 10,213 |

PC 的互斥排除流程：名稱缺失 2 筆、再排除 genres 不可用 5,440 筆、再排除名稱含 demo / playtest 53 筆。Android 的 10,213 筆排除均因 release 不可用；81 筆 installs 不可用記錄亦在此排除集合內，不能重複相加。

## 與上一輪數字的差別

PC 基本 cohort 比 89,450 多 3 筆，因為保留了名稱 `none` 的 AppID 339860、385020、398970。其中 2 筆有 owners 標籤，所以可用標籤由 81,156 變成 **81,158**。保留不等於確認其名稱正確，仍可人工核對。

Android 比 318,298 多 2 筆：`com.DN.None` 和 `com.Tomkii.NULl`，均保留原名稱和原 installs，成為 **318,300** 筆。所有增量可於 `literal_title_review.csv` 查到。

| 候選 target | 分組列數 |
|---|---|
| PC O1 / O2 / O3 | 59,301 / 14,215 / 7,642 |
| PC owners 未知 | 8,295 |
| Android <1k / 1k–<100k / >=100k installs 下限 | 150,745 / 116,584 / 50,971 |

## 仍需處理

- PC 基本 cohort 有 1,033 筆僅含軟件類 genres（啟發式），未確定是否納入主要分析；另有 122 筆沒有 developer，可影響群組切分。
- Android 有 214 筆非 USD 或未知幣別，已保留記錄但 price_usd 設為缺失；沒有匯率換算。
- Android 有 **5 筆 Free 與原 price 不一致**，已列於 `mobile_free_price_review.csv`；尚未判定哪個欄位正確。相關分析必須先處理這些衝突，不能把原數值當作已核實的營利模式。
- PC owners 的選擇偏差、評論欄位互相矛盾、PC 日期僅為代理、Mobile 為 2021 歷史快照等上次限制仍存在。格式核對通過並未解決來源語義。
- PC demo / playtest 名稱規則可能誤排真實作品；ledger 保留每筆原因，待人工抽查再決定最終 cohort。

下一步是針對研究問題建立文獻對照表，核對這些邊界記錄及主要 target 定義，再定 feature allowlist 和 developer group split。導師對雙平台的回饋與下次交付日期仍未收到。本次沒有建立最終 cleaned data、train/test 切分、模型或應用框架。

## 重跑與核對

在 `Program` 目錄執行：

```powershell
uv run --locked python src/data/clean_candidates.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked python src/data/verify_clean_candidates.py
```

設定：`config/cleaning_candidate_v1.json`；欄位含義：[data_dictionary.md](data_dictionary.md)。`manifest.json` 是生成完成紀錄，其 independent_verification 欄提示另外執行核對；真正的核對結果在 `verification.json`，並記錄對應 manifest 雜湊。每次重新生成會清除舊的核對成功標記，避免中斷後誤用過期結果。

本次程式只讀取已審核的輸入 Parquet 並核對前後雜湊，沒有修改原始 Dataset 或下載檔，也沒有重新雜湊所有大型原始資料。這不是重新宣稱全量原始資料已再次審核。
