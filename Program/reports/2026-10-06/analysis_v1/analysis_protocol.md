# analysis_v1：分析特徵與切分已固定

日期：2026-10-06。這是可執行的工作版本，因使用者要求接續而固定；**不代表導師已批准、正式論文已完成或模型已有效**。本版覆蓋研究設計 v1 中尚未落實的 cohort、feature 及 split 部分，其餘評估原則仍適用。

## 主要任務及樣本

PC target 保持 estimated-owner source interval 三級，0-0 仍未知；主要母體限**快照觀察價格 >0**、非 software-only heuristic、有可用 target 及開發者標籤的作品。這個 scope 減少零價樣本 owners 高比例未知造成的混淆，但**不修復**整個市場的選擇偏差，也不代表原價、終身付費狀態或銷售收入。

Mobile target 保持 minimum-installs 下界三級，保守遊戲類別及原日期規則不變。5 筆 Free/price 矛盾保留，Free 改成 unknown；214 筆非 USD／未知幣別保留缺失 price_usd。

PC 基本 cohort 加入一筆具理由的 demo 名稱例外後是 89,454。主分析按順序排除未知 owners 8,295、再排除未知 developer 11、再排除非正價格 6,908、再排除 software-only 713，得到 **73,527**。這是互斥流程；各條規則獨立命中的 133 個 developer 缺失／占位值、1,033 個 software-only 等會重疊，不可再相加。詳見 [cohort_flow.csv](cohort_flow.csv)。

## 實際切分

| 平台 | 主要 cohort | Train | Calibration | Test | 開發者群組 | 最大群組 |
|---|---:|---:|---:|---:|---:|---:|
| PC | 73,527 | 51,152 | 11,435 | 10,940 | 43,242 | 832 |
| Mobile | 318,300 | 221,806 | 48,297 | 48,197 | 131,030 | 1,333 |

實際比例 PC 約 69.57/15.55/14.88%，Mobile 約 69.69/15.17/15.14%。沒有為了類別分布重抽 seed。每個 split 和每個訓練 CV fold 均有全部 3 類；實際類別比例不同，保留此差異並報告。分級標籤不是等距人數，不做 owners 數量 MAE。

PC 先以全 94,948 筆原始作品的非占位 developer 名稱建立連通群組，包括未進主樣本的共同開發作品，避免先篩选後漏掉橋接關係。Mobile developer_id 原字串有 131,444 個，標準化後 131,030 組。名稱只做 Unicode NFKC、空白整理及 casefold，不做模糊實體合併；群組是資料標籤的集合，不是已證實公司實體。

固定 seed=42，SHA-256 對 `seed|holdout|platform|group_id` 做 UTF-8 雜湊，前 16 hex 轉成 [0,1) 數值；<0.70 train、<0.85 calibration，否則 test。另一個 `cv` namespace 取 modulo 3，僅 train 使用。群組及分配都不讀 target 值；SQL 獨立重算每列分配，差異為 0。

## 特徵白名單

| 特徵集合 | PC | Android |
|---|---|---|
| P | genres、規劃功能 categories 白名單、supported_languages、price_observed、Windows/Mac/Linux、功能／語言缺失旗標 | category、content_rating、Free、USD price、ads、IAP、價格／Free 缺失旗標 |
| P+A | P 加 age_days | P 加 age_days |
| age_only | age_days | age_days |
| P_without_price | P 去掉 price_observed；必做幣別不確定性的對照 | 未設此必做對照 |

PC `planning_categories` 明確保留單人／多人／合作／PvP、區域或線上連線、手掣及 VR 支援等可規劃功能。沒有把原 categories 全部照單全收；Steam achievements、trading cards、Workshop、stats 等不在此版白名單。精確欄位和功能 token 見 `config/analysis_v1.json`、`config/feature_policy_v1.json`。

genres／languages 在未來訓練折學習 multi-hot vocabulary；其餘類別編碼、imputation、scaling 亦只在訓練折擬合。未知 token 的 coverage 必須記錄；不可在 test 上重新擬合字典。本輪**只整理原始型別的特徵表，沒有擬合 encoder、imputer 或模型**。

P 代表可用來描述規劃的屬性；實際數值仍來自上市後快照，不是已保存的首發前屬性。P+A 的 age 是累積觀察時間，不是固定六個月預測期。PC `price_observed` 未自行改名 USD，且不與 Mobile price 合併比較。

產品名稱、IDs、developers／publishers、owners／installs 的所有組成與衍生值、評論／評分、CCU、playtime、Metacritic、user tags、split 與 CV fold 均不能作預測輸入。features 與 labels/splits 分檔保存。`app_id` 只供一對一連接；`select_features()` 按白名單取欄，連 app_id 也不會進模型。

## 訓練之前及之後的使用規則

1. 先執行固定版本驗證器；輸入、設定或生成程式改變時，既有 manifest 會阻止覆寫，應建立新的 analysis 版本並說明原因。
2. 下一輪先在 **train** 的 3-fold group CV 比較 majority／class-prior、age-only 及少量候選模型。模型種類、超參數和 preprocessing 實作需在看 test 成績前確定；本輪未安裝建模套件。
3. 用 CV 決定模型後，train 擬合；calibration 只作校準與已列明支持規則，不用於反覆選模型家族；test 最後才評估。本輪只核對 test 的完整性與類別計數，沒有計算模型分數。
4. 宏平均 F1 為主，另報 balanced accuracy、逐類指標、混淆矩陣。機率輸出再評 log loss、Brier、reliability；機率沒有驗證前不放進介面。
5. cohort ledger 保存較廣範圍樣本的既定群組分配，供軟件類別、價格、180/365 日、Mobile 四級等敏感度實驗沿用。另做 random split 對照前必須先寫清實驗用途，不能從不同切分中挑最高成績。

## 可重跑指令及產物

在 Program 執行：

```powershell
uv run --locked python src/data/freeze_analysis.py
uv run --locked python src/data/verify_analysis.py
uv run --locked python src/data/review_analysis_questions.py
uv run --locked python -m unittest discover -s tests -v
```

`data/processed/analysis_v1/` 保存兩平台 feature Parquet、labels_splits Parquet、cohort ledger 及 PC 全量 developer edges；這些資料由 `.gitignore` 排除。GitHub 保存程式、設定、計數及雜湊，並不自動備份大型資料。

[manifest.json](manifest.json) 固定輸入、依賴和產物雜湊；[verification.json](verification.json) 記錄独立驗證成功及其對應 manifest。10 個回歸測試包括：共同開發者橋接、占位名稱不成組、Unicode 規則、CV 隔離、feature allowlist、上一輪名稱／標籤邊界。沒有以測試通過冒充研究結論。
