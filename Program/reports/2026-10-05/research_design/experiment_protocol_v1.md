# 實驗與系統評估 protocol v1

日期：2026-10-05。狀態：建議方案；實驗尚未執行。此文件把研究問題轉成可執行的評估設計，最終 cohort 與 split 仍待正式清理後鎖定。

## 任務與評估母體

PC 主候選是可用 estimated-owner 區間的三級分類；Mobile 主候選是安裝下界三級分類。兩者各自建立模型及指標，不合併標籤、不比較不同年份的絕對市場機會。評估只適用於所列母體，不能外推為新遊戲營收或前瞻六個月表現。

PC owners 未知不是負例，排除比例須按價格、上市年齡及 genre 報告。零價格記錄的可觀察性較低，預定另行報告且首版不提供該情境的商業機率。Mobile 免費產品 309,987 筆、付費 8,311 筆；分組評估不能用整體成績掩蓋付費產品的表現。

## 特徵與可用時點

主實驗分成兩個 feature sets：

- **P：規劃特徵**。PC genres、可規劃的遊戲功能、支援系統與語言、快照價格及零價格旗標；Mobile category、content rating、free、USD price、ad supported、IAP。這些是規劃可描述的產品屬性，但資料中的值仍是上市後快照，不是假定已存档的首發前值。
- **P+A：規劃特徵＋觀察年齡**。加入 release-to-observation days，衡量曝光期對歷史分类的影響。PC 用 2025-03-13 作參考代理；Mobile 用逐筆 Scraped Time。P+A 不能包裝成「上市後指定天數的預測器」，因為 outcome 並非統一追蹤期量測。

genre／language 採 multi-hot；类别詞彙、數值轉換及缺失填補只在訓練折擬合。高基數開發者名稱只用作群組切分，主模型不直接使用身份。PC user tags、required_age、DLC 數等先不納入 P：前者可能上市後形成，年齡限制大多為零，DLC 數受上市時間影響。

嚴格排除：AppID、產品名稱、評論／評分／recommendations、owners、安裝欄位、CCU、遊玩時間、Metacritic、外部人氣指標、由 target 衍生的分級。自身 target 欄及其組成欄不能流入特徵矩陣。名稱只可用於產品識別及清理檢查。Mobile 的 `Installs`、`Minimum Installs`、`Maximum Installs` 必須一起排除為輸入。

Pipeline 有助把訓練期轉換與測試資料分開，但它本身不能修正「特徵當時不可得」的問題。[scikit-learn 資料洩漏指引](https://scikit-learn.org/stable/common_pitfalls.html)

## 預定切分方式

**主要評估：開發者群組 holdout**。以 seed 42，近似 70% 訓練、15% calibration、15% 最終測試；實際比例由完整群組大小決定，不為了湊比例拆散群組。此時尚未產生 split。

- PC 同一產品可能有多名開發者，暫定 cohort 有 6,092 筆多開發者產品。先建立產品—開發者二部圖，以連通群組切分，避免只取第一位開發者而漏掉重疊。若大群組令切分不可行，先報告再調整評估母體，不隨機拆散群組。
- PC 有 121 筆沒有開發者。它們不能共用一個「Unknown studio」假身份，也不能宣稱是已證實的新工作室；群組 holdout 主評估排除並單獨計數。
- Mobile 用 developer_id 標籤。主 cohort 有 131,443 個標籤，最大標籤 1,333 筆；這不是經實體解析的公司身份，須把結論限定為未見過的標籤。
- 在訓練部分做 3-fold group CV 作有限調參。Calibration 部分只作機率校準及在規則內設定支持／拒答門檻；最終測試集不作特徵選擇、分級門檻調整或反覆挑模型。

另設 stratified random holdout 作對照，辨識群組重疊可能造成的樂觀差距。它不是另一個可以挑最好結果來呈現的主測試。[群組與一般交叉驗證](https://scikit-learn.org/stable/modules/cross_validation.html)

**時間穩健性**：release-year 分層只表示不同上市批次的歷史泛化。2024／2025 的 78,264 個共有 AppID 中，2,774 筆評論合計下降；35,026 筆正負評論完全相同。原因尚不明，不能先假定所有欄位同時重新抓取，也不建立銷售增長標籤。跨快照結果先作資料診斷，補足欄位時點證據後才設時間實驗。

## 最小實驗矩陣

| 編號 | 模型／比較 | 目的 | 主輸出 |
|---|---|---|---|
| E0 | Majority／class-prior baseline | 建立最低可比較基準 | 全套分類指標 |
| E1 | Age-only 簡單基準 | 檢查累積曝光本身能解釋多少 | 與 P+A 的差異 |
| E2 | 正則化 multinomial logistic regression，P 與 P+A | 可解釋且低複雜度的候選 | CV、holdout、係數穩定性 |
| E3 | 一個樹模型候選，例如 histogram gradient boosting，P 與 P+A | 檢查非線性增益 | 與 E2 同 split、同 features 的比較 |
| E4 | 最佳候選的群組／random 切分對照 | 檢查泛化與樂觀偏差 | 指標差距，不挑最好 split |
| E5 | 預先列明的 cohort／target 敏感度 | 檢查結論是否依賴清理選擇 | 三／四級、價格群組、180／365 日、軟件類別排除 |

E2／E3 是候選而非已選定最終模型；每類初始調參最多 8 個預先列明組合，記錄運算時間及失敗。先完成小矩陣，不以大量模型數量代替研究深度。

**指標**：主指標 macro-F1；輔以 balanced accuracy、每類 precision/recall/F1、混淆矩陣。Accuracy 僅輔助。類別有序誤差另外報跨一級／兩級比例，但三級間不是等距人數，不能把 label-index MAE 說成 owners 數量誤差。[評估指標文件](https://scikit-learn.org/stable/modules/model_evaluation.html)

模型若輸出機率，另報 log loss、明確定義的 multiclass Brier score（每筆對所有類別平方差求和再平均），並繪 reliability 圖；用未參與擬合的 calibration 資料校準，再在最終測試評估。[機率校準文件](https://scikit-learn.org/stable/modules/calibration.html)

比較同一測試樣本上的成績差異，按開發者群組做 paired bootstrap，暫定 1,000 次、seed 42；報告 95% 區間及有效重抽樣次數。若重抽樣缺某類，記錄並使用固定 label set，不默默移除較難類別。區間接近／跨越零時，報告證據不足，不宣稱模型優越。

## 何時可以放進系統

- 所有特徵、target、split 都能從固定資料重現；群組及 AppID 沒有跨 split 洩漏。
- 模型須在主要 holdout 上對最強適用基準有可解釋的改善，並且逐類及免費／付費子群表現可接受。不能先承諾 90% accuracy。
- 若模型沒有可靠改善，系統保留同類比較、分布及資料支持量，報告模型限制；不能把未通過的機率包裝成產品建議。
- 低支持量、未知類型、價格超出訓練支持範圍、未知幣別、PC 零價格等情境須有可測試的處理。擬議的 N<30 支持量門檻不是統計保證，亦需檢查相似度與分布偏移。

## 系統案例與使用者任務

至少建立下列功能案例：常見類型、罕見類型、沒有可比產品、極端價格、未知幣別、PC 零價格、Mobile ads/IAP 不同設定、缺失輸入、不同資料年份提示，以及匯出結果與介面數值一致。

RQ4 的使用者任務先準備四項：找到可比產品、比較兩個構想、解釋分級／樣本支持量、辨識不能由資料支持的收入／因果主張。若招募可行，將純 EDA 畫面与完整介面作順序平衡的任務比較，記錄完成率、時間、解讀正確率與質性回饋；樣本小則以描述結果報告，不宣稱普遍效益。

## 已探索資料的透明度

目前已看過完整候選資料的分布以決定研究設計；未來留出的測試集不是完全未接觸的原始資料。因此只能聲稱「未用其 outcome 擬合／調參的評估集」，不能聲稱這是未見過的新收集外部資料。完成設計後鎖定規則，再保留未參與模型選擇的 test；更強的外部前瞻驗證需要另行取得資料。
