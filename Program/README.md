# FYP game planning dataset audit

此目錄包含資料可行性審核、研究設計及候選清理流程，沒有模型訓練或最終應用程式。結果是工作筆記，應由學生理解與核對後再作研究決定。

最新進度：[2026-10-06 候選清理報告](reports/2026-10-06/cleaning_candidate_v1/cleaning_report.md) 及 [資料字典](reports/2026-10-06/cleaning_candidate_v1/data_dictionary.md)。本輪修正字面名稱被當成缺失的問題；PC 基本 cohort 為 89,453 筆，其中 81,158 筆可用候選標籤；Android 318,300 筆。這些是尚待研究決定的候選資料，不是最終訓練集。

```powershell
uv run --locked python src/data/clean_candidates.py
uv run --locked python -m unittest discover -s tests -v
uv run --locked python src/data/verify_clean_candidates.py
```

主要報告：[2026-10-05 可行性報告](reports/2026-10-05/dataset_feasibility_report.md)。
預測目標：[target feasibility](reports/2026-10-05/target_feasibility.md)。

後續研究設計：[研究設計 v1](reports/2026-10-05/research_design/research_design_v1.md) 與 [實驗 protocol v1](reports/2026-10-05/research_design/experiment_protocol_v1.md)。
這一階段補充 owners／評論計數的一致性、類別分布、未知值選擇偏差與 cohort 敏感度；沒有訓練模型。診斷可重跑：

```powershell
uv run --locked python src/data/target_design_diagnostics.py
```

研究設計中的 81,156 個 PC 可用標籤及 318,298 筆 Mobile 記錄是上一輪參考 cohort。最新差異見上方候選清理報告；前一輪輸出保留作可追溯對照。正式清理仍需核對 PC 軟件產品、名稱篩選及 Mobile Free／price 衝突。

## 重跑

在 PowerShell 切換至 `F:\HKBU_Y4\FYP\Program` 後，逐項執行：

```powershell
uv sync --locked
uv run --locked python src/data/fetch_sources.py --date 2026-10-05 --download-steam
uv run --locked python src/data/validate_structure.py
uv run --locked python src/data/profile_datasets.py
uv run --locked python src/data/compare_and_targets.py
uv run --locked python src/data/build_reports.py
uv run --locked python src/data/verify_audit.py
```

使用 Python 3.14 與 `uv.lock` 的精確套件版本。`uv` 已存在於本機，環境放在此專案 `.venv`，不依賴 Windows 的 `python` alias。`requirements.txt` 是 lock 的匯出；以 uv.lock 為準。

`fetch_sources.py` 已保存本次來源 metadata 與固定的 Hugging Face revision。相同日期重跑會沿用 lock，下載只限 Steam Parquet 約 192 MB，並驗證 LFS SHA-256。RAWG 與 Steam Reviews 只保存 metadata；沒有下載幾十 GB 的評論。`--date` 是 metadata 保存日期，本審核程式的評估日期固定在 `audit_common.py` 的 `DATE`；新一輪審核需一致更新該日期，保留舊 reports。

正式全量重跑用上述指令。若先前執行因中斷而停止，可使用 `profile_datasets.py --resume` 跳過已完成的 profile；變更原始輸入或分析規則後不要使用 `--resume`，因為它不驗證既有結果是否符合新規則。`--only` 可指定資料集 key 作針對性重跑。完整 profiles 的合併會保留其他已存在的版本。

## 原始資料與產物

- `../Dataset/`：使用者原始 Kaggle 檔案，原位只讀，沒有更名、覆寫或修復原檔。
- `data/raw/existing_local_sources.json`：原始本地來源路徑、大小及 SHA-256。
- `data/raw/source_metadata/2026-10-05/`：metadata、固定 revision、dataset cards、匯出程式來源副本。
- `data/raw/huggingface/<revision>/steam.parquet`：固定版本的原始下載。
- `data/interim/`：審核用 Parquet；保留原記錄，只作欄位命名／序列化及明確的 Google 分類子集。不是最終 cleaned data。
- `data/interim/cleaning_candidate_v1/`：兩平台基本候選 cohort 與覆蓋每列輸入的 ledger；candidate 含 target，不可直接整表作模型特徵。
- `data/processed/`：保留作日後正式清理輸出，本次沒有寫入。
- `reports/2026-10-05/`：五份要求的輸出及支持證據。
- `reports/2026-10-06/cleaning_candidate_v1/`：候選清理規則影響、欄位字典、邊界記錄、manifest 及獨立核對結果。

資料 profile 以 DuckDB 4 GB 記憶體上限、2 threads 執行，可能使用暫存磁碟；Python、Arrow 及其他物件另需記憶體。大型推薦資料的逐列去重及唯一值計算需較長時間。所有 CSV row count、缺失與基數均是全量；本次未作隨機抽樣。日後模型／抽樣預定 seed 42，但未在本次使用。

## 五份主要輸出

| 檔案 | 內容 |
|---|---|
| `dataset_inventory.csv` | 每個本地／遠端資料檔的來源、授權、版本證據、大小、雜湊及審核程度 |
| `schema_comparison.csv` | 原始欄名、對應名稱、缺少／新增欄位、觀察型態及 HF 原生型態 |
| `data_quality_summary.csv` | 每欄缺失、空集合、唯一值、零值、無效值及表級重複紀錄 |
| `target_feasibility.md` | 候選 target、分布、洩漏、評估方式與未知 |
| `dataset_feasibility_report.md` | PC／Mobile 資料建議、限制及待確認事項 |

`schema_comparison.csv` 的 canonical mapping 僅處理明確名稱變體，不把 owners 自動改為 sales，不把 about_the_game 與 detailed_description 視為相同欄位。集合型欄位的字串差異不等於語義差異。

`data_quality_summary.csv` 中同一 table 的重複列／key 計數在每個欄位重複顯示，不應逐欄加總。未實作特定 domain rule 的欄位 invalid_count 留空。空集合與字串 null 分開，`-1` 為數值領域無效而非已證實缺失。金額幣別、時間窗口及代理指標意義仍需按照研究用途核對。

## 關鍵讀取決定

FronkonGames 原 CSV 表頭 `DiscountDLC count` 合併了兩個名稱。程式先用原作者 exporter 的欄位順序與本地 JSON 的所有共同 AppID、21 個純量欄位核實，再以額外欄名解讀原 CSV。若出現不一致便停止依此解讀。額外 JSON AppID 被計數保留，沒有假設兩個檔案行數相同。

Google Play 採 16 個明確遊戲標籤，Sports 另存：同一 Category 欄同時可能代表體育 App 或體育遊戲，缺少 genreId 不能可靠区分。實際保守樣本為 328,513 筆，Sports 歧義記錄 47,483 筆。名稱、日期及 target 可用性的進一步排除僅計算影響，不是定案清理。

來源原始說明與自動 metadata 分開保存；目前 remote 版本號不能冒充使用者當初下載的版本。所有學術主張仍需要原始來源與文獻佐證。
