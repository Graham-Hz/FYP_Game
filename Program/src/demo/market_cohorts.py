"""Descriptive selected-versus-baseline comparisons with explicit denominators."""
import math

import pandas as pd


VERSION = "market_cohort_comparison_v1"
COLORS = ["#176b54", "#426cba", "#bd7623", "#89958f"]


def number(value):
    if value is None or pd.isna(value):
        return None
    value = float(value)
    if not math.isfinite(value) or abs(value) > 2 ** 53 - 1:
        raise ValueError("Comparison value is outside the browser safe numeric range.")
    return int(value) if value.is_integer() else value


def quartiles(values):
    known = values.dropna()
    q1, median, q3 = known.quantile([.25, .5, .75], interpolation="linear").tolist() if len(known) else [None] * 3
    return {"n": len(known), "q1": number(q1), "median": number(median), "q3": number(q3)}


def cohort(frame, key, label, source, tier_definitions):
    statistics = {"volume_lower": quartiles(frame.volume_lower)}
    if source == "pc":
        statistics["volume_upper"] = quartiles(frame.volume_upper)
    if source == "revenue":
        statistics["revenue"] = quartiles(frame.revenue)
        known = int(frame.revenue.notna().sum())
    else:
        known = int(frame.target_tier.isin([ident for ident, _ in tier_definitions]).sum())
    n = len(frame)
    tiers = [{"id": ident, "label": name, "count": int(frame.target_tier.eq(ident).sum()),
              "percent": number(100 * frame.target_tier.eq(ident).sum() / n) if n else None}
             for ident, name in tier_definitions] if source != "revenue" else []
    return {"key": key, "label": label, "n": n, "known_outcome_rows": known,
            "unknown_outcome_rows": n - known, "statistics": statistics, "tiers": tiers}


def compare(selected_frame, baseline_frame, source, selected_label, baseline_label,
            baseline_definition, caption, tier_definitions=()):
    selected = cohort(selected_frame, "selected", selected_label, source, tier_definitions)
    baseline = cohort(baseline_frame, "baseline", baseline_label, source, tier_definitions)
    overlap = len(set(selected_frame.app_id) & set(baseline_frame.app_id))
    notes = ["兩組沿用同一資料版本、附加標籤及發售年份條件；比較是歷史描述，不代表因果或新遊戲的成功機率。",
             "每組 n 是組內全部記錄。分層百分比以 n 作分母；數值四分位數只使用該數值已知的記錄，並另列可用筆數。"]
    if overlap:
        notes.append(f"兩組有 {overlap:,} 款相同遊戲；Steam 可具有多個玩法標籤，兩組不能視為互不重疊的獨立樣本。")
    if not baseline["n"]:
        notes.append("相同條件下沒有對照樣本；對照統計及百分比保持未提供，不以零代替。")
    if not selected["n"]:
        notes.append("相同條件下沒有所選樣本；所選統計及百分比保持未提供，不以零代替。")
    if any(0 < item["n"] < 30 for item in (selected, baseline)):
        notes.append("至少一組少於 30 筆記錄；小樣本容易受個別遊戲影響。")
    if source == "revenue":
        chart = {"id": "cohort_comparison", "title": "所選樣本與對照：估計營收中位數",
                 "description": "同一高營收選入樣本內的比較；中位數只用已知估計總營收，不是預測、利潤或典型全市場收入。",
                 "type": "bar", "unit": "USD", "yLabel": "估計累積總營收中位數（USD）",
                 "series": [{"key": "revenue", "label": "估計營收中位數", "color": COLORS[0]}],
                 "rows": [{"label": item["label"], "n": item["n"], "cohort": item["key"],
                           "values": [item["statistics"]["revenue"]["median"]]} for item in (selected, baseline)]}
    else:
        if any(item["unknown_outcome_rows"] for item in (selected, baseline)):
            for item in (selected, baseline):
                count = item["unknown_outcome_rows"]
                item["tiers"].append({"id": "unknown", "label": "結果未知", "count": count,
                                      "percent": number(100 * count / item["n"]) if item["n"] else None})
        series = [{"key": item["id"], "label": item["label"], "color": COLORS[i]}
                  for i, item in enumerate(selected["tiers"])]
        chart = {"id": "cohort_comparison", "title": "所選樣本與對照：數量分層分布",
                 "description": "每列以組內全部樣本 n 為分母；比例固定在 0–100%。未知結果另列，沒有樣本的組別不畫成零比例。點選分段可查看記錄。",
                 "type": "stacked_bar", "unit": "%", "yLabel": "組內比例（%）", "series": series,
                 "rows": [{"label": item["label"], "n": item["n"], "cohort": item["key"],
                           "values": [tier["percent"] for tier in item["tiers"]],
                           "counts": [tier["count"] for tier in item["tiers"]]} for item in (selected, baseline)],
                 "scale_min": 0, "scale_max": 100}
    chart.update(source=f"{caption} · 所選 n={selected['n']:,} · 對照 {baseline_label} · 對照 n={baseline['n']:,}",
                 section="distribution", integerTicks=False)
    return {"method_version": VERSION, "selected": selected, "baseline": baseline,
            "overlap_count": overlap, "baseline_definition": baseline_definition,
            "notes": notes, "chart": chart}
