# FYP 程式導讀

日期：2026-10-16。用現有資料及同一折研究設定，親手走一次 CSV → 統計 → 圖表 → 模型。這是學習與重現，不新增正式模型搜尋或最終評估。

## 如何開啟

1. 在檔案總管進入 `My_FYP\Program`，雙擊 [START_WALKTHROUGH.cmd](../START_WALKTHROUGH.cmd)。
2. 保留啟動視窗；JupyterLab 應在瀏覽器開啟。首次啟動可能需要下載教學環境。如果瀏覽器沒有自動開啟，用啟動視窗顯示的本機網址。
3. 開啟 [01_understand_your_fyp.ipynb](01_understand_your_fyp.ipynb)。按 **Shift+Enter** 逐格執行，先完成第 1–5 節。
4. 左側 `[*]` 表示正在運算；完成後才執行下一格。Notebook 已保存示範輸出，重新執行才是你自己的這次操作。
5. 想由零重跑，選 **Kernel → Restart Kernel and Run All Cells**。完成後儲存 Notebook，在啟動視窗按 Ctrl+C 並按提示停止伺服器。

你也可用 VS Code 的 Jupyter 功能開啟，但 kernel 要選 `Program/experiments/walkthrough_v1/.venv/Scripts/python.exe`。首選上面的啟動檔，可減少環境選錯的機會。

## 先學甚麼

| 進度 | 內容 | 自己要做到 |
|---|---|---|
| 第 1–3 節 | `import pandas as pd`、讀 CSV、缺失／型別／未知值 | 解釋一列代表甚麼，未知與零／false 有何不同 |
| 第 4–5 節 | `value_counts`、`groupby`、Matplotlib | 產生分布圖及免費／付費比較圖，說清楚分母 |
| 第 6–8 節 | Parquet、merge、X/y、developer folds、前處理 | 解釋 fitting 與 validation，知道哪些欄位不能當輸入 |
| 第 9–10 節 | Logistic Regression `.fit()`、baseline、指標、混淆矩陣 | 真正訓練一次，重現既有 fold 0 的預測 |
| 第 11 節 | 正式程式位置及練習 | 加入自己的圖表／解釋，留下修改紀錄 |

不用一次理解所有 hash／路徑設定。先理解資料操作，再打開 Notebook 指出的正式 `.py`，逐步對照。程式已標明哪些部分是既有 helper；不把呼叫 helper 說成已自己重寫整個算法。

## 執行內容與輸出

- Android train CSV：221,806 筆；它是已整理的研究匯出，原始 Kaggle 清理在 `src/data/`。
- 模型示範：原有 `P_C0.1_none` 的 fold 0，147,902 筆 fitting、73,904 筆 validation。分組及參數固定；不是重新調參。
- Notebook 保存 3 張 inline 圖，另輸出 PNG 到 [教學輸出](../reports/2026-10-16/walkthrough_v1/)；重跑會更新這個教學資料夾。
- 不儲存／取代正式模型，不修改 Power BI CSV／PBIX、app 或 DOCX；不評估 calibration/test。
- 教學環境在 `experiments/walkthrough_v1/`，保留自己的 `uv.lock`；原資料／模型環境沒有新增繪圖或 Jupyter 依賴。

驗證工具已從全新 kernel 執行整份 Notebook、核對正式 OOF 預測及原有檔案，見 [verification.json](../reports/2026-10-16/walkthrough_v1/verification.json)。三張 PNG 亦已目視檢查。瀏覽器雙擊啟動流程未在 UI 中驗收；遇到錯誤時保留訊息，不要先修改研究資料或重新切分。

## 常見情況

- **NameError**：可能跳過前面的格，從頭按順序執行。
- **套件不存在／版本不同**：使用上述教學環境，不要對凍結模型環境直接 `pip install`。
- **找不到資料檔**：大型資料是 Git 忽略的本機檔；只有 clone repository 未必足夠。這台電腦已有所需檔案。
- **hash 不符**：表示來源與既有實驗版本不同；先查明原因，不刪掉檢查。

開發者重現指令（在 Program）：

```powershell
uv run --project experiments/walkthrough_v1 --locked python.exe -X utf8 -B notebooks/verify_walkthrough.py
```

本教學由 AI 協助建立；你的學習任務是理解、實際操作、完成自己的練習及依手冊披露協助。它不是可以直接提交的報告正文。
