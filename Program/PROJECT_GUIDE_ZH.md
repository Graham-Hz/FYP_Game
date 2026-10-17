# FYP 資料夾與程式導覽

核對日期：2026-10-17。這是理解專案、準備操作和回答老師問題的工作導覽，不是提交用報告正文。先理解輸入、處理、輸出和限制，再按需要打開程式；不需要背熟每個檔名。

目前已有資料處理、研究模型實驗、可匯入 CSV 的本機比較網站。網站目前顯示歷史樣本統計，尚未使用研究模型作預測。分析總覽、完整互動資料表、相似遊戲參考及最終模型評估仍有待完成。

## 1 從外層資料夾開始

以下位置相對於 `F:\HKBU_Y4\FYP`。

| 位置 | 用途 | 展示時是否需要打開 |
|---|---|---|
| `My_FYP/` | 你自己的專案 repository | 主要入口 |
| `others/` | 前輩 FYP 參考材料 | 說明參考來源時才需要，不是本系統輸入 |
| `Lecture Notes/` | 大學課程教材 | 解釋課堂方法與本專案的關係時使用 |
| `Handbook of Projects for the Final Year.pdf` | 報告及項目要求 | 查要求時使用 |
| `FYP_PROJECT_CONTEXT_FOR_CODEX.md` | 最初討論背景 | 歷史背景；目前進度以 `Program/PROJECT_STATUS.md` 為準 |
| `tmp/`、其他外層文件 | 工作目錄中的其他材料 | 本導覽未逐項核實其用途，不代表可以刪除 |

`My_FYP` 裡最重要的是 `Dataset/` 與 `Program/`：前者保存原始輸入，後者保存程式、生成資料、研究結果及報告。

## 2 Program 裡每類檔案做甚麼

| 位置 | 白話解釋 |
|---|---|
| [START_DEMO.cmd](START_DEMO.cmd) | 啟動目前的網站／Python 服務 |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | 網站操作及三分鐘示範 |
| [CSV_IMPORT_GUIDE.md](CSV_IMPORT_GUIDE.md) | 匯入 CSV 的格式、步驟和限制 |
| `src/` | 真正執行工作的程式碼，按職責分資料、模型、網站等 |
| `config/` | 固定規則與參數，例如納入條件、可用特徵、模型設定 |
| `data/` | 原始下載、處理中資料、固定研究資料、模型及應用版本 |
| `tests/` | 檢查程式在正常及錯誤情況下是否符合預期；不是模型的 test dataset |
| `reports/` | 統計結果、研究紀錄、驗證證據、你的 Word 報告及 Power BI 成果 |
| `notebooks/` | 可逐格閱讀／執行的教學示例；不是正式清理流程的入口 |
| `experiments/` | 模型及教學的獨立套件環境設定；主要模型程式仍在 `src/models/` |
| `pyproject.toml`、`uv.lock`、`requirements.txt` | 套件需求及版本紀錄；執行以 lock 鎖定版本 |
| `.venv/` | 已安裝的 Python 環境及套件，不是你逐個撰寫的原始碼 |
| `.gitignore` | 指定哪些本機檔案不放進 Git；不會自動刪除它們 |

`.git/` 位於 repository 層，保存 Git 版本歷史。`__pycache__/` 是 Python 自動產生的快取，與保留研究結果的 `data/processed/` 不同。

## 3 日常示範怎樣啟動

1. 在檔案總管開啟 `F:\HKBU_Y4\FYP\My_FYP\Program`。
2. 雙擊 [START_DEMO.cmd](START_DEMO.cmd)，保留啟動視窗。
3. 待資料核對及載入完成，瀏覽器開啟 `http://127.0.0.1:8765/`。
4. 選平台，設定 A、B 條件，按「比較歷史分布」，再試匯出結果。
5. 結束時在啟動視窗按 Ctrl+C。關閉瀏覽器分頁不等於停止服務。

啟動檔實際執行：

```powershell
uv run --locked python.exe src/demo/server.py --open
```

`uv` 管理環境並執行 Python；`--locked` 使用鎖定依賴；`server.py` 啟動本機服務；`--open` 開瀏覽器。這是本機網址，其他人不能靠這條網址瀏覽你的電腦。

網站啟動會檢查固定研究檔案、建立 DuckDB 記憶體資料表，讀入研究 train 資料；如之前已啟用另一個有效的匯入版本，會恢復該版本。沒有每次下載原始資料、重新清洗或訓練模型。

這台電腦已有所需資料。另一台電腦只有 Git clone 並不足夠，因為大型資料及生成檔案沒有跟隨 Git 上傳。環境、資料缺失、連接埠衝突等處理見 [操作指引](DEMO_GUIDE.md)。本輪核對了啟動檔及程式入口，沒有重新執行瀏覽器操作驗收。

## 4 原始資料如何成為研究資料

```text
Dataset 中的 Kaggle 原始資料
  ↓ 結構核對、欄位整理、缺失／重複／無效值盤點
data/interim 中的審核用 Parquet
  ↓ 解析日期、布林及集合；納入／排除規則；建立目標分級
data/interim/cleaning_candidate_v1
  ↓ 確定主分析範圍；選特徵；按開發者群組切分
data/processed/analysis_v1
  ├─ train → 統計分析、模型開發、原有網站版本、Power BI 匯出
  ├─ calibration → 留待最終模型的校準階段
  └─ test → 留待最終評估
```

主要輸入是 Steam 2025 年 3 月的 `Dataset/Steam Games Dataset 2025/games_march2025_full.csv`，以及 Google Play 2021 年 6 月的 `Dataset/Google Play Store Apps/Google-Playstore.csv`（路徑相對 My_FYP）。其他 Kaggle 資料和固定版本 Hugging Face Steam 資料用於來源審核／比較，不是全部合併為主模型資料。

Parquet 是適合程式分析的表格檔案格式，能保存欄位型別及集合，亦有壓縮；可以用 `pd.read_parquet(...)` 讀取。它不是另一份網上來源。

| 階段 | 主要程式（相對 Program） | 做甚麼／產生甚麼 |
|---|---|---|
| 取得來源 | [fetch_sources.py](src/data/fetch_sources.py) | 保存來源 metadata、下載固定 revision 的 HF Steam 資料；你原有 Kaggle 檔案已在 Dataset |
| 結構核對 | [validate_structure.py](src/data/validate_structure.py) | 核對 CSV 每列欄數、原檔 hash、特殊表頭解讀等 |
| 資料盤點 | [profile_datasets.py](src/data/profile_datasets.py) | 用 DuckDB 統計缺失、型別、重複、數值範圍等，產生審核用 Parquet；此時不是最終清理 |
| 候選清理 | [clean_candidates.py](src/data/clean_candidates.py) + [cleaning_rules.py](src/data/cleaning_rules.py) | 用 pandas 解析及套用清理規則；保存候選資料及每列處理理由 |
| 固定研究資料 | [freeze_analysis.py](src/data/freeze_analysis.py) | 套用主分析範圍、整理特徵，分開保存 features 和 labels/splits |
| 群組切分 | [group_splits.py](src/data/group_splits.py) | 按開發者群組分 train／calibration／test 及 train 內的 CV folds |
| 特徵限制 | [feature_policy.py](src/features/feature_policy.py) + [feature_policy_v1.json](config/feature_policy_v1.json) | 只允許指定欄位進模型，排除 target、安裝量、owners 等答案相關欄位 |
| 描述分析 | [profile_training.py](src/analysis/profile_training.py) | 產生 train 樣本分布、分組統計、缺失及遊戲年齡分析 |
| Power BI 匯出 | [export_powerbi_v1.py](src/analysis/export_powerbi_v1.py) | 把固定 train 資料匯出成 Power BI 使用的 CSV |

`compare_and_targets.py`、`target_design_diagnostics.py`、`review_analysis_questions.py` 是來源比較及研究疑點診斷；`build_reports.py` 整理審核報告。它們不是每天開網站必須重新跑的步驟。完整重現方法見 [README](README.md)，不要為了展示而重跑全部清理和模型實驗。

## 5 清理不是把所有空白刪掉

目前程式的具體例子：

- **日期**：解析發佈／觀察日期，計算兩者相差的天數。缺失必要日期或發佈晚於觀察日期的紀錄會被排除；Steam 日期有代理日期限制。
- **未知值**：空白不直接當成 0 或 false。遊戲名稱字面為 `None`／`NULL` 時保留並標記，不因看似缺失字眼就刪除。
- **範圍**：Android 採明確的 16 個遊戲類別，排除無法可靠區分體育 App／遊戲的 Sports。Steam 主研究範圍限定正觀察價格等條件，並排除僅軟件類型的啟發式紀錄。
- **衝突**：Android 的免費／價格矛盾，在固定分析版本把免費狀態設成未知。非 USD／未知幣別不冒稱美元價格。
- **目標**：Steam 用來源估算 owners 區間映射三級；`0–0` 視為未知。Android 用安裝量下限分為 `<1,000`、`1,000 至 <100,000`、`≥100,000`。不是收入或精確銷量。
- **重複 ID**：候選清理遇到重複或缺失 ID 會停止，不會默默保留第一筆。

`row_ledger`／`cohort_ledger` 是逐列處理紀錄，記下是否保留及原因；`rule_counts.csv` 是規則影響的統計。原始 Dataset 沒有被直接修改。

## 6 模型究竟在哪裡

| 程式 | 角色 |
|---|---|
| [preprocessing.py](src/models/preprocessing.py) | 將類別／集合編碼成數字，處理數值缺失及縮放；這些學習到的規則只在當折 fitting 資料上擬合 |
| [run_development.py](src/models/run_development.py) | 基準分類器及 Logistic Regression 的開發實驗 |
| [run_tree_development.py](src/models/run_tree_development.py) | Random Forest 比較 |
| [run_age_sensitivity.py](src/models/run_age_sensitivity.py) | 檢查限制遊戲觀察年齡後結果如何改變 |
| [run_scope_sensitivity.py](src/models/run_scope_sensitivity.py) | 檢查不同樣本範圍／目標分級下的結果 |
| `verify_*.py` | 另行核對資料、分組、指標及保存模型的輸出等；各檔的檢查範圍不同 |

目前已使用 scikit-learn 的 Logistic Regression 和 Random Forest，並非 kNN。`P` 指快照中可用於描述規劃的屬性；`P+A` 再加入遊戲觀察年齡。這些屬性不是已證明的發售前測量，因此不能把結果說成已驗證的新遊戲成功預測。

模型輸出保存在 `data/processed/model_*`，摘要在 `reports/日期/model_*/results_notes.md`。多個檔案對應不同平台、特徵組、設定及驗證折，並不是每個檔案都代表新功能。

約 70/15/15 的切分以開發者群組為單位，不追求行數恰好等比例。同一開發者群組不跨集合；Steam 合作開發形成相連群組也一起分配。這能減少同開發者作品同時落入訓練／評估造成的資訊洩漏，但不保證消除所有偏差。

| 平台 | train | calibration | test | 合計 |
|---|---:|---:|---:|---:|
| Steam | 51,152 | 11,435 | 10,940 | 73,527 |
| Android | 221,806 | 48,297 | 48,197 | 318,300 |

現在的模型比較使用 train 內的三折群組交叉驗證；保留的 calibration／test 效能尚未評估。不能把開發 CV 分數叫作最終測試準確率。網站的歷史比例亦不是模型預測機率。

## 7 網站與新 CSV 的另一條流程

```text
瀏覽器：index.html + style.css + app.js
  ↓ 傳送平台、篩選條件等請求
Python：src/demo/server.py
  ↓ 用 DuckDB 查詢目前啟用的資料版本
返回筆數、三級分布、重疊及來源資訊
  ↓
瀏覽器顯示結果／匯出 JSON
```

`index.html` 是頁面結構，`style.css` 是外觀，`app.js` 負責按鈕、請求和更新畫面；它們都在 `src/demo/static/`。`server.py` 處理請求及查詢，不包含重新訓練模型的操作。

| 匯入程式 | 用途 |
|---|---|
| [contracts.py](src/imports/contracts.py) | 驗證指定 CSV 欄位、資料型別及資格規則，形成預覽／處理紀錄 |
| [repository.py](src/imports/repository.py) | 儲存已驗證快照及啟用版本設定，讀取時核對完整性 |
| [convert_sources.py](src/imports/convert_sources.py) | 將兩種已知來源的原始欄位轉成系統接受的 CSV |
| [cli.py](src/imports/cli.py) | 從命令列產生範本、驗證及匯入；平時可用網站介面 |

使用者匯入指定格式 CSV → 驗證／預覽 → 儲存版本 → 主動啟用 → 網站查詢新版本。匯入版本保存在 `data/application/v1/versions/`，`active.json` 記錄各平台正在使用哪個版本。

這條流程不會覆寫固定研究資料，不自動合併舊快照，亦不自動重新訓練模型。目前 CSV 合約涵蓋描述比較所需欄位，並不等於完整模型訓練表。詳細操作與可用示範 CSV 見 [CSV 匯入指引](CSV_IMPORT_GUIDE.md)。

## 8 老師追問時應理解的幾個要點

| 問題 | 回答要點及可打開的證據 |
|---|---|
| 為甚麼有這麼多檔案？ | 分開程式、輸入、規則、結果和驗證證據；保留不同實驗版本以便重現。不是所有檔案都要逐個執行。 |
| Data 是手動整理嗎？ | 清理步驟已寫成 Python 程式。AI 協助審核、實作與核對；學生需要理解並解釋選擇。打開 `clean_candidates.py` 和 `cleaning_rules.py`。 |
| 哪裡用 pandas？ | 清理、特徵準備、模型資料處理都有 `import pandas as pd`；大型盤點和網站查詢亦使用 DuckDB。 |
| 為甚麼不能把安裝量放進模型輸入？ | 因為它用來定義答案；放進去等於把答案線索交給模型。打開特徵白名單。 |
| 怎樣知道清理沒有亂刪？ | 查看逐列 ledger、規則計數、獨立 verifier、tests，以及原始檔 hash。這是工程核對，不代表來源沒有偏差。 |
| 網站用了 AI 預測嗎？ | 目前沒有。研究模型已另行實驗，網站現階段提供歷史條件比較。 |
| 新資料可以直接使用嗎？ | 符合指定格式及驗證規則後可作新的應用快照；任意 CSV、模型自動重訓不在現有功能內。 |
| AI 做了甚麼，你做了甚麼？ | 按真實紀錄說明需求／決策／操作／修改／理解，以及 AI 協助的程式和分析；不要把 AI 協作實作說成全部獨立手寫。參閱 assistance log。 |

SHA-256 可以理解為檔案內容指紋，用於檢查版本是否改變；不能證明資料內容一定真實。`manifest.json` 是一次資料／實驗產物的清單與設定紀錄；`verification.json` 是檢查結果。`reports` 中帶日期的資料夾記錄產生結果的階段，不代表資料採集日期。

## 9 第一次只需實際走這幾步

1. 雙擊 `START_DEMO.cmd`，完成一次 Steam 或 Android 條件比較。
2. 打開本導覽，沿「原始資料 → 清理 → 特徵／切分 → 分析／模型／網站」指出各位置。
3. 打開 `cleaning_rules.py`，找到 `owner_interval` 或 `install_tiers`，理解一個標籤如何產生。
4. 打開 `feature_policy_v1.json`，指出一個可以用的特徵及一個禁止用的答案欄位。
5. 打開一份 `results_notes.md`，分清楚研究結果與仍未完成的最終評估。

想看熟悉的 load CSV、groupby、畫圖及一次 `.fit()`，可選擇開啟 [Notebook](notebooks/01_understand_your_fyp.ipynb)，啟動及執行說明見 [notebooks/README.md](notebooks/README.md)。它讀取已處理資料做教學，不能代替原始 Kaggle 清理示範；深入練習不是網站開發的前置要求。
