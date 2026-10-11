# CSV 匯入與資料版本：操作指引

版本：`application_csv_v1`，2026-10-10。功能已實作；適用於本機單一程式程序，不是多人／公開網路服務。沒有新增執行依賴或修改研究 lock。

## 直接從介面使用

1. 雙擊 `START_DEMO.cmd`。若仍有舊版啟動視窗，先關閉後重開。
2. 選 Steam 或 Android，展開「資料版本與 CSV 匯入」。兩平台各自保存啟用版本。
3. 下載空白範本，或選用下面已轉換的真實資料 CSV。空白範本只有表頭，不能直接當資料匯入。
4. 選 CSV，填來源名稱、網址（可留空）、快照截至日期及資料性質。Steam 價格幣別未核實時保留 `unknown`。
5. 按「驗證及預覽」。先看總筆數、合資格／排除／無效筆數和原因；可下載 JSON 驗證報告。
6. 通過後按「儲存已驗證版本」。此步不切換當前資料；同一 CSV、來源設定及規則重複匯入不會再存一份。
7. 在版本下拉選單選新版本，按「啟用所選版本」。篩選及舊結果會清除，再按「比較歷史分布」。
8. 選「原有研究 train 資料」即可切回。重開程式會保留上次各平台的選擇。

新快照不會合併旧快照、覆寫 research `analysis_v1`、改動 train/test 或重新訓練。匯出結果記錄實際版本、資料性質、來源、分級及樣本分母；匯入版本不冒稱 research train。

## 本機已準備的試用 CSV

這兩份是從原始 Kaggle CSV 按已固定 train ID 轉換，**不是新外部資料，也不是整個市場**。用來證明匯入流程可處理真實規模。來源及 metadata 同放在各自資料夾。

| 平台 | 檔案（相對 Program） | 來源名稱 | 快照截至日期 | 預期合資格筆數 |
|---|---|---|---|---:|
| Steam | `data/application/conversions/pc_train_v1/snapshot.csv` | Steam March 2025 research train subset | 2025-03-13 | 51,152 |
| Android | `data/application/conversions/mobile_train_v1/snapshot.csv` | Google Play June 2021 research train subset | 2021-06-16 | 221,806 |

資料性質選「歷史資料」。Steam 幣別 `unknown`；逐列 observation 留空並明確使用快照代理日期。Android 保留原始每列 scraped date；June 16 是該檔截至日期，不是 Kaggle 版本發佈日。這兩份 CSV 不會隨 Git clone 下載。

## CSV 格式

- UTF-8，可有 BOM；逗號分隔。欄名必須完整且不重複，順序可變，不接受額外欄。
- 上限 64 MiB、500,000 筆、單一欄位 32,768 字元。日期採 `YYYY-MM-DD`，數字不放千分位逗號。
- 首列是欄名；空白代表未知，**不等於 0／false**。標題 `None`／`NULL` 保留為文字。
- 同一 CSV 的 ID 不可重複；不同版本可以有同一遊戲。
- 每份 CSV 是完整的分析快照，可以是明確記錄來源範圍的子集；不自動與舊版本合併。
- PC 集合採 JSON 陣列；在 CSV 中需按 CSV 規則跳脫雙引號，建議使用轉換器或正常 CSV writer。

### 共用欄位

| 欄名 | 定義及空白處理 |
|---|---|
| `app_id` | 非空識別字串，最多 300 字；不可重複 |
| `title` | 遊戲名稱，最多 500 字；空白列排除 |
| `release_date` | 發佈日期；缺失列排除；不合法格式阻止匯入 |
| `observed_date` | 此列觀察日期；空白使用 metadata 的 snapshot_date，並計數提示。不可晚於快照截至日期；release 晚於 observation 的列排除 |

### Steam 額外欄位

| 欄名 | 定義及規則 |
|---|---|
| `genres` | JSON 字串陣列，例如 `["Action","Adventure"]`；空集合排除；軟件專用類型依既定 heuristic 排除 |
| `planning_categories` | JSON 字串陣列；可空，token 必須在 `config/analysis_v1.json` 的 `pc_planning_categories` 白名單內 |
| `developers` | JSON 字串陣列；至少一個非 placeholder 開發者才納入。不是模型輸入或已核實公司實體 |
| `price_observed` | 快照觀察價格，非負有限數值；主分析只納入 >0；未知幣別不推斷成 USD |
| `owner_lower`, `owner_upper` | 估算 owners 原始區間上下界；同時空白或 `0,0` 為未知並排除。一邊缺失、負數、非整數或下界大於上界阻止匯入 |

集合最多 100 個非空字串，每個最多 200 字。Demo/playtest 名稱啟發式與既定個別例外沿用目前設定。Owners tier：先判 upper ≤20,000；再判 lower ≥100,000；再判 lower ≥20,000 且 upper ≤100,000；其餘跨界區間排除。這是來源區間映射，不是精確銷量。

### Android 額外欄位

| 欄名 | 定義及規則 |
|---|---|
| `category` | 16 個已定義遊戲類別之一；其他列排除，包括含糊的 Sports |
| `developer_id` | 開發者識別字串；空白／placeholder 列排除 |
| `free`, `ad_supported`, `in_app_purchases` | `true`／`false`（不分大小寫），或空白表示未知；其他值阻止匯入 |
| `minimum_installs` | 來源安裝量下界，非負整數；缺失排除，不使用精確 downloads／收入替代 |
| `price` | 非負有限觀察價格或空白；與 free 矛盾時 free 設 unknown 並記錄提示 |
| `currency` | 三個大寫字母的来源貨幣代碼，未知留空；非 USD／未知不當作 USD |

16 類別：Action, Adventure, Arcade, Board, Card, Casino, Casual, Educational, Music, Puzzle, Racing, Role Playing, Simulation, Strategy, Trivia, Word。Installs 分級：<1,000；1,000 至 <100,000；≥100,000。

本版標準 CSV 僅涵蓋描述比較與資格檢查所需欄位，不包含全部建模特徵；不能直接把它當作新的模型訓練表。

## 驗證與資料保存

任何格式錯誤會阻止整個版本儲存。缺少 outcome 等可解釋的排除會記在完整 ledger；若沒有合資格列，同樣不可儲存。多個排除／警告原因可命中同一列，原因次數不能直接相加當作總排除筆數。畫面最多列 100 項格式錯誤，總錯誤數及逐欄數保留。

預覽暫存在記憶體，只保留最新一次，提交時期限 15 分鐘；新預覽或停止程序會清除。沒有到期自動背景回收，但不會累積多份預覽。通過不代表来源內容真實或研究偏差已消除。人工示例必須選 `synthetic`，介面會明示不代表市場。

儲存位置（Git 忽略）：

```text
data/application/v1/
  active.json
  versions/<platform>-<identity>/
    source.csv         原始上傳位元組
    validation.json    來源 metadata、計數、錯誤／提示及規則 hash
    data.parquet       合資格的比較欄位及 outcome tier
    ledger.parquet     全部有效格式紀錄的納入／排除及警告原因
    manifest.json      版本 ID、來源、日期、筆數及以上檔案 SHA-256
```

版本 ID 綁定 CSV hash、metadata、contract version 及 validator／規則 hash。寫入完整後才發布該版本；啟用前重新檢查檔案 hash。啟用設定用原子檔案替換；資料表切換使用 DuckDB transaction。測試覆蓋寫檔失敗時舊版本仍可用；這不是跨磁碟故障的資料庫持久性保證。

目前只支援一個本機應用程序；不要用兩個程序同時修改同一份 registry。沒有多帳戶登入、版本刪除介面、自動爬取或自動重訓。若日後驗證規則更新，舊版本須用保存的 source.csv 及 metadata 重新匯入，不繞過相容性檢查。

若 `active.json` 損壞導致啟動失敗，停止程式、先保存該檔副本供檢查，再把兩平台設定恢復為 `{"pc":"research_train_v1","mobile":"research_train_v1"}`。不要刪除版本資料或修改 frozen manifest。

## CLI 與既有来源轉換

以下都在 `Program` 執行。範本也可直接從 UI 下載；CLI 輸出不覆寫既有路徑。

```powershell
uv run --locked python src/imports/cli.py template --platform pc --output pc_template_v1.csv
uv run --locked python src/imports/cli.py validate --csv data/application/conversions/pc_train_v1/snapshot.csv --metadata data/application/conversions/pc_train_v1/metadata.json
uv run --locked python src/imports/cli.py import --csv data/application/conversions/pc_train_v1/snapshot.csv --metadata data/application/conversions/pc_train_v1/metadata.json
```

`validate` 只驗證；`import` 通過才儲存，不啟用。來源 metadata 欄位全部必須存在：platform、source_name、source_url、snapshot_date、outcome_definition、data_kind、price_currency。PC outcome_definition 為 `estimated_owner_interval`，Android 為 `minimum_installs_lower_bound`；Android price_currency 為 `per_row`。程式不會打開／爬取 source_url。

可重現本輪真實資料轉換（輸出資料夾已存在時須改用新名稱；不必重複執行）：

```powershell
uv run --locked python src/imports/convert_sources.py --platform pc --input "../Dataset/Steam Games Dataset 2025/games_march2025_full.csv" --output-dir data/application/conversions/pc_train_v1 --snapshot-date 2025-03-13 --source-name "Steam March 2025 research train subset" --source-url https://www.kaggle.com/datasets/artermiloff/steam-games-dataset --research-train-only
uv run --locked python src/imports/convert_sources.py --platform mobile --input "../Dataset/Google Play Store Apps/Google-Playstore.csv" --output-dir data/application/conversions/mobile_train_v1 --snapshot-date 2021-06-16 --source-name "Google Play June 2021 research train subset" --source-url https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps --research-train-only
```

Adapter 只支援這兩個已知来源欄位結構。移除 `--research-train-only` 可轉換所提供快照的完整 PC 資料／Android 16 類遊戲，但須用新輸出資料夾和正確 metadata，再獨立驗證；這不等於延用本輪研究切分。轉換記錄保存原檔 hash、輸入／輸出數和篩選原因。不成功時有 `FAILED.txt`，不可匯入該部分輸出。

## 驗證指令及 Chapter 2 證據

```powershell
uv run --project experiments/model_dev_v1 --locked python -B -m unittest discover -s tests -v
uv run --locked --with playwright python.exe -B tests/check_import_browser.py
uv run --locked python -B tests/verify_import_real.py
```

本轮 33 項測試通過，另有 Edge 完整操作測試及兩平台全 train 逐筆核對。實驗資料存於 [驗證紀錄](reports/2026-10-10/csv_import_v1/verification_notes.md)。這些支援 Chapter 2 的流程、processing、storage 及 visualization 討論；不是使用者研究或模型效能結果。
