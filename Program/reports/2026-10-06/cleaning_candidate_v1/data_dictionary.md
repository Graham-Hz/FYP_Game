# 候選清理 v1 資料字典

這是可核對的工作資料，不是最後訓練集。主鍵均為 `app_id` 字串，PC 與 Mobile 分開；不可跨平台直接 join。原始文字及未選用欄位仍在原資料和審核 Parquet 內，候選檔只抽取此階段需要的欄位。

輸入：`data/interim/artem_games_march2025_full.parquet` 及 `data/interim/google_games.parquet`。輸入 SHA-256 在 configuration 和 manifest 中固定。Mobile 輸入已限於 16 個明確遊戲類別；不包括 Sports 歧義記錄。

## 兩平台共用欄位

| 候選欄位 | 型別／來源與處理 | 用途與限制 |
|---|---|---|
| app_id | string；原 app_id，不改大小寫 | 追溯與連接，不能作預測特徵 |
| title | string；PC name / Mobile app_name，保留原字串 | 展示及人工核對；真 null 或只有空白才屬缺失；`none` 等保留，不是已證實有效名稱 |
| release_date | timestamp；PC `%Y-%m-%d` / Mobile `%b %d, %Y` 解析 | 解析失敗保持 NaT，該列不入基本 cohort |
| reference_date | timestamp；PC 固定 2025-03-13；Mobile Scraped Time 日期 | PC 是資料發佈日期代理，不是每筆觀察時間；Mobile 時區未提供，僅使用日期 |
| age_days | nullable integer；reference_date − release_date，日數 | 歷史累積時間；不能當作真正上架前特徵；未來只在明確的 P+A 實驗使用 |
| target_tier | nullable string；平台專屬候選分組 | 不是 revenue / exact sales；不能作預測特徵 |
| target_status | string；標籤解析結果 | 缺失原因／審核，不作預測特徵 |
| label_available | boolean；target_tier 非空 | 候選標籤可用性，不代表資料完全可信或可部署 |

## PC 額外欄位

| 候選欄位 | 型別／來源與處理 | 用途與限制 |
|---|---|---|
| genres | list[string]；原 genres | literal_eval 解析字串 list；去首尾空白、保序去重；空或無法解析者排除基本 cohort |
| categories | list[string]；原 categories | 同上；缺失／空 list 保留，以 ledger 標記；尚未確認哪些可作規劃特徵 |
| supported_languages | list[string]；原 supported_languages | 同上；不是實際玩家語言分布 |
| developers | list[string]；原 developers | 同上；包含逗號的開發者名稱不拆開；供未來群組切分，不作預測特徵 |
| price_observed | nullable float；原 price | 僅保留有限且非負數值；保留來源單位，本流程未獨立證實 Steam price 幣別 |
| zero_observed_price | nullable boolean；price_observed == 0 | 不等同已確認 free-to-play 商業模式 |
| windows / mac / linux | nullable boolean；各原同名欄 | 僅接受 True / False（忽略大小寫及首尾空白）；其他值保持未知 |
| owners_lower / owners_upper | nullable integer；estimated_owners | 來源區間端點，不能用平均值冒充銷量；target-derived，禁止作特徵 |
| software_only_heuristic | boolean；genres 全屬設定內軟件類別且非空 | 僅啟發式判斷；基本 cohort 保留，待產品類型核對及敏感度分析 |

PC target：有效區間須 `0 <= lower <= upper` 且 `upper > 0`。按順序分配：upper <= 20,000 為 O1；lower >= 100,000 為 O3；其餘 lower >= 20,000 且 upper <= 100,000 為 O2。名稱保存為完整的 `O*_source_interval...` 字串。跨越界線而不符合任一組者不標記。`0 - 0` 狀態是 `unknown_0_0`，不是低銷量或失敗。

其他 target_status：`missing`、`invalid`、`straddles_threshold`、`labelled`。基礎 cohort 不因 owners 未知而刪除；只有 labelled candidate 排除未知 target。

## Mobile 額外欄位

| 候選欄位 | 型別／來源與處理 | 用途與限制 |
|---|---|---|
| category | string；原 category | 必須位於已審核 16 個類別；其餘立即中止生成 |
| content_rating | string；原 content_rating | 內容適齡分級，不是玩家年齡 |
| developer_id | string；原 developer_id | 供群組切分；不是已核實的公司法人識別碼 |
| currency | string；原 currency，保持原值 | 追溯幣別；不是匯率換算結果 |
| free / ad_supported / in_app_purchases | nullable boolean；原同名欄 | 只解析明確 True / False；不是實際收入或廣告數量 |
| price_usd | nullable float；原 price 僅當 currency=USD | 數值必須有限且非負；不換算非 USD 值，不把未知幣別的 0 補為 USD 0 |
| price_usd_unavailable | boolean；price_usd 為空 | 提示價格不能用於 USD 比較，相關列仍保留 |
| minimum_installs | nullable integer；原 minimum_installs | 只接受有限非負整數；安裝區間下限，不是精確安裝數；target-derived，禁止作特徵 |

Mobile target：0–999 為 `M1_under_1k`；1,000–99,999 為 `M2_1k_to_under_100k`；>=100,000 為 `M3_100k_plus`。target_status 為 `labelled` 或 `invalid_or_missing`。未使用 maximum_installs、rating 或 rating_count 生成特徵或標籤。

## 每列 ledger 與篩選規則

`pc_row_ledger.parquet` 和 `mobile_row_ledger.parquet` **覆蓋所有輸入列**。基本 cohort 以外的記錄仍能循 app_id 找回原因。所有 `exclude_*` 和 `flag_*` 是非空 boolean。

| 欄位／規則 | 定義及處理 |
|---|---|
| exclude_title_missing | 實際 null 或全空白名稱；文字 null-like 名稱保留 |
| exclude_release_unavailable | 無法按指定格式解析 release |
| exclude_reference_unavailable | 參考日期無法解析 |
| exclude_release_after_reference | release 晚於參考日期 |
| exclude_genres_unavailable（PC） | genres 缺失、空集合或解析失敗 |
| exclude_demo_playtest_title_heuristic（PC） | title 有 ASCII 詞界的 demo / playtest，大小寫不敏感；可能誤排真正作品，屬候選規則，並非官方產品分類 |
| flag_literal_null_like_title | trim、lower 後為 none / null / nan / n/a；供人工核對，不自動刪除 |
| flag_*_parse_error（PC lists） | list literal 格式不合法，或包含非字串元素；不私自按逗號切分 |
| flag_*_unavailable | 對應欄位缺失／無法解析，或 list 為空；不自動填補。target 特指沒有候選標籤 |
| flag_software_only_heuristic | 上述軟件類啟發式規則，只標記 |
| flag_non_usd_or_unknown_currency | currency trim / upper 後不是 USD，含 null |
| flag_price_invalid_or_missing | 原 price 無法轉成有限非負數值 |
| flag_free_price_conflict | Free=True 且原 price>0，或 Free=False 且原 price=0；不是已證實錯誤，可能需核對折扣等來源語義 |
| eligible_base | 所有 exclude_* 均為 False |
| eligible_labelled | eligible_base 且 target 可用；**不是 train/test 分組** |
| first_exclusion_reason | 按上述 exclude 順序，第一個命中的規則；無排除則 retained；用於可加總流程數字 |

`rule_counts.csv` 的 affected_all_input_rows 是各條規則獨立命中的列数，可重疊，不可相加；first_exclusion_rows 互斥，可相加得到排除總數；affected_retained_rows 是保留基本 cohort 內仍有的問題。欄位旗標未必抄入 candidate 檔，使用時須以 app_id join ledger。

原始評論、owners、installs、評分、CCU、遊玩時長等結果欄不應混進特徵矩陣。這些 candidate 檔包含 target，**不可把整個檔案直接傳入模型**；下一步仍須建立預測特徵白名單和 developer 群組 split。Free/price 的 5 筆衝突須先定處理政策，再做相關分析或模型。
