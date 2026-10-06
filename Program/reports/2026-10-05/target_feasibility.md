# 預測目標可行性審核

審核日期：2026-10-05（Asia/Hong_Kong）。這是工作筆記及方法建議，並非已完成研究的結論或提交稿。尚未訓練模型，尚未選定最終 target。

## 已測得的 PC 分布

| 審核版本 | 記錄數 | owners 為 0 - 0 | 正負評論合計為零 | CCU 為零 | 至少 50 則正負評論 |
|---|---:|---:|---:|---:|---:|
| `fronkon_local` | 125,855 | 24,579 | 42,899 | 106,175 | 30,624 |
| `fronkon_json` | 141,335 | 38,445 | 58,353 | 121,646 | 30,637 |
| `fronkon_hf` | 124,146 | 23,033 | 41,195 | 104,468 | 30,621 |
| `artem_games_march2025_full` | 94,948 | 13,656 | 22,300 | 76,008 | 27,141 |
| `artem_games_march2025_cleaned` | 89,618 | 8,418 | 17,055 | 70,698 | 27,078 |

### Estimated owners

**事實**：March 2025 full 有 81,292 筆非零區間；13,656 筆為 `0 - 0`；格式錯誤或上下界顛倒為 0。逐區間分布見 `owners_distribution.csv`。

**解釋與未知**：它是 SteamSpy 估算區間，不是官方銷量。`0 - 0` 的資料生成原因未充分確認，不能當作零銷量或失敗案例。把區間中點當真實數量會引入人為精確度。免費遊戲 owners 也不等於付費購買者。

**候選方案**：先評估非零區間的有序分類，對細分類與合併類別做敏感度分析。門檻須有研究問題依據，不能挑選令 accuracy 較高的門檻。排除未知區間會改變樣本組成，須報告排除比例及類型分布。

### 評論量與口碑

**事實**：March 2025 full 的 `positive + negative` 中位數為 11，零值 22,300 筆。所有候選的分位數見 `target_statistics.json`。

**候選方案**：評論量可用作歷史曝光／參與程度代理；比較 `log1p` 回歸及分級分類。不得稱為收入或商業成功。以評論量作 target 時，排除 positive、negative、recommendations、review counts 及由它們計算的比例等結果欄位作輸入。

口碑可用正評比例作次要結果，但零評論時比例未定義。至少 10／50／100 則評論的樣本量已計算；50 並非既定採用門檻。小樣本比例必須考慮不確定性或平滑，且門檻會造成選擇偏差。

**資料問題**：March 2025 full 的 `num_reviews_total` 與 `pct_pos_total` 各有 39,575 筆 -1；這是無效領域值／疑似缺失標記，尚不可當作有效評論數或比例。`required_age` 有 1 筆 -1，零值也不能解讀成玩家平均年齡。

### CCU、遊玩時間及複合成功分數

March 2025 full 的 CCU 零值比例為 80.05%。CCU 的時間窗口及更新方式尚待確認，因此不建議作唯一主 target。遊玩時間也需釐清單位、採樣及零值語義。

目前不建議建立複合成功分數：owners、評論量、CCU、評分不代表同一結果，任意加權欠缺效度證據，亦可能把同一人氣訊號重複計算。

## 已測得的手機遊戲分布

**事實**：從 2,312,944 筆 Google Play 應用記錄中，以 16 個明確遊戲 category 標籤保留 328,513 筆。另有 47,483 筆 Sports 標籤記錄混有遊戲及一般體育 App，獨立存放於審核中間資料，不納入保守樣本。

- `Minimum Installs` 缺失 81 筆，零值 984 筆；中位數 1,000。
- 三級範例（尚未定案）：少於 1,000 為 156,155 筆，1,000 至低於 100,000 為 119,905 筆，至少 100,000 為 52,372 筆，另有 81 筆缺失。這是原始保守樣本分布，並非完成所有 cohort 規則後的訓練類別比例。
- `Rating` 及 `Rating Count` 各缺失 6,930 筆；110,027 筆評分與評分數同時為零。不能把未獲評分解讀成極差口碑。
- `Installs` 移除逗號及 `+` 後，與 `Minimum Installs` 的不一致數為 0。它們並非兩個獨立訊號。
- `Maximum Installs < Minimum Installs` 為 0 筆，但 Maximum Installs 的上游定義仍未核實，不能僅憑欄名宣稱它是區間上界或官方精確下載次數。
- 原始發行日期缺失 10,213 筆；觀察日期為 2021-06-15 至 2021-06-16。這是歷史截面，不能稱為 2026 年市場。

**候選方案**：以可解釋的安裝量分級作 Mobile 主 target 候選；保留原始 `Installs` 標籤，將 `Minimum Installs` 視為公開分級的下界。`Maximum Installs` 暫不作主 target。Rating 可作具評分支持量要求的次要分析。

## 決策時點與洩漏控制

系統定位是早期開發規劃。特徵須依「使用者當時能否知道」審查，不能只依相關性挑選。

| 特徵群 | 預定用途 | 限制 |
|---|---|---|
| Genre/category、擬定內容分級、平台與語言 | 開發規劃輸入候選 | 當前資料值可能經上市後更改；內容分級不代表實際受眾人口 |
| Price、free/paid、ads、IAP | 歷史同類產品比較 | 觀察到的是快照狀態，並非已證實的首發策略；不能做因果最佳化 |
| Owners、CCU、評論、評分、遊玩時間 | 結果／描述性基準 | 原則上不輸入早期預測模型 |
| User tags | 描述或敏感度分析 | 可隨上市後回饋形成，不能默認首發前可得 |
| Developer/publisher | 群組切分、解釋候選 | 高基數及同公司洩漏風險；名稱不能直接當業績能力 |
| Release date、上市至快照時間 | 控制曝光期及分層 | 不得以未來才能知道的累積結果宣稱上市前預測 |

## 評估設計建議

1. 先界定 cohort、target、資料時點及最低支持量；再劃分資料。所有編碼、缺失處理、類別合併及調參只在訓練資料擬合。
2. 分類比較 majority baseline、簡單線性／有序模型與少量樹模型；報告 macro-F1、balanced accuracy、逐類 recall、混淆矩陣。有序 target 另報有序誤差；需要機率輸出時檢查校準。
3. 回歸比較中位數 baseline 與少量候選模型；同時報告原尺度 MAE、對數尺度誤差及分組表現，不能只看 R²。
4. 評估 release-cohort 切分及 developer/publisher 群組切分。單一截面的 release-year holdout 並不自動等於真實前瞻測試；2024／2025 快照可研究時間穩健性，但須先審核同 AppID 的特徵時點。
5. 使用固定 seed 42，固定測試集；報告不確定性、零值／缺失處理及不同樣本篩選的敏感度。
6. PC 與 Mobile 以同一研究框架分別評估，不直接合併 owners 與 installs，不以不同年份截面比較哪個平台較賺錢。

**需要決定但本次未代為定案**：PC 以 owners 區間還是評論量為主、Mobile 分級門檻、是否接受歷史決策支援定位、導師是否批准雙平台範圍。

來源：本地全檔審核輸出；[Steam dataset source](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset)；[Google Play dataset source](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps)；[Google 官方 App/Game 類別](https://support.google.com/googleplay/android-developer/answer/9859673?hl=en)。
