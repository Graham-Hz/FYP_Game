# 研究設計來源與後續文獻工作

查閱日：2026-10-05。這是本輪實際查閱的來源紀錄，不是完整 literature review，也不證明本專案的原創性。

| 來源 | 本次查閱範圍 | 可支持的內容 | 不可據此推定 |
|---|---|---|---|
| [De Luisa et al. 2021, Predicting the Popularity of Games on Steam](https://arxiv.org/html/2110.02896v1)；[版本與 DOI](https://arxiv.org/abs/2110.02896v1) | 摘要、資料與方法相關段落、結論 | Steam 人氣已有相關研究；該研究使用上市後首月玩家數作重要輸入，並比較 Bayesian 模型 | 本專案已有真正上市前預測能力；已全面覆蓋相關文獻；本專案方法必定新穎 |
| [SteamSpy About](https://steamspy.com/about) | 估計方法、誤差及 owners 定義說明 | Owners 是帶限制的估計，取得遊戲不只包括一般 Steam 購買 | 本地 0 - 0 一定代表哪一種失敗；網站歷史介紹等於每個 2025 API 欄位的最新規格 |
| [scikit-learn Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) | 資料洩漏與 preprocessing | 轉換只在訓練部分擬合，pipeline 有助隔離步驟 | 使用 pipeline 就能消除上市後特徵或不當問題定義 |
| [Cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html) | 群組切分及一般切分 | 同群組資料可用 group-aware 方法分離 | 本地 developer 字串已是已驗證公司身份 |
| [Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html) | 分類及基準評估 | 不同分類指標回答不同問題；需建立 baseline | 預定 macro-F1 或 balanced accuracy 已達某數值 |
| [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) | 校準概念及校準資料獨立性 | 分類機率需另行評估校準 | 某個模型輸出 0.8 就等於已驗證 80% 的未來成功率 |

上述 stable 文件可能日後更新。正式實驗時須固定實際套件版本並記錄文件版本；本次未安裝建模套件。

## 尚待完成的文獻矩陣

每篇至少記錄：完整書目／DOI、資料来源及觀察年份、預測時點、可用輸入、target 定義、樣本及排除規則、切分方式、baseline、主指標、限制，以及與本專案的差異。

先覆蓋三類問題：Steam 歷史人氣／owners、Google Play 遊戲安裝／變現，以及可解釋決策支援的使用者評估。沒有看到全文及實驗細節時，不以摘要推斷其資料洩漏，也不宣稱自己的方案優於它。

Steam 官方 review 文件本輪有嘗試開啟，但工具讀取內容不足以核實本地兩組 review counts 的參數對應，因此沒有把 API filter 差異寫成已證實原因。仍需核對原收集程式、版本及參數。
