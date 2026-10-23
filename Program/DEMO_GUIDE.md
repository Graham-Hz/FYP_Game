# 歷史遊戲比較原型：操作與展示指引

2026-10-10 · 本機可行性展示 v2。已加入指定格式 CSV 匯入、驗證及資料版本切換，操作見 [CSV_IMPORT_GUIDE.md](CSV_IMPORT_GUIDE.md)。GameScope 是暫用的介面名稱，並非已確定的 FYP 題目。

## 啟動

在這部電腦進入 `My_FYP/Program`，雙擊 **START_DEMO.cmd**。它會核對資料版本，然後開啟瀏覽器 `http://127.0.0.1:8765/`。啟動視窗須保持開啟；關閉視窗或按 Ctrl+C 即停止。

不需要手動輸入 PowerShell 指令。如已有啟動視窗，直接開啟上述網址，避免重複啟動。

若看見 `uv was not found`，表示目前 Windows 環境未能找到已安裝的 uv；先重新開啟檔案總管／終端再試。若仍失敗，保留錯誤訊息以便檢查。若提示連接埠被使用，關閉自己先前開啟的原型視窗再啟動，或使用另一個連接埠：

```powershell
uv run --locked python src/demo/server.py --port 8766 --open
```

## 三分鐘示範

1. Steam：A 選 Action，B 選 Adventure，按「比較歷史分布」。指出各自樣本數、三組來源估算擁有者區間的比例，以及兩組的重疊數。
2. 加上 Single-player 等功能，觀察符合條件的樣本數如何改變。這只描述歷史樣本，不代表改變功能會提高成功機率。
3. Android：A 選 Puzzle，B 選 Action，可再選免費、廣告或內購。結果改為安裝量下限分級，不能直接拿來與 Steam 排名。
4. Android 的「免費下載」選「資料不明」可展示小樣本處理；再選 Casino 可展示沒有匹配樣本的情況。
5. 按「匯出結果 JSON」。檔案包含當次兩組條件、各級筆數與百分比、重疊數、資料年月及固定版本雜湊。改動條件後須重新比較，才可匯出新結果。

以上示範使用「原有研究 train 資料」。其他版本下的「全部」是該版本全部合資格紀錄；空白功能條件不代表「沒有該功能」。同組不同欄位以 AND 合併。Steam 多重類型／功能允許重疊，Android 每筆只有一個來源類別。小樣本提示採用 n < 30，這是介面門檻而非統計可靠性的保證。

## 範圍與限制

| 平台 | 資料快照 | 原型使用筆數 | 顯示結果 |
|---|---|---:|---|
| Steam | 2025-03 | 51,152（train） | 來源估算擁有者區間三分級 |
| Android | 2021-06 | 221,806（train） | 來源安裝量下限三分級 |

完整研究 cohort 分別為 73,527 及 318,300 筆；上表原有版本只查詢 training partition。來源及排除規則見 [analysis protocol](reports/2026-10-06/analysis_v1/analysis_protocol.md)。Steam primary cohort 只包含正價格及可用標籤／開發者的紀錄，並排除僅軟件類型紀錄；Android 排除 Sports 等不明確範圍及缺失發佈日期紀錄。匯入版本則使用獨立快照及其納入規則，畫面／匯出會標示版本和分母；不改動上述研究 cohort。

Steam 貨幣仍未核實，所以原型沒有價格篩選。Android 的衝突免費狀態保留為資料不明，不當作付費。資料是不同年份的快照；不代表目前市場，也不是專門抽樣的獨立工作室資料。開發者年齡／資源、遊戲年齡、選樣及資料缺漏等尚未受到控制。

介面沒有接入預測模型、推薦排名、收益估算或因果結論。它現在支援「指定格式 CSV → 驗證／儲存／啟用 → 條件比較 → 匯出核對」。首輪研究模型已另行擬合，但未部署。雙平台研究方向仍待導師確認；正式模型及最終框架尚未決定。

## 開發與重現

服務以 Python 標準庫 HTTP server + 已有 DuckDB／PyArrow 實作，只綁定 `127.0.0.1`，沒有修改 `uv.lock`。前端沒有 CDN 或外部網絡依賴。啟動時校驗 analysis manifest 及四個 feature/label 檔案的 SHA-256；原有版本只建立 train 資料表，不提供切換研究 test 或 calibration 的接口。另行啟用的匯入版本只讀自己的比較 Parquet，並驗證版本檔案 hash。寫入 API 有本機 Host、Origin 和頁面 token 檢查；不提供多人登入或公開服務。

資料檔維持 Git-ignore，**只下載 GitHub 程式碼不足以啟動**。本機目前已具備四個 `data/processed/analysis_v1/{pc,mobile}_{features,labels_splits}.parquet` 檔案。在其他電腦先依 [Program README](README.md) 的流程重建所需原始／中間及分析資料，並核對 [manifest](reports/2026-10-06/analysis_v1/manifest.json)。雜湊不一致時應查明原因，不可直接改常數略過驗證。

```powershell
uv run --project experiments/model_dev_v1 --locked python -B -m unittest discover -s tests -v
uv run --locked python src/data/verify_analysis.py
# 可選瀏覽器測試：需要本機 Microsoft Edge；暫時加入測試工具，不變更 uv.lock。
uv run --locked --with playwright python.exe tests/check_demo_browser.py
```

新增整合測試依賴本機 frozen artifacts。瀏覽器測試另開獨立的 headless Edge，不使用日常瀏覽器設定；畫面及測試輸出放在 Git-ignore 的 `data/processed/demo_qa/`。

## 報告工作

Chapter 1 結構及寫作提示見 [Chapter 1 規劃筆記](reports/planning/chapter1_planning_notes.md)。2026-10-23 學生確認尚未與導師討論專案範圍及方法；這些筆記並非會議紀錄，舊兩星期匯報安排已移除。進度報告及各項研究證據見 [報告索引](reports/README.md)。最新 Handbook 的一般 AI 限制、學生另行表示的個別放寬，以及實際程式／分析／報告撰寫協助，分別記錄於 [AI assistance log](reports/planning/ai_assistance_log.md)；不把學生確認方向寫成導師批准。
