# 文獻對照 v1：研究工作筆記

查閱日 2026-10-06。本文件供學生理解及核對，不是可直接提交的論文段落。完整逐篇欄位見 [literature_matrix.json](literature_matrix.json) 和同名 CSV；沒有用摘要補造實驗細節。

本輪以 Steam popularity / owners prediction、Google Play game installs / success prediction、explanation evaluation 等字詞搜尋，再追到作者全文、出版社或 arXiv。納入 6 篇供目前決策使用；這是針對性檢索，**不是 systematic review，也不能證明原創性**。L4/L5 的閱讀深度有限，已逐項標明。Hu et al. 的 Steam 2024 paper 找到索引，但全文工具存取失敗，本輪不據其實驗數值下結論。一般 Android apps 與玩家流失／比賽勝負研究未當成同一 target 的直接比較。

| 文獻 | 本次核對重點 | 對目前 FYP 的影響 |
|---|---|---|
| [L1 De Luisa et al. (2021)](https://arxiv.org/html/2110.02896v1) | Steam 人氣研究使用上市後首月玩家數；不是本專案可取得的首發前輸入 | 明確區分歷史分類及前瞻預測；不直接比較不同 target 的分數 |
| [L2 Kerim & Genç（online 2022；期刊卷期 2025）](https://link.springer.com/article/10.1007/s00521-022-07154-z) | Apple 遊戲 metadata、複合指標及模型比較 | 可參考問題設計；不移植分數權重或稱 Android 標籤已被該研究驗證 |
| [L3 Muhtasim & Hossen (2024)](https://www.mecs-press.org/ijeme/ijeme-v14-n3/IJEME-V14-N3-2.pdf) | 平台、樣本及 feature 說明有內部矛盾 | 高準確率不能代替可重現的資料與評估程序；保留相關文獻身份但不作性能基準 |
| [L4 Kapoor & Narayanan (2023)](https://www.sciencedirect.com/science/article/pii/S2666389923001599) | ML 研究中的 leakage 與可重現性問題；本輪限摘要層次 | 保留資料／程式版本、特徵來源及切分紀錄，避免過度解讀模型 |
| [L5 Tintarev & Masthoff (2012)](https://link.springer.com/article/10.1007/s11257-011-9117-5) | 解釋的不同目的不能混為同一項效果；本輪限出版社摘要 | 使用者評估分開量度任務正確性、完成率與滿意度 |
| [L6 Wardatzky et al. (2024), v1 preprint](https://arxiv.org/html/2412.14193v1) | 解釋評估的受試者代表性及報告問題 | 必須記錄招募和經驗背景；同學小樣本不能代表全體開發者 |

## 對研究問題的具體調整

以下是本專案的設計決定，不是文獻已替本資料證實的結論：

1. **RQ1：歷史關聯。** 在各自資料年份與明確 cohort 下，哪些規劃可描述的屬性與 owners／installs 分組有關？PC 主要分析限觀察價格 >0；不可解讀成某定價造成銷量增加。
2. **RQ2：未見 developer label 的泛化。** P 與 P+A 能否超過 majority／class-prior／age-only 基準？資料保存的是上市後 snapshot，故不聲稱真正 pre-launch forecasting。
3. **RQ3：規則與觀察條件敏感度。** 以相同群組分配檢查年齡限制、軟件類規則、PC 價格資訊及 Mobile 分級；不反覆挑選較好 test。
4. **RQ4：決策支援任務。** 系統是否帮助使用者找到可比作品、正確解讀歷史標籤、辨識不能支持的收入／因果結論？可用性及招募方案仍待實際安排，沒有宣稱做過 user study。

## 方法依據與實作分界

[scikit-learn 群組交叉驗證文件](https://scikit-learn.org/stable/modules/cross_validation.html) 支持同組分離的評估原則；[preprocessing 與 leakage 文件](https://scikit-learn.org/stable/common_pitfalls.html) 支持所有擬合轉換限制在訓練部分。本專案的 SHA-256 分組分配是自訂可重現實作，**沒有聲稱呼叫 sklearn GroupShuffleSplit**；實際比例不保證精確 70/15/15，也不保證逐類分層。

這一輪已在模型訓練前固定 target 定義、cohort、predictor allowlist、seed 及 split。這不等於外部預註冊：前面曾查看全資料分布。測試集可稱未用於擬合／調參的保留資料，不能稱全新收集的外部資料。

正式論文前仍需擴展 Android installs 的直接實證文獻，補讀 L4/L5 的完整方法，以及按導師要求整理引用格式。本輪已足以支持目前可逆的實驗設計，沒有把文獻數量或高分數當作研究品質保證。
