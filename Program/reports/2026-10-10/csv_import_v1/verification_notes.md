# CSV 匯入及應用資料版本 v1

2026-10-10。研究／工程紀錄，不是 report 提交正文。

已完成：兩平台標準 CSV contract、動態空白範本、既有來源轉換器、驗證／预覽、來源與品質記錄、不可覆寫版本儲存、啟用／切回、重啟保存選擇、比較／JSON 匯出版本綁定。全部在本機執行，既有研究環境 lock 未變。

## 驗證

- 全套 33 個 unittest 通過：包含舊資料清理／切分／前處理／比較測試，以及 11 個新增匯入測試。
- 新測試覆蓋 owners/install 邊界、缺失與 false、重複 ID、錯誤表頭／編碼／日期／數字、Free-price 衝突、零合資格、寫入失敗、不重複儲存、檔案 hash 損壞、版本切換失敗回滾、重啟、過期預覽、跨平台及路徑拒絕、HTTP write token／Origin。
- Headless Microsoft Edge：重複檔拒收、有效檔預覽／儲存／啟用、依新版本篩選及匯出、重新整理、切回研究版本。無 page JavaScript error；390px 無水平溢出；桌面及手機畫面已查看。
- 真實資料測試由原始 CSV 只選固定 train IDs，轉換後每列 ID、target tier 及比較欄位與 frozen Parquet 比較，差異 0。預測及 held-out outcome 沒有用來測試或調參。

| 平台 | 驗證筆數 | CSV bytes | 全列比較差異 |
|---|---:|---:|---:|
| PC | 51,152 | 8,432,091 | 0 |
| Mobile | 221,806 | 27,640,794 | 0 |

PC 51,152 列使用明示的 snapshot proxy date；Mobile 156 列 USD 價格不可用、4 列 Free/price 衝突設 unknown，與既有比較欄位一致。數字由 [real_data_verification.json](real_data_verification.json) 保存，包含程式與資料 hash。

真實規模測試使用臨時版本庫；UI 測試使用明示 synthetic 的兩列 fixture。兩者測後自動釋放，沒有把測試版本加入使用者的版本清單。保留的兩份轉換 CSV 共約 34.4 MiB，是可重用的真實匯入示範資料，位於 Git 忽略的 `data/application/conversions/`。

## Chapter 2 寫作素材對應

| 部分 | 可核對的實作／證據 |
|---|---|
| Method / Proposed Method | CSV → 驗證預覽 → 儲存版本 → 明確啟用 → 分平台篩選比較 → 顯示分布及匯出；`src/demo/server.py` |
| Data source | 保留原本 Kaggle provider／snapshot 引用；外部新匯入由維護者填 metadata，不宣稱已獨立核實 |
| Acquisition and processing | `src/imports/convert_sources.py`、`contracts.py`；格式錯誤阻止儲存，可允許缺失／排除另計數；原始檔不覆寫 |
| Data storage | `src/imports/repository.py`；source.csv、typed Parquet、完整 ledger、validation、manifest、atomic active.json；與研究資料分離 |
| Data analysis | 固定平台分級、條件交集、分母與重疊計數；本輪沒有新模型實驗 |
| Data visualization | 平台／版本標籤、兩組分布圖及樣本數、低樣本／空结果提示、匯入品質摘要；原型已實作但用戶效用未驗證 |

可以依上述素材由學生解釋設計與實作；不要把此紀錄當作已完成用户研究、已支援任意 CSV、自動重訓或可預測商業成功的證據。

## 使用界線與後續

首版僅支援目前 contract 和已知來源 adapter。比較用 CSV 不含完整模型特徵。平台版本獨立，無多帳戶、跨程序寫入協調或版本刪除介面；資料規則變動時重新驗證匯入。研究模型版本相容性及部署仍待後續。

下一步回到研究線：先固定一個樹模型候選與少量參數，再沿用既定 train/group CV 做比較及必要敏感度分析。相似遊戲參考、最終校準／test 及使用者評估仍未完成。
