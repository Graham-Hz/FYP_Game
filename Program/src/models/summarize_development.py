"""Create readable working notes after independent development verification."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/2026-10-07/model_dev_v1"


def main():
    run_bytes = (REPORT/"run_manifest.json").read_bytes()
    run = json.loads(run_bytes)
    verification = json.loads((REPORT/"verification.json").read_text(encoding="utf-8"))
    if run["status"] != "complete" or verification["status"] != "passed" or verification["run_manifest_sha256"] != hashlib.sha256(run_bytes).hexdigest():
        raise ValueError("Require a completed, independently verified run")
    summary = pd.read_csv(REPORT/"cv_summary.csv")
    choices = json.loads((REPORT/"development_choices.json").read_text(encoding="utf-8"))
    rows = []
    for platform in ("pc", "mobile"):
        for feature in ("none", "age_only", "P", "P+A", "P_without_price"):
            found = next((r for r in choices if r["platform"] == platform and r["features"] == feature), None)
            if found:
                rows.append(summary.loc[summary.platform.eq(platform) & summary.configuration.eq(found["configuration"])].iloc[0])
    names = {"none": "多數類別／類別比例基準", "age_only": "只用觀察年齡", "P": "規劃特徵 P", "P+A": "規劃特徵＋觀察年齡 P+A", "P_without_price": "規劃特徵但不含價格"}
    lines = ["# 首輪模型開發結果", "", "實驗完成：2026-10-07；恢復檢查、獨立驗證與摘要：2026-10-08。研究工作紀錄，並非報告提交正文。", "",
             "**已完成首輪線性模型比較：26 組設定、78 次折內擬合，全部使用既定 train 分區的三折開發者群組驗證。未評估 calibration 或最終 test，未把模型接入使用者介面。**", "",
             "## 結果", "", "每種特徵集合列出依平均 fold macro-F1 選出的開發設定；所有設定與逐折结果仍保留。Macro-F1 取值 0–1，對三個分級的 F1 等權平均，並不是準確率或成功機率。SD 是三折分數的離散程度，並非信賴區間。", "",
             "| 平台 | 輸入／基準 | Macro-F1 平均 | Fold SD | Balanced accuracy 平均 | Accuracy 平均 | C | Class weight |",
             "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r.platform} | {names[r.features]} | {r.macro_f1_mean:.4f} | {r.macro_f1_sd:.4f} | {r.balanced_accuracy_mean:.4f} | {r.accuracy_mean:.4f} | {'—' if pd.isna(r.C) else r.C} | {r.weight} |")
    lines += ["", "## 如何解讀", "",
              "- 選參數與本表使用同一組 CV，屬開發比較，存在選模偏樂觀；不是最終測試成績，也未進行顯著性或因果推論。",
              "- age-only 和 P+A 比較的是歷史觀察年齡的資訊，不是已驗證的上市後固定天數預測；較高分不代表遊戲規劃能控制年齡帶來的差異。",
              "- PC 限正觀察價格等既定分析範圍；P_without_price 用來檢查未核實幣別的價格欄位影響。PC 與 Mobile 的年份、母體及 outcomes 不同，不能按這張表排名平台商業機會。",
              "- balanced 權重可改變少數分級的取捨；不能只看整体 accuracy，也不能把未校準的 predict_proba 作為可對外展示的成功機率。",
              "", "## 三個分級的表現", "", "以下為每種輸入的所選設定，合併全部 OOF 預測後的逐類 recall；與上表的平均 fold 統計有所區別。", "",
              "| 平台 | 輸入／基準 | 第一級 recall | 第二級 recall | 第三級 recall |", "|---|---|---:|---:|---:|"]
    per_class = pd.read_csv(REPORT/"per_class.csv")
    for r in rows:
        selected = per_class.loc[per_class.platform.eq(r.platform) & per_class.configuration.eq(r.configuration)].sort_values("tier")
        recalls = " | ".join(f"{value:.4f}" for value in selected.recall)
        lines.append(f"| {r.platform} | {names[r.features]} | {recalls} |")
    subgroups = pd.read_csv(REPORT/"mobile_subgroups.csv")
    lines += ["", "## Android 子群檢查", "", "只列 P 與 P+A 所選設定。資料不明子群樣本非常小，不能据此判斷一般效果；付費子群的結果亦須與免費子群分開解讀。", "",
              "| 輸入 | 子群 | n | 固定三類 macro-F1 | Accuracy |", "|---|---|---:|---:|---:|"]
    for r in rows:
        if r.platform == "mobile" and r.features in ("P", "P+A"):
            for s in subgroups.loc[subgroups.configuration.eq(r.configuration)].itertuples():
                lines.append(f"| {r.features} | {s.subgroup} | {s.n:,} | {s.macro_f1_fixed_three_labels:.4f} | {s.accuracy:.4f} |")
    audit = json.loads((REPORT/"preprocessing_audit.json").read_text(encoding="utf-8"))
    retries = sum(r["convergence_retries"] for r in audit)
    max_unknown = max((r["coverage"].get("rows_with_unknown", 0)/r["validation_n"] for r in audit), default=0)
    lines += ["", "## 驗證與重現", "",
              f"- 全部 {verification['configurations']} 組／{verification['folds_checked']} 折完成；共獨立核對 {verification['prediction_rows_checked']:,} 筆預測及 {verification['model_replay_rows']:,} 筆保存模型的重播預測。",
              "- 獨立核對包括：完整 train-only OOF 成員、開發者群組隔離、前處理統計、特徵白名單、混淆矩陣、逐類 precision/recall/F1、macro-F1、accuracy、balanced accuracy、log loss、Brier、fold 平均／SD、Android 子群及檔案 hash。",
              f"- 收斂重試總數：{retries}。各折資料中含至少一個未見編碼值的樣本比例，最大為 {100*max_unknown:.3f}%；詳見 preprocessing_audit.json。未見值不會擴充驗證時的詞彙表。",
              "- 模型環境使用獨立 uv.lock，原分析環境及資料版本不變。整合測試共 22 項通過（原有 16 項＋新增前處理 6 項）。",
              "- [事前實驗設計](../../planning/model_dev_v1_protocol.md)、[全部 CV 設定](cv_summary.csv)、[逐折指標](fold_metrics.csv)、[驗證紀錄](verification.json)。大型預測及折模型放在 Git-ignore 的 data/processed/model_dev_v1/。",
              "", "## 接下來", "",
              "1. 根據逐類與子群表現檢視模型限制，完成預先限定的樹模型比較及敏感度分析；保留最終測試集。",
              "2. 推進指定格式 CSV 的欄位字典、範本與版本化匯入，使已存在的描述比較支援更新資料；新快照不混入本次實驗。",
              "3. 待候選方法與評估規則固定後，才進入校準與最終測試。需要足夠證據才把模型輸出放入介面。",
              "4. Chapter 1 由學生按 review notes 自行修訂；以原型與本次開發結果準備導師討論，不需等待整個最終系統完成。",
              "", "Reproduce summary: `uv run --project experiments/model_dev_v1 --locked python.exe src/models/summarize_development.py`", ""]
    (REPORT/"results_notes.md").write_text("\n".join(lines), encoding="utf-8")
    print(REPORT/"results_notes.md")


if __name__ == "__main__":
    main()
