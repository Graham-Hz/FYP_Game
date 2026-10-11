# 課堂內容與 FYP 對照

日期：2026-10-11。用途：學習及研究規劃紀錄，不是提交用的 report 正文。

## 結論與閱讀範圍

三科都能支援這個 FYP。最值得直接使用的是 COMP3115 的資料前處理、EDA、視覺化和模型評估觀念，COMP3925 的 Power Query、資料表關係及 DAX，以及 COMP1016 對抽樣、統計量和推論假設的理解。先把已完成的工作解釋清楚，再補有實際用途的呈現及相似遊戲參考；不需要為了列出更多課堂方法而增加模型。

已建立所提供文件的內容索引：42 份 PDF 共 1,741 頁，另有 5 份 PPTX、12 份有效 DOCX、2 份 notebook 及 7 個 ZIP。PDF 包括講義、tutorial 答案及 lab，不等於 42 個獨立課題。COMP1016 的若干 lab／答案有重複版本。閱讀方式是逐講檢視章節與文字內容，對下列直接影響 FYP 的方法、假設及 Power BI 練習作重點細讀，並視覺核對部分公式／關係圖。不是每道習題、每張 screenshot 或每行示範程式都已重新驗算。

兩段 tutorial MP4 沒有播放；軟件隨附的 DLL、EXE、headers 等不當作課程內容；Word 的 `~$` 暫存檔不作來源。課程材料及全文擷取留在 `My_FYP` 以外，不把整份講義複製入 GitHub。清單及檔案 hash 見 [source_inventory.json](../2026-10-11/lecture_review/source_inventory.json)。下文頁碼指 PDF 檔案第幾頁；不以投影片頁腳推算。

## COMP1016 Mathematical Methods for Business Computing

| 課題及來源 | 實際內容 | FYP 用法與判斷 |
|---|---|---|
| L00、L01 | 描述／推論統計、類別與數值資料；隨機變數、期望與變異、geometric／binomial／normal distribution | 用來解釋資料型態和 outcome 分布。Owners 區間及 installs 下界不等於精確連續銷量；不能為了套模型而改成真實收入 |
| L02 pp. 4–13、24–44 | sampling frame、convenience／random／stratified／cluster sampling；sampling distribution、CLT | **直接適用**：Kaggle 快照的涵蓋範圍／選擇偏差；developer group split 是防止相關樣本跨 partition，不等於取得了全市場隨機樣本 |
| L03 pp. 4–33、35–44 | point／interval estimation、confidence level、z／t、比例 CI、樣本量 | **觀念適用，公式不可直接搬**：目前 fold SD 不是 CI；樣本大不會自動消除偏差及同 developer 的相依性 |
| L04、L05 | H0／H1、p-value、Type I／II error；單／雙樣本平均、比例、paired t、F-test | 後續若有使用者任務時間或同一人的前後比較，可以先設計量度與假設。現階段不對三折 CV 分數直接做一般 t-test 宣稱優勝 |
| L06 pp. 2–12 及後續例題 | experimental design、one-way／two-way ANOVA、interaction | 可幫助理解混雜與交互作用，但不能把 O1/O2/O3 編成 1/2/3 後做 ANOVA，聲稱平均「成功程度」有差異 |
| L07 pp. 4–8、19–25 | contingency table、chi-square goodness-of-fit／independence；expected frequencies、獨立及互斥假設 | **列聯表／比例直接適用**；例如 Android category × install tier。正式 p-value 需另訂分析單位與假設；Steam 多 genre 展開後不符合「每列互相獨立、類別互斥」的簡單設計 |
| L08 pp. 4–9、19–21 | Wilcoxon rank-sum／Mann–Whitney；Kruskal–Wallis（部分標 reference）；signed-rank 明示未涵蓋 | 暫不新增檢定。Nonparametric 不代表沒有假設；非同形狀分布的比較不能一概解讀成只比較中位數 |
| L09 pp. 3–9、18–37 | simple linear regression、least squares、residual diagnostics、R²、slope inference | 理解回歸與分類的區別。現有 Logistic Regression 是分類器，不是這課的 simple linear regression；不要用 R² 作本 FYP 分類主指標 |
| L10–L12 | 線性方程、Gaussian／Gauss–Jordan elimination、矩陣運算／逆／determinant、vectors、dot product、norm、distance、linear transformation | 支援理解編碼後的 feature matrix、線性分類和相似度。无需在產品另外加入「矩陣求逆」功能 |
| L13 pp. 2–20 | bonus／reference：LU 等 decomposition、word／image embedding、cosine similarity、LLM 概念 | 相似度觀念可用；目前不需要額外加入 image model／LLM／embedding pipeline |

Lab 1–2 練習 Python、NumPy／Pandas 和資料來源；Lab 3 是描述統計、查詢和繪圖；Lab 4 是機率、CLT、CI 和檢定；Lab 5 是雙樣本、chi-square、ANOVA；Lab 6 包括 Excel／Python linear regression，以及 exponential smoothing 等 forecasting；Lab 7 在 ZIP 內，是線性方程及矩陣。股票／forecasting 示範的時間序列條件不能直接套到我們的一次市場快照。

## COMP3115 Exploratory Data Analysis and Visualization

| 講義 | 主要內容 | 與目前工作的關係 |
|---|---|---|
| Lecture 1 pp. 3–4、35–72 | EDA 與 confirmatory analysis 分別；feature types、mean／median／mode、variance／SD、quartiles、IQR、outliers | 已有 train-only class balance、子組比例、age quantiles、missingness。宜補上可核對的圖表；高 owner／install 值可能是真實長尾，不能只因超過 1.5 IQR 就刪除 |
| Lecture 2；Lecture 3 pp. 3–24、31–58 | Python basics；NumPy arrays／masking／aggregation；Pandas Series／DataFrame、CSV、group summaries、Matplotlib | 已用於資料整理、驗證及模型結果匯總。不需要改用 notebook 才算運用課堂知識 |
| Lecture 4 pp. 3–18、27–42 | missing／noisy／inconsistent data、imputation、binning、one-hot、normalization | 已實作保留 missing／unknown、型態驗證、fold 內 median／scaling／類別編碼。FYP 加入了課堂示範以外的 leakage 控制；不能先對全部資料 fit preprocessing 再切分 |
| Lecture 4 pp. 43–54 | optional text mining：tokenization、stemming、vector space、TF–IDF | 暫不加入。需要新的文字資料品質檢查、feature policy 和實驗理由；課堂可選內容不等於 FYP 必做 |
| Lecture 5 pp. 15–58 | histogram、bin width／density、boxplot、probability／Q–Q plot、scatterplot、scatter matrix、line chart | age band／price distribution 可以使用。類別 outcome 宜用 count／比例圖；按 release year 分組不等於同一市場隨時間的銷量走勢 |
| Lecture 6 pp. 6–59、67–87 | 選圖、bar／dot／slope／small multiples、benchmark、100% stacked bar；互動、色彩、可讀性、dashboard layout | **優先加入 Power BI**：數量卡、分級比例、同平台條件篩選、工具提示、清楚年份與分母。不同平台不放成可直接比較的「成功率」排行榜 |
| Lecture 7 | univariate／multivariate linear regression、loss、gradient descent、normal equation | 支援理解 fitting／features／loss，但不是現有 Logistic Regression 的完整教材 |
| Lecture 8 pp. 6、12、17–43、47–65 | classification pipeline、perceptron、MLP、activation／backpropagation、under／overfitting | 分類與模型複雜度觀念已用到。Random Forest／Gradient Boosting 在 p.12 overview 出現，並非整份講義詳細實作的主題 |
| Lecture 9 pp. 6–32、34–47 | SVM／margin／kernel；k-NN、distance、cosine／Jaccard、選 k、cross-validation、normalization | 固定 train folds 與保留 test 符合評估思路，FYP 再加入 developer groups。**相似遊戲參考可用 nearest-neighbour 思路和集合相似度**；不需要因此再訓練一個 k-NN 分類器 |
| Lecture 10 pp. 10–18、30–46、50–63 | K-means、initialization、elbow、限制；hierarchical clustering／linkage；GMM／kernel 延伸 | 暫非必要。若未定義「分群支援甚麼決策」，多一個 cluster 圖不會自然提升 FYP |
| Lecture 11 pp. 23–24、35–61、63–73 | dimensionality reduction、PCA／covariance／eigenvectors／reconstruction、autoencoder | 暫不加。現有稀疏類別特徵仍可直接建模，降維會增加解釋及新評估工作 |

注意：Lecture 9 p.40 標題寫 Jaccard Distance，但展示的是 intersection / union，數值越大越相似；實作時應明確叫 **Jaccard similarity**，distance 才是 1 − similarity。Cosine 的圖亦展示 similarity。已視覺核對该頁；SciPy 的 [Jaccard distance 定義](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jaccard.html) 可作外部方法核對。

所提供內容中 Logistic Regression 在 Lecture 9 p.27 被提及；不能据此寫成課堂完整教授。現有 Logistic Regression、Random Forest 的具體方法仍需正式文獻／官方文件引用。Lecture 9 pp.45–46 展示 CV 選參數和獨立 test；我們的 group-aware 延伸可參考 [scikit-learn grouped CV](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)。

## COMP3925 Data Analysis Studio

| 來源 | 提供材料確實涵蓋 | 建議運用 |
|---|---|---|
| Topic 1 pp. 2–19、24–39 | Python data structures、資料型態與 acquisition→cleaning→transformation→analysis→storage；Power Query、欄位定義、型態、自訂欄位 | 把現有 Python pipeline 的已驗證輸出交给 Power BI；Power Query 負責載入、設定型態及顯示名稱 |
| Topic 2 pp. 2–14、16–33 | sets／JSON／API 圖像標籤示範；analytics categories、analyst tasks、Import／DirectQuery；headers、null、duplicates、pivot／unpivot | 採用本機 CSV Import；不需要照示範加入圖像標籤 API。歷史描述和後續模型研究要分清楚 |
| Topic 3 pp. 2–16 | requests／JSON read-write、Pandas、Seaborn、API exercise | 已有 CSV／JSON、Pandas 等實作基礎。新增資料來源需要真正研究理由，不因教過 API 就擴大爬取 |
| Topic 4 pp. 6–8、15–32 | virtual environments、Python／Power BI integration、Python visual 限制 | 保留目前固定環境；首版採原生 visuals，CSV 作介面，無需把訓練放進 Power BI |
| Topic2_PrepareData pp. 3–5；Topic2_LoadData pp. 3–11 | profiling、SQL／CSV／Excel 來源、欄位選取、expand／merge、unpivot、型態、Enable Load | 可直接練習可追溯 Applied Steps，不重新猜清理規則或把 unknown 改成 0 |
| Topic3_DesignDataModel pp. 2–4、8–16 | one-to-many、filter propagation、hierarchy、summarization、quick measures、bridge 與 ambiguity | **重要**：Steam game–genre 是多值關係，不能把展開後的列數當遊戲總數 |
| Topic3_DAXCalculation pp. 2–7、8–13 | calculated tables／columns、sort-by-column、measures、AVERAGE／MEDIAN／DISTINCTCOUNT／COUNTROWS、比例與 BLANK | 用 distinct game count、tier share、support warning；錯誤加總 percentage 或 price 的問題與課堂內容直接相關 |
| Topic4_DesignReport pp. 2–12、13–15 | slicers、visual fields、bar／column／matrix／cards、filters、cross-filter／tooltips、publish 示例 | 先做兩頁本機 report 及核對；service publishing 不是首版完成條件 |

Power BI 的 **data model** 在這些 labs 主要指 tables／relationships／measures，與 FYP 的機器學習 model 是兩件事。提供的 labs 列出十個課程系列名稱，但本 folder 沒有全部十個 lab 的內容；不能宣稱 Advanced DAX、RLS 等已完整閱讀。亦不推定 Topic 4 就是整科課程的全部內容。

## 採用次序及不增加的工作

1. **現在可做**：學生按 [Power BI 任務指引](powerbi_handoff_v1.md) 製作兩頁描述 report。我已提供四個 CSV、資料定義及核對數字；PBIX／DAX 和畫面仍需學生在 Power BI 實際操作與驗證。
2. **下一個產品功能可沿用課堂知識**：相似遊戲參考，先限定同平台及有支援的條件，使用 genre／function 集合相似度，展示相似原因及歷史結果。缺少 metadata 不當成真正相似；不能用 outcome／owners／installs 去定義相似，再宣稱可以支持早期規劃。規格、missing handling、排序和使用者驗證仍未完成。
3. **統計推論先定問題再做**：先有列聯表、支持量、age／free／paid 分層及敏感度。若加入 CI／正式 association test，需預先定義母體、獨立單位、developer 相依、effect size 及多重比較處理；cluster-aware uncertainty 是額外方法，不假稱為講義已教。現在不新增 p-value 結果。
4. **研究主線仍保留**：餘下 cohort／target sensitivity、group-versus-random diagnostic、final selection、calibration／test，之後才考慮模型接入。Power BI 不取代這些工作，也不重新選特徵或查看 held-out labels 來修圖。
5. **暫不新增**：ANN、SVM、K-means、PCA、TF–IDF、autoencoder、時間序列預測、圖像 API。它們有課堂基礎，但目前缺少優先於既定工作的必要性。

原有 FYP 方向不需重定：CSV 更新的系統繼續負責驗證、版本和互動比較；Power BI 先作分析及展示輔助。未承諾把 Power BI 嵌入產品或自動同步 application snapshot。

## 交付及完成界線

- [Power BI 手把手教學交接](powerbi_handoff_v1.md)：可以整份貼給另一個 ChatGPT。
- 資料在 `Program/data/processed/powerbi_v1/`，Git 已忽略；四個 CSV 包含 272,958 筆 game rows、143,472 個 game–genre pairs 及 33 個 genre labels。
- [匯出紀錄](../2026-10-11/lecture_review/powerbi_export_verification.json) 與 [獨立核對](../2026-10-11/lecture_review/powerbi_independent_verification.json)：已逐欄核對 frozen train、bridge pairs、CSV round trip。不是 Power BI 介面／DAX 執行驗證。
- `FYP_v1.docx` 未修改；課堂資料是學習來源，不取代 Chapter 1 related-work 的外部學術文獻。
