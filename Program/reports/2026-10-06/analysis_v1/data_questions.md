# 剩餘資料疑點：證據與處理

2026-10-06 工作筆記。將「已找到原因」、「只有支持某原因的線索」和「採取保守分析政策」分開。原始檔、上一輪 candidate 及舊報告均保留。

| 疑點 | 本次證據 | analysis_v1 處理 | 尚未確定 |
|---|---|---|---|
| PC `0 - 0` owners 與評論 0 | 已固定的上游 scraper 在 SteamSpy request 無結果時填入 owners `0 - 0`、positive/negative 0 | owners 0-0 保持未知；review target 繼續停用 | 未知當初精確 collector revision／呼叫參數，因此不能把每筆 0 歸因為 API 失敗，也未解释全部 review count 差異 |
| Steam price=0 | 同一程式在 is_free 或缺 price_overview 時填 0 | 主實驗限制為觀察價格 >0；零價留作另行描述／敏感度 | 0 不能證明永久 F2P；缺 owners 的選擇偏差仍存在 |
| Steam price 幣別 | 當前固定上游程式預設 cc=us，從格式化價格抽取數值 | 使用 `price_observed` 源單位，不宣稱已核實 USD；必做 P_without_price 對照 | 本地版本的原始抓取參數沒有證據，不能只靠現行預設補出幣別 |
| Demo 名稱排除 | 其餘基本規則後有 53 筆；檢視名稱清單。1129080 的本地 description 描述 forex 練習與模擬，不是另一款作品的試玩版 | 加入一筆有記錄的 exception，基本 cohort 89,453→89,454；其餘保留明確標記為啟發式的排除 | 未對其餘 52 筆逐一證明官方歷史 app type；日後可做不加 exception 的敏感度 |
| 軟件類 genres | 1,033 筆 software-only heuristic；樣例含 Silo 2、VR 體驗 The Marvellous Machine。兩者本輪 API type 都返回 game | 主 cohort 排除此類，保留 inclusion sensitivity；不用 API type 冒充完整產品分類 | 部分 educational／VR 作品可能被排除；不是聲稱這 1,033 筆全是壞資料 |
| 字面名稱 none | 385020 本地 description 為停止服務提示，developer 亦是 none；385020／398970 當前 API 仍返回 name=none | 名稱字串保留；developer 的占位字串按欄位政策當成未知，不能虛構共同工作室 | 當前 metadata 不能重建 2025 的實際開發者身份 |
| Android Free／price 衝突 | 5 筆均 Free=False、原 price=0，且幣別缺失；已有逐筆 CSV | 保留安裝標籤；將這 5 筆 `free` 設為未知，新增 free_unavailable；price_usd 本來已未知 | 不判定它們真的免費／付費，亦不推測當年的折扣或 scraper 錯誤 |
| Android 非 USD 價格 | 214 筆非 USD 或未知 | 保留列；price_usd 保持空值及 indicator | 不做今天的匯率換算，也不把未知幣別 0 變成 USD 0 |
| 開發者重複／共同製作 | PC 全量原資料建立多開發者連通圖；Mobile 名稱標準化後有少量字串合併 | NFKC、空白整理、casefold；不模糊比對或刪標點。所有共同開發者連到同組，包含之後被排除的橋接作品 | 字串一致／相近不等於已驗證同一法人；公司曾更名等問題仍未解決 |

## 證據位置

- [上游 scraper 固定版本](https://github.com/FronkonGames/Steam-Games-Scraper/blob/cdbbddd9b01c7be2a9d80635c1b93b4936915252/SteamGamesScraper.py)：price 約 L204–207；SteamSpy 成功及失敗路徑約 L402–430；cc 預設約 L47、L144–149。本機只讀副本和 SHA-256 在 `data/raw/source_metadata/2026-10-06/`。這是可能的機制證據，不是當初執行紀錄。
- [Forex Demo Accelerator 目前官方 API](https://store.steampowered.com/api/appdetails?appids=1129080&cc=us&l=english)；另外保存 1000510、100400、385020、398970 的回應。`steam_app_checks/manifest.json` 記錄查閱日、URL、hash 與限制。**2026 查閱資料沒有合併進 2025 特徵／target**。
- [53 筆 title 排除檢視清單](demo_title_review.csv)；Forex 的完整本地 description 仍在原始 full Parquet，可按 app_id 1129080 追查。
- [Mobile 衝突記錄](../cleaning_candidate_v1/mobile_free_price_review.csv)。候選 v1 保留原 Free；本輪只在新的 analysis_v1 feature artifact 遮蔽衝突值。
- [PC 開發者標準化變體](pc_developer_normalization_review.csv)、[Mobile 變體](mobile_developer_normalization_review.csv)及 [診斷計數](data_question_diagnostics.json)。這些清單是可核對的合併規則痕跡，不宣稱逐項做過法人身份核實。

## 仍不做的分析

reviews 的新增評論／成長率、owners midpoint 當銷量、Android installs 當收入、2021/2025 兩平台市場规模直接排序、用如今 API 修補當年 outcomes，均不在此版分析範圍。現有問題已以明確 scope／missingness 政策隔離，可以進行所定義的歷史分類實驗；沒有宣稱所有來源疑點已消失。
