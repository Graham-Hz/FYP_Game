# Chapter 1：已核對的引用資料

核對日期：2026-10-08。供建立 ACM author–year References，並非 report 正文。最終 References 按作者姓氏排序；每個正文引用須與同一版本／年份的條目一致。

## 五項研究：bibliographic records

**De Luisa et al. (2021)**

Andraž De Luisa, Jan Hartman, David Nabergoj, Samo Pahor, Marko Rus, Bozhidar Stevanoski, Jure Demšar, and Erik Štrumbelj. 2021. Predicting the Popularity of Games on Steam. *Elektrotehniški vestnik* 88, 4 (2021), 151–162. [Publisher PDF](https://ev.fe.uni-lj.si/4-2021/Luisa.pdf).

期刊卷期及頁碼由原文首頁核實。原 matrix 閱讀的是 [arXiv v1](https://arxiv.org/abs/2110.02896v1)；`10.48550/arXiv.2110.02896` 是預印本 DOI，不是已核實的期刊 DOI，勿混用。

**Kapoor and Narayanan (2023)**

Sayash Kapoor and Arvind Narayanan. 2023. Leakage and the reproducibility crisis in machine-learning-based science. *Patterns* 4, 9 (2023), Article 100804. [DOI](https://doi.org/10.1016/j.patter.2023.100804).

出版者登錄的 [Crossref metadata](https://api.crossref.org/works/10.1016/j.patter.2023.100804) 核實作者、期刊、卷期及 article number。此次 PMC／出版者全文頁存取有限；核對 metadata 不等於完整批判性閱讀。

**Kerim and Genç (2025)：建議採用正式卷頁年份**

Abdulrahman Kerim and Burkay Genç. 2025. Mobile games success and failure: mining the hidden factors. *Neural Computing and Applications* 37 (2025), 543–557. [DOI](https://doi.org/10.1007/s00521-022-07154-z).

[Publisher record](https://link.springer.com/article/10.1007/s00521-022-07154-z) 同時列出 online publication 2 April 2022，以及 issue January 2025；其 “Cite this article” 使用 2025。正文建議改成 Kerim and Genç (2025)。若明確採用 online-first 2022 記錄，須一致標示該版本。研究使用 Apple App Store，不能當作 Android installs 標籤的直接驗證。

**Tintarev and Masthoff (2012)**

Nava Tintarev and Judith Masthoff. 2012. Evaluating the effectiveness of explanations for recommender systems: Methodological issues and empirical studies on the impact of personalization. *User Modeling and User-Adapted Interaction* 22 (2012), 399–439. [DOI](https://doi.org/10.1007/s11257-011-9117-5).

標題及副標題、作者、年份、卷頁由 [publisher record](https://link.springer.com/article/10.1007/s11257-011-9117-5) 核實。不自行補未在本輪核實的 issue number。原 matrix 只讀 abstract／metadata；不能宣稱已重現或完整審查其實驗方法。

**Wardatzky et al.：兩個版本必須分清**

目前實際閱讀的版本：

Kathrin Wardatzky, Oana Inel, Luca Rossetto, and Abraham Bernstein. 2024. Whom do Explanations Serve? A Systematic Literature Survey of User Characteristics in Explainable Recommender Systems Evaluation. *arXiv preprint*, arXiv:2412.14193v1 (12 December 2024). [Version 1](https://arxiv.org/abs/2412.14193v1). [arXiv DOI](https://doi.org/10.48550/arXiv.2412.14193).

**本輪新核實的正式出版版本**：

Kathrin Wardatzky, Oana Inel, Luca Rossetto, and Abraham Bernstein. 2025. Whom do Explanations Serve? A Systematic Literature Survey of User Characteristics in Explainable Recommender Systems Evaluation. *ACM Transactions on Recommender Systems* 3, 4 (2025), 35 pages. [Journal DOI](https://doi.org/10.1145/3716394).

出版者提交的 [Crossref record](https://api.crossref.org/works/10.1145/3716394) 列出卷 3、期 4、pages 1–35、online date 10 April 2025、print date 31 December 2025；[作者的補充資料](https://zenodo.org/records/14771123) 同時連到預印本及此 journal DOI。ACM 頁本輪未成功直接載入；Crossref 未提供 article-number 欄位，因此這裡不猜文章編號。最終排版可用 ACM 官方 citation export 補全編號。

建議先對照正式版相關段落，再在正文與 References 採用 2025 期刊條目。若仍引用已讀 v1，2024 預印本條目可以保留，但不能聲稱該研究尚未有正式出版版。arXiv v2 是 3 February 2025，也不等於上述期刊版本。不要同時列两條而未說明正文各自引用甚麼。

## Dataset source references

以下年份指本研究使用的 dataset snapshot／version 年份，不宣稱是最初建立日期。

Artemiy Ermilov. 2025. *Steam Games Dataset 2025*. Kaggle dataset, March 2025 snapshot. [Dataset page](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset).

Gautham Prakash. 2021. *Google Play Store Apps*. Kaggle dataset, June 2021 collection. [Dataset page](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps). [Collector repository](https://github.com/gauthamp10/Google-Playstore-Dataset).

作者名稱及版本日期取自本地已保存的 Kaggle API metadata：`../../data/raw/source_metadata/2026-10-05/kaggle_artermiloff__steam-games-dataset.json` 與 `kaggle_gauthamp10__google-playstore-apps.json`。Steam lastUpdated 2025-03-13；Google Play lastUpdated 2021-06-17，後者不等於每列採集日。Metadata 保存日期 2026-10-05；若引用格式需要 access date，應用实际查閱該來源日期，不能把版本更新日當作查閱日。

Background 說明資料來源時加入引用；Method/Data 另寫確切本地檔名、取用版本、SHA-256、篩選規則和觀察時間。Steam／Google Play 是平台，不應取代整理發布這兩個 CSV 的資料提供者名稱。HF 並非當前主分析來源，不要混寫。

## 引用支援範圍與待辦

- De Luisa：上市後首月訊號與其後 popularity；不是上市前成功保證。
- Kerim：Apple metadata／構建成功指標；不能直接驗證 Android install tiers。
- Kapoor／Narayanan：資料洩漏及可重現性；不能因引用它就宣稱本研究完全無偏差。
- Tintarev／Masthoff：解釋效果與滿意度的區別。
- Wardatzky：受試者特徵、代表性及可推廣性；不證明本專案介面有用。
- 尚未新增可靠、直接匹配 Android installs 任務的實證研究；保留 targeted review 限制。正式提交前仍要閱讀並核對最終引用版本。

本次僅新增出版 metadata 核對，沒有默默修改 2026-10-06 的歷史 matrix 或其 reading-depth 紀錄。
