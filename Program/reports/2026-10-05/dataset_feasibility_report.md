# 遊戲開發決策支援系統資料集可行性報告

審核日期：2026-10-05（Asia/Hong_Kong）。本文件是可檢查的專案工作筆記，不是供直接提交的 FYP 論文。事實來自本地檔案全量檢查及已保存的來源 metadata；建議與尚未確認事項分開列出。

## 建議決定

**建議以 Artemiy 的 March 2025 full 作 PC 第一主候選，以 Google Play 的 2021 年保守遊戲子集作 Mobile 主候選，進入研究問題與清理規則確認階段。** 這是可行性建議，尚未替你或導師確定最終資料集／題目／target。

PC 建議從原版開始自行建立可追溯清理流程，作者 cleaned 版用於敏感度比較。理由是它有明確的 2025 年 3 月資料說明、47 欄、可用 genres/tags，以及可比較的 2024 版本。這不代表較新 FronkonGames 資料沒有價值，而是它的 CSV、JSON、Parquet 不同步，且資料時點與更新語義仍需較多核實。

Mobile 可支援歷史安裝量、類型與變現狀態研究；不能支援直接的營收預測或 2026 年即時市場機會判斷。若研究問題堅持「目前市場」或「未來收入」，現有核心資料不足，需另行收集適當資料。

## 主候選的實測結構

| 檔案／審核版本 | 行數 | 欄數 | 判定與用途 |
|---|---:|---:|---|
| FronkonGames 本地 CSV | 125,855 | 表頭 39；每行 40 | 有條件保留為替代／穩健性資料；需已核實的表頭解讀 |
| FronkonGames 本地 JSON | 141,335 | 42 欄＋AppID | 保留替代候選；精確原始版本與逐筆觀察時間未知 |
| FronkonGames HF Parquet | 124,146 | 41 | 暫緩作主資料，tags 全空且非 CSV 的完整替代 |
| Artemiy March 2025 full | 94,948 | 47 | 建議 PC 主候選；自行清理 |
| Artemiy March 2025 cleaned | 89,618 | 47 | 作者清理對照，非直接當作已驗證乾淨資料 |
| Artemiy May 2024 full／cleaned | 87,806／83,646 | 46 | 歷史穩健性候選，尚未建立縱向模型 |
| Google Play 全部 App | 2,312,944 | 24 | 篩選來源，不能把全數當作遊戲 |
| Google Play 保守遊戲子集 | 328,513 | 24 | 建議 Mobile 主候選，不含 Sports |
| Sports 歧義子集 | 47,483 | 24 | 獨立保留，需額外 type/genreId 證據才納入 |

檔案 bytes、SHA-256、來源、授權、版本證據見 `dataset_inventory.csv`。CSV 用嚴格 UTF-8 解碼及 CSV parser 檢查所有記錄，不以換行數推算行數；巢狀 JSON 採串流讀取。

## Steam 格式和版本差異

**事實**：原 CSV 全部 125,855 行均有 40 個值，表頭只有 39 個名稱。`DiscountDLC count` 應拆為 `Discount`、`DLC count`，其依據為原作者目前匯出程式的欄位順序，以及本地 JSON 的 AppID 對齊比較。共檢查 2,642,955 個純量值，未發現不一致。原檔未修改，只在審核讀取時提供 40 個欄名。

**事實**：本地 CSV 的 SHA-256 為 `1b48008b01a799d82385d6e66ba0cb65dd477b6aa4b6c2ec8c443025ab6880ad`，與 HF revision `ba4e26785af33bee500e96597068c6e77f4edea9` 所列 `games.csv` 的 LFS SHA-256 相同。因此可以確認該 CSV 的位元組相同；不能由此斷言該 repository 內的 Parquet／JSON 也相同。

HF Parquet 只有 124,146 筆，全部 AppID 可在本地 CSV 找到，少了 1,709 筆。在共有記錄上，owners、price、positive、negative、release date 均一致；name 有 59 筆字串不同。兩份資料的文字及集合欄位有不同序列化方式，`aligned_value_comparison.csv` 明確區分數字、布林與字串比較，不能把所有字串差異都解讀為內容更新。

HF Parquet 的 124,146 筆 tags 全為空陣列；本地 CSV 則有 42,502 筆 tags 缺失，其餘存在標籤。HF dataset card 宣稱的 143,395 筆也不是所下載 Parquet 的行數。Repository 更新日不可等同每個檔案的採集日或同步更新日。

本地 JSON 有 141,335 筆，比 CSV 多 15,480 筆；全部 CSV AppID 均存在於 JSON。JSON 不等於該 HF revision 的遠端 JSON（雜湊及大小不同）。本地 CSV 和 JSON 都含 1 筆晚於本次審核日的 release date。這些情況要求保留版本區別及篩選紀錄，不能只使用「Steam Games Dataset」一個名稱。

## 資料品質及樣本界定

- PC 主候選 AppID 沒有重複，完整列也沒有重複。但標題有 755 筆重複超額；同名不一定是同一遊戲，不能依 title 直接去重。
- March 2025 full 有 5,441 筆空 genres、22,117 筆空 tags。`num_reviews_total`／`pct_pos_total` 各有 39,575 筆 -1；對這些欄位，零缺失率不代表完整。
- 作者 cleaned 比 full 少 5,330 個 AppID；其中 5,218 筆標題含 playtest/demo，5,229 筆 genres 為空。這两個集合互相重疊，不能相加。兩版共有 ID 的逐欄差異已另行比較；作者所有清理決策及判定依據仍未完整取得。
- Google Play 的 Sports 同時是 App 及 Game 類別，官方文件及本地標題樣本均支持此歧義。16 個其餘遊戲標籤得到 328,513 筆；含 Sports 的寬鬆候選為 375,996 筆。這是 category-based 篩選，不是人工驗證每個產品，仍可能有錯誤分類及漏收。
- 保守手機子集中有 81 筆 Minimum Installs 缺失，6,930 筆 Rating／Rating Count 缺失，110,027 筆沒有評分支持量。免費／付費與價格、安裝標籤與下界、release/update 與 scrape 的交叉檢查已執行；不一致計數見 `cross_field_checks.json`。
- `proposed_cohort_counts.csv` 記錄逐步篩選的影響。示範規則下，March 2025 full 保留 89,450 筆；Mobile 要求已知 title、安裝下界及合理發行日期後保留 318,298 筆。這些尚非最終訓練樣本，也未保證全為正式遊戲；名稱 heuristic 及排除缺失日期需要敏感度分析。

所有 null、空白字串及文字 `nan/none/null/n/a` 在本次 profile 中視為缺失；`[]`／`{}` 另列 empty collection。零值不自動視為缺失。數值欄 invalid 包括不可解析、非有限、負值及指定範圍超界；無領域規則的欄位留空而非填零。`unique_nonmissing` 對列表是整個序列化值的基數，非拆解後單一 tag 的基數。

## 補充資料

| 候選 | 建議 | 原因 |
|---|---|---|
| Nik Davis Steam 2019 | 接受為歷史補充 | 27,075 筆主表，18 欄；太舊，不宜描述目前 PC 市場 |
| Game Recommendations on Steam | 接受為按需補充 | 50,872 筆產品、14,306,064 位用戶、41,154,794 筆推薦；推薦 CSV 沒有 review text，不能直接作文本情緒分析 |
| RAWG Hugging Face | 暫緩 | 已保存來源及 revision；本次只核對 metadata，未下載全量，未證明 join 品質 |
| Steam Reviews Hugging Face | 暫緩 | repository 約 23.46 GB；card 稱 1.13 億評論；本次沒有下載全量或驗證行數，後續只考慮有研究目的的固定抽樣 |

已計算部分本地資料的 AppID 重疊，見 `supplementary_join_coverage.csv`。AppID 可連接不代表可忽略時間差、產品類型、授權或欄位意義。

## 來源與認受性證據

以下為 2026-10-05 保存的 Kaggle API metadata，均超過 1,000 次下載。這證明使用量指標達到背景文件提到的偏好，不代表導師正式接受或資料必定可靠。

| 資料集 | Kaggle 累計下載數 | 平台列示授權 |
|---|---:|---|
| [fronkongames/steam-games-dataset](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) | 38,655 | MIT |
| [artermiloff/steam-games-dataset](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset) | 10,848 | MIT |
| [gauthamp10/google-playstore-apps](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps) | 35,957 | Database: Open Database, Contents: Database Contents |
| [nikdavis/steam-store-games](https://www.kaggle.com/datasets/nikdavis/steam-store-games) | 39,621 | Attribution 4.0 International (CC BY 4.0) |
| [antonkozyriev/game-recommendations-on-steam](https://www.kaggle.com/datasets/antonkozyriev/game-recommendations-on-steam) | 21,740 | CC0: Public Domain |

HF Steam／RAWG／Steam Reviews 的近月下載數分別為 2,076／305／2,102；此期間口徑與 Kaggle 累計數不同，不能直接排名。每個 remote file 的 inventory 列重複 repository 下載數，不應加總。來源說明已保存在 `data/raw/source_metadata/2026-10-05/`；下載量及平台 metadata 的保存日與原始資料採集日分開記錄。

Steam 上游為 Steam Store API／SteamSpy；Google Play 為作者從 Google Play 抓取的 2021 年截面；RAWG card 指向 RAWG API；Steam Reviews card 指向 Kaggle kieranpoc 原資料，列示 CC BY-NC 4.0。本次記錄發布者的授權聲明，未將 hosting 平台當作原始資料生產者，也未推定發布者授權可覆蓋所有第三方內容。

尚未做正式文獻檢索或逐一驗證其他研究採用情況；下載數不可替代文獻支持。Steam HF 頁面有 DOI `10.57967/hf/0511`，但 DOI 不代表所有 revision／檔案相同。

## 對研究及程式設計的影響

**建議**：將共同問題界定為「歷史同類遊戲的市場觸及與口碑基準，如何支援早期規劃」。PC 與 Mobile 共用研究及 UI 框架，但分開資料時期、target 與模型。使用者可選平台及規劃條件，查看相似產品、觀察分布、支持樣本量與限制；若模型通過評估才加入校準過的預測區間／機率。

**假說，尚未驗證**：genre、價格狀態、語言及變現狀態與表現代理指標可能有關。關聯不等於改變定價或加入 IAP 會造成業績提升。品牌、行銷預算、開發品質與曝光資源等重要因素缺失。

**主要限制**：單一截面有存活者偏差及不同上市時間的累積曝光差；Steam 部分欄位混合來源及更新時點。2021 Mobile 和 2025 PC 不能用絕對數值直接比較平台前景。以名稱排除 demo/playtest 只是可檢查的啟發式，不能保證正式發行身份。

候選 target、洩漏欄位、baseline、評估指標及群組／時間切分建議詳見 `target_feasibility.md`。未訓練任何模型，也未生成「哪種遊戲必定成功」的結論。

## 重現方法與仍待確認事項

環境及完整指令見 `Program/README.md`。依賴由 `uv.lock` 固定。原本 `Dataset/` 保持原位且只讀，以全檔 SHA-256 記錄；新增的 HF 原始下載放在 `Program/data/raw/`，審核用 Parquet 在 `data/interim/`，沒有建立 final cleaned data。DuckDB 記憶體上限設為 4 GB、2 threads，必要時寫入磁碟暫存；這不是整個 Python 程序的絕對記憶體上限。

審核所有本地 CSV；兩個 JSON 的檢查程度在 inventory 標明；ZIP 只列出成員及計算 archive 雜湊，未重複解壓並 profile 每份副本。RAWG／HF Reviews 僅 metadata。所有 row count／缺失／基數與 key 檢查皆為全檔，不是抽样推估；外部資料 card 的聲稱另行標示。

**未解決但已明確記錄**：原本 Kaggle 下載的精確版本號及日期；FronkonGames 各記錄的採集時點；Maximum Installs、0 - 0 owners 及部分零值／-1 的生成語義；作者完整清理規則；導師對雙平台及歷史資料的接受程度；最終研究問題、target、模型及應用框架。這些未知不妨礙本次審核，但會限制後續建模與最終主張。

## 來源連結

- [固定 Steam HF revision](https://huggingface.co/datasets/FronkonGames/steam-games-dataset/tree/ba4e26785af33bee500e96597068c6e77f4edea9)
- [Steam 作者匯出程式](https://github.com/FronkonGames/Steam-Games-Scraper/blob/main/ConvertToCSV.py)，本次副本另存，main URL 本身非版本固定。
- [Google Play 原作者 repository](https://github.com/gauthamp10/Google-Playstore-Dataset)
- [Google 官方 App 與 Game categories](https://support.google.com/googleplay/android-developer/answer/9859673?hl=en)
- [HF 下載數計算說明](https://huggingface.co/docs/hub/datasets-download-stats)
- [RAWG 固定 revision](https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset/tree/d9f5c486875b6309255b5fb10709480ace0eede7)
- [Steam Reviews 固定 revision](https://huggingface.co/datasets/adde023/steam-reviews/tree/d0ec12b33dffb8109b683b2e07780e2fc6b97187)
