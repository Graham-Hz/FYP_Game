# Power BI 教學交接與驗收 v1

日期：2026-10-11。這是給學生及協助操作的 ChatGPT 的工作指引。學生自行操作 Power BI Desktop；目前只完成 CSV 匯出與資料核對，尚未建立或驗證 PBIX。前兩頁完成即可，模型結果頁是第二輪工作。

## 可直接貼給 ChatGPT 的開場

> 請用繁體中文逐步教我用 Power BI Desktop，完成下面這份 FYP 任務。我學過 COMP3925 的 Power Query、relationships、DAX measures 和 report design，但需要操作指導。每次只教一小段，待我核對結果再繼續。先做 Android 頁，再做 Steam 頁。請沿用本文指定資料表名稱、欄位、分級及驗收數字。先確認我的 Power BI 畫面版本與語言，不要假設你能讀取我電腦的路徑。資料已由 Python 匯出，不需要重新下載 Kaggle、重新訓練模型或改清理規則。不要替我撰寫可提交的 FYP report 正文。若畫面或數字不同，先找原因，不要用手動改數字令結果吻合。

把下列規格一併貼上；需要資料時，提供下面四個 CSV。電腦內已準備好，無需再使用 PowerShell 產生。

## 目的與範圍

使用者是獨立遊戲開發者／小型工作室。問題是：「在這個歷史樣本中，符合某些規劃條件的遊戲有多少？它們的觀察結果分布如何？支持量是否太小？」

建立 **Power BI Desktop report（本機 .pbix）**。不是 service dashboard、收入預測、因果分析或新遊戲成功機率。Steam 和 Android 分頁、分開計數，不產生兩平台共同的成功率。

資料僅用 frozen `analysis_v1` 的 train subset：Steam 51,152；Android 221,806。Calibration／test 沒有匯出。CSV 是當前固定研究資料的展示介面，不會跟應用程式新 CSV activation 自動同步。

## 檔案及來源

在檔案總管打開：

`F:\HKBU_Y4\FYP\My_FYP\Program\data\processed\powerbi_v1`

| CSV／Power BI 表名（完全一致） | 一列代表 | 列數 |
|---|---|---:|
| `pc_games.csv` → `pc_games` | 一隻 Steam game | 51,152 |
| `mobile_games.csv` → `mobile_games` | 一個 Android app | 221,806 |
| `pc_genres.csv` → `pc_genres` | 一組不重複 game–genre 配對 | 143,472 |
| `genre.csv` → `genre` | 一個 genre label | 33 |

來源：Steam [March 2025 Kaggle dataset](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset) 的 positive-observed-price 主 cohort；Android [June 2021 Google Play dataset](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps) 的保守 game cohort。兩者經 FYP 的既定清理及 group split 選取 train，不能稱為全市場總量。Steam age 以 2025-03-13 作來源月份代理日；Android 用各列 scrape observation。Age 已計算好，勿用 TODAY() 重算。

## 載入及欄位字典

使用 Get data → Text/CSV → Transform Data，UTF-8／逗號／首列 header。確認自動 Changed Type，特別是所有 `app_id` 必須是 Text。不要把數字 ID 相加。

| 欄位 | 型態／意義 |
|---|---|
| `app_id` | Text；平台內唯一 ID。兩平台 ID 不 join |
| `target_tier` | Text；原分析標籤。圖表可縮短顯示標題，但不改資料值 |
| `tier_order` | Whole Number；1、2、3。將 target_tier 設定 Sort by column = tier_order；排序欄隱藏 |
| `age_days` | Whole Number；發售至資料觀察的日數。不是追蹤預測期 |
| `age_band`／`age_band_order` | Text／Whole Number；0–179、180–364、365–1094、1095+ days，另保留 Unknown；依 order 排序 |
| PC `price_observed` | Decimal Number；snapshot price，**幣種未確認，不加 USD／HKD 符號**；不加總 |
| PC `windows`／`mac`／`linux` | Text `Yes`／`No`／`Unknown`，unknown 不變成 No |
| PC `categories_unavailable`／`languages_unavailable` | Text Yes／No／Unknown；品質旗標，Yes 代表 unavailable |
| Mobile `category`／`content_rating` | Text；同一筆 app 各一個值 |
| Mobile `free` | Text Yes＝免費、No＝付費、Unknown＝未確定，不把未知併入付費 |
| Mobile `ad_supported`／`in_app_purchases` | Text Yes／No／Unknown |
| Mobile `price_usd` | Decimal Number；空值保留 null；0 是真正數值，不可混同 missing；不要換算 Steam 價格 |
| Mobile `price_usd_unavailable`／`free_unavailable` | 品質旗標；Yes 代表 unavailable |
| Bridge `genre` | Text；多 genre 的一隻遊戲會在 pc_genres 出現多列；`<empty_or_missing>` 是保留未知／空集合的標籤 |

Power Query 只做載入、型態和必要的顯示整理，不 drop duplicates 遮掩重複 ID，不刪 missing，不自行重新定 target。

Target 定義：Steam O1 為來源 owner interval 上限 ≤20k；O2 為來源 interval 下限 ≥20k、上限 ≤100k；O3 為來源 interval 下限 ≥100k。區間本身是估算，非精確 owner 數。Android M1：minimum installs <1k；M2：≥1k 且 <100k；M3：≥100k。安裝數是下界。**不要為 Steam 區間取中點計平均銷量，也不要稱任何一級為已驗證的「成功」。**

## Data model

第一步 Android 頁只需 `mobile_games`，沒有 relationships。

Steam 頁才加入其餘三表；移除錯誤的自動偵測關係，只建立：

1. `genre[genre]` **1 → many** `pc_genres[genre]`，Single direction，由 genre 流向 bridge，Active。
2. `pc_games[app_id]` **1 ↔ many** `pc_genres[app_id]`，Both directions，Active。

兩者都以 one-to-many cardinality 建立；第二條需要反向把已選 genre 的 game IDs 傳回 pc_games。這是本次單一 bridge 的明確例外，不把其他關係一律改 Both。三表之間沒有第二條傳遞路徑，不直接再連 genre 到 pc_games；Mobile 不與 Steam 相連。

Genre 的 slicer 使用 `genre[genre]`。多選 Action、Indie 表示 **Action OR Indie**，包含任一即納入，重疊遊戲只計一次；不宣稱這是兩個 genre 都符合的 AND 篩選。每個 genre bar 可以共用遊戲，因此所有 bar 的總和可能大於整體遊戲數。關係圖及多選核對是必要驗收。設計原則參考 [Microsoft many-to-many guidance](https://learn.microsoft.com/en-us/power-bi/guidance/relationships-many-to-many)。

## DAX measures

以下是待在 Power BI 實際執行核對的起始定義，不宣稱已測試 DAX engine。將每個 measure 分開建立；列名不翻譯。

```dax
Mobile Games = COALESCE(DISTINCTCOUNT(mobile_games[app_id]), 0)

Mobile Tier Share =
DIVIDE(
    [Mobile Games],
    CALCULATE(
        [Mobile Games],
        REMOVEFILTERS(mobile_games[target_tier], mobile_games[tier_order])
    )
)

Mobile Median Age = MEDIAN(mobile_games[age_days])

Mobile Support Note =
IF([Mobile Games] = 0, "No matching games",
    IF([Mobile Games] < 30, "Small sample (<30); interpret cautiously", ""))

PC Games = COALESCE(DISTINCTCOUNT(pc_games[app_id]), 0)

PC Tier Share =
DIVIDE(
    [PC Games],
    CALCULATE(
        [PC Games],
        REMOVEFILTERS(pc_games[target_tier], pc_games[tier_order])
    )
)

PC Median Age = MEDIAN(pc_games[age_days])

PC Support Note =
IF([PC Games] = 0, "No matching games",
    IF([PC Games] < 30, "Small sample (<30); interpret cautiously", ""))
```

Games 用整數、Tier Share 用 percentage 一位小數、median age 用 days。Share 的分母只移除 tier 及其排序欄，保留 age／category／genre 等規劃條件；不要移除整張 fact table 的 filters。零分母維持 BLANK，不改成成功率 0%。可參考 [REMOVEFILTERS 官方定義](https://learn.microsoft.com/en-us/dax/removefilters-function-dax)。初版不放 outcome tier slicer，以免造成難以解讀的分母；圖表的 outcome 點選互動亦先設為不過濾其他 visuals。

30 是沿用原型的**介面提醒門檻**，不是統計有效性／代表性的保證。UI 提示不能由 CLT 的教學口訣推論成 n≥30 就可靠。

## 兩頁 report 要做甚麼

### Android historical sample

目的：查看 category／monetization 條件下的歷史 install tier 分布和資料支持。

- 頁首文字：`Google Play, June 2021; research train subset; install lower-bound tiers`。
- Slicers：category、free、ad_supported、in_app_purchases、age_band。保留 Unknown 選項，不預先只顯示免費。
- Cards：Mobile Games、Mobile Median Age、Mobile Support Note。
- 橫向 bar：category 在 axis、Mobile Games 在 value，以樣本數排序。
- 100% stacked bar：category 在 axis、target_tier 在 legend、Mobile Games 在 value；tooltip 顯示 Games 和 Tier Share。不要直接加總百分比。
- Matrix：target_tier 在 rows、Mobile Games 和 Mobile Tier Share 在 values。三個 tier 的 share 總和應為 100%（有 matching games 時）。

### Steam historical sample

目的：查看 genre／age 條件下的 owner interval tier 分布。

- 頁首文字：`Steam, March 2025; positive observed-price research train subset; estimated owner intervals`；加上 `Price currency unverified`。
- Slicers：genre[genre]、pc_games[age_band]；第一版不必加入更多 filters。
- Cards：PC Games、PC Median Age、PC Support Note。
- 橫向 bar：genre[genre] 在 axis、PC Games 在 value；顯示多 genre 重疊提醒。
- 100% stacked bar：genre[genre] 在 axis、pc_games[target_tier] 在 legend、PC Games 在 value。
- Matrix：target_tier、PC Games、PC Tier Share。

版面優先顯示問題、來源、slicers、support、結果，使用一致的 tier 順序和可分辨顏色。不需要 pie、map、word cloud、動畫或自訂 visual。首次製作先讓 slicers 控制所有本頁 visuals；bar／matrix 的點選 cross-filter 先關閉，驗收後再逐一開啟並測試。

不直接把全部 Android rows 放入 Python visual：它超過官方列出的 150,000-row 上限；Python visual 的圖像本身也不能像原生圖表一樣點選後 cross-filter 其他圖。首版採原生 visuals；如果之後需要 Python 特殊圖，先明確匯總再作圖。[Microsoft Python visual 限制](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-python-visuals#limitations)

## 必須核對的數字

清除 filters／selection 後：

| 平台 | Total | Tier 1 | Tier 2 | Tier 3 |
|---|---:|---:|---:|---:|
| Steam | 51,152 | 38,428 | 8,527 | 4,197 |
| Android | 221,806 | 103,908 | 81,403 | 36,495 |

組合篩選（每次先 clear filters）：

| 操作 | Total | Tier 1 | Tier 2 | Tier 3 |
|---|---:|---:|---:|---:|
| Steam genre 同時選 Action、Indie（OR） | 41,926 | 31,522 | 6,953 | 3,451 |
| Steam Action，age 選 365–1094 及 1095+ | 17,406 | 12,126 | 3,315 | 1,965 |
| Android free=No，age 選 365–1094 及 1095+ | 5,372 | 2,406 | 2,546 | 420 |
| Android category=Puzzle | 34,175 | 17,108 | 13,077 | 3,990 |

Android free=Yes／No／Unknown 分別為 **215,952／5,850／4**。Unknown 應觸發 small sample 提示；再選一組沒有交集的 category／age 條件，確認 Games=0、Share blank、No matching games。不要手動輸入上述答案代替 DAX。

所有圖的分母、filters 和 matrix 必須一致；檢查排序正確。0.0% 的四捨五入總和不一定精確 100.0%，允許顯示捨入，但整數 counts 必須完全相符。完整 export provenance 見 `reports/2026-10-11/lecture_review/powerbi_export_verification.json`；資料已用獨立 pandas 與 frozen train 逐欄比較，Power BI 内部仍須上述驗收。

## 保存及交回甚麼

在 `Program/reports/powerbi/` 新建並保存 `FYP_Historical_Overview_v1.pbix`；此名稱是**預定交付，現在尚不存在**。保留兩頁全貌、關係圖、一次 genre 多選核對、Android Unknown 提示的 screenshots，以及簡短記錄哪幾項驗收已通過。交回後由 Codex 對照來源及語意再 review；不要只說「圖看起來正常」。

儲存後關閉並重開 PBIX，確認連線；用同一組 CSV 按 Refresh 後再核對 baseline。這只證明同資料 refresh，未證明自動處理任意新 CSV。若要連接 application snapshots，需另外加 version／provenance 輸出契約。

## 第二輪才做的模型結果頁

先完成前兩頁，再使用既有結果 CSV。候選來源：`reports/2026-10-10/model_tree_v1/linear_tree_comparison.csv` 與 `reports/2026-10-11/model_age_v1/matched_comparison.csv`、`family_comparison.csv`。匯入前重新核對欄名／資料粒度；**不與 game tables 相連**。展示同平台、同 features、同 cohort 的模型比較；年齡分析區分 `age_refit` 和 `primary_fit_same_rows`。Macro-F1 是現成研究指標，不 SUM；不混合 mean-fold 與 pooled 分數，不跨平台平均、不把 fold SD 當 CI，標記 `Development CV; not final test`。本版沒有準備或驗收此頁。

## 給 Codex 的重現入口

在 Program 執行 `uv run --locked python.exe -B -m src.analysis.export_powerbi_v1`，再執行 `uv run --locked python.exe -B -m src.analysis.verify_powerbi_v1`。只讀 frozen research input；沒有重新訓練、沒有讀出 calibration／test 分析表、沒有更改 app 的 active version。生成 CSV 已由現有 `data/processed/` 規則忽略，不加入 Git；PBIX 含資料，應先決定分享範圍再另行上傳。
