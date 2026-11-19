"""Distribution and relationship charts for already filtered, eligible game rows.

All statistics use complete available observations. Only scatter marks and drawn
outliers may be capped; their full sample sizes remain in the exported metadata.
No model is fitted and no outcome, interval midpoint or missing value is imputed.
"""
import hashlib
import math

import numpy as np
import pandas as pd


SAFE_NUMBER = 2 ** 53 - 1
MAX_POINTS = 800
MAX_OUTLIERS = 20
GREEN = "#176b54"
TIER_LABELS = {
    "pc": [("O1_source_interval_up_to_20k", "上限 ≤ 20,000"),
           ("O2_source_intervals_20k_to_100k", "區間 20,000–100,000"),
           ("O3_source_intervals_100k_plus", "下限 ≥ 100,000")],
    "mobile": [("M1_under_1k", "下限 < 1,000"),
               ("M2_1k_to_under_100k", "下限 1,000–<100,000"),
               ("M3_100k_plus", "下限 ≥ 100,000")],
}


def _number(value):
    if value is None or pd.isna(value):
        return None
    result = float(value)
    if not math.isfinite(result) or abs(result) > SAFE_NUMBER:
        raise ValueError("Analytical chart value is non-finite or exceeds the browser safe numeric range.")
    return int(result) if result.is_integer() else result


def _numeric(series):
    result = pd.to_numeric(series, errors="raise").astype(float)
    valid = result.dropna()
    if not np.isfinite(valid.to_numpy()).all() or valid.abs().gt(SAFE_NUMBER).any():
        raise ValueError("Analytical chart values must be finite and within the browser safe numeric range.")
    if valid.lt(0).any():
        raise ValueError("Game price, counts, revenue and observation age must be nonnegative.")
    return result


def _base(ident, title, description, kind, unit, caption, section):
    return {"id": ident, "title": title, "description": description, "type": kind,
            "rows": [], "series": [], "unit": unit, "yLabel": unit,
            "source": caption, "section": section}


def _formatted(value):
    return f"{value:,.5g}"


def _histogram(values, name, unit, caption):
    known = values.dropna().to_numpy(dtype=float)
    config = _base("outcome_histogram", f"{name}的分布", "", "histogram", "款", caption, "distribution")
    config.update(xScale="log1p", xLabel=name, xUnit=unit,
                  series=[{"key": "count", "label": "遊戲數", "color": GREEN}],
                  summary={"available_rows": len(known), "missing_rows": int(values.isna().sum())})
    if len(known):
        low, high = float(known.min()), float(known.max())
        transformed = np.log1p(known)
        if transformed.min() == transformed.max():
            # One populated bin is enough for constant (or numerically identical
            # transformed) values. Do not construct a spurious distribution.
            lower, upper = low, high
            if lower == upper:
                lower, upper = max(0.0, low - 0.5), min(float(SAFE_NUMBER), high + 0.5)
            rows = [{"label": f"{_formatted(lower)}–{_formatted(upper)}", "values": [len(known)],
                     "lower": _number(lower), "upper": _number(upper), "count": len(known), "upper_inclusive": True}]
        else:
            bins = min(12, max(1, math.ceil(math.log2(len(known))) + 1))
            transformed_edges = np.linspace(transformed.min(), transformed.max(), bins + 1)
            edges = np.expm1(transformed_edges)
            edges[0], edges[-1] = low, high
            edges = np.unique(edges)
            counts, edges = np.histogram(known, bins=edges)
            rows = [{"label": f"{_formatted(left)}–{_formatted(right)}", "values": [int(count)],
                     "lower": _number(left), "upper": _number(right), "count": int(count),
                     "upper_inclusive": i == len(counts) - 1}
                    for i, (left, right, count) in enumerate(zip(edges[:-1], edges[1:], counts))]
        config["rows"] = rows
    config["description"] = (f"以 {len(known):,} 筆已知{name}計數；log1p 軸上的等寬分箱，區間以原始{unit}顯示。"
                             "分箱左閉右開，最後一箱含上限；零值保留，缺失不補零。分箱寬度會影響分布外觀。")
    return config


def _boxplots(frame, values, name, unit, caption, top_n):
    prepared = frame[["app_id", "groups"]].copy()
    prepared["metric"] = values
    expanded = prepared.explode("groups")
    rows, excluded, missing = [], [], 0
    for group, subset in expanded.groupby("groups", sort=True):
        known = subset.metric.dropna().sort_values()
        missing += int(subset.metric.isna().sum())
        if len(known) < 5:
            excluded.append({"label": str(group), "available_rows": len(known)})
            continue
        q1, median, q3 = known.quantile([0.25, 0.5, 0.75], interpolation="linear").tolist()
        iqr = q3 - q1
        lower_fence, upper_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        inside = known[(known >= lower_fence) & (known <= upper_fence)]
        outliers = known[(known < lower_fence) | (known > upper_fence)].tolist()
        positions = np.linspace(0, len(outliers) - 1, min(MAX_OUTLIERS, len(outliers)), dtype=int).tolist() if outliers else []
        drawn = [outliers[i] for i in sorted(set(positions))]
        rows.append({"label": str(group), "values": [_number(x) for x in [inside.min(), q1, median, q3, inside.max()]],
                     "n": len(known), "group_rows": len(subset), "missing_rows": int(subset.metric.isna().sum()),
                     "outlier_count": len(outliers), "outliers": [_number(x) for x in drawn]})
    rows.sort(key=lambda row: (-row["values"][2], row["label"]))
    config = _base("genre_boxplot", f"玩法／類別的{name}分布", "", "boxplot", unit, caption, "distribution")
    config.update(rows=rows[:top_n], xScale="log1p", xLabel=name, xUnit=unit,
                  series=[{"key": key, "label": label, "color": GREEN} for key, label in
                          [("lower_whisker", "下鬚"), ("q1", "Q1"), ("median", "中位數"), ("q3", "Q3"), ("upper_whisker", "上鬚")]],
                  summary={"eligible_groups": len(rows), "displayed_groups": min(top_n, len(rows)),
                           "excluded_groups": excluded, "outlier_display_limit_per_group": MAX_OUTLIERS,
                           "quartile_method": "linear_interpolation", "whisker_method": "actual_observations_within_1.5_IQR_fences"})
    config["description"] = ("只顯示至少 5 筆已知值的組別，按中位數排序；Q1／中位數／Q3 採線性插值，鬚端是 1.5×IQR 範圍內的實際值。"
                             f"{len(excluded)} 組因樣本不足略去；每組最多畫 {MAX_OUTLIERS} 個均勻抽取的離群值，完整離群數保留。"
                             "預設 log1p，可切換原始尺度；數值統計仍採原始尺度。多玩法遊戲可出現在不同組。")
    return config


def _scatter(frame, source, unit, currency, caption):
    if source == "mobile":
        x = _numeric((frame.observed_date - frame.release_date).dt.total_seconds() / 86400)
        y = _numeric(frame.volume_lower)
        x_name, x_unit = "觀測距發售日數", "日"
        y_name, y_unit = "安裝量下限", unit
        caveat = "觀測日來自原始或匯入資料；缺失日期排除。較舊遊戲有較長累積時間，不能把關聯視為時間成長曲線。"
    elif source == "pc":
        x, y = _numeric(frame.price), _numeric(frame.volume_lower)
        x_name, x_unit = "觀測價格", currency if currency != "unknown" else "來源數值（幣別未核實）"
        y_name, y_unit = "Owners 估計下限", "估計 owners 下限"
        caveat = "縱軸只取來源 owners 區間的下限作代理，不是精確購買量，也不使用區間中點。觀測價格不等於發售定價。"
    else:
        x, y = _numeric(frame.price), _numeric(frame.revenue)
        x_name, x_unit = "觀測價格", "USD"
        y_name, y_unit = "估計累積總營收", "USD"
        caveat = "高營收選入樣本具有選樣偏差；來源估計不等於實際回款或利潤，觀測價格也不等於發售定價。"
    pairs = frame[["app_id", "title"]].copy()
    pairs["x"], pairs["y"] = x, y
    pairs = pairs.dropna(subset=["x", "y"])
    rho = None
    if len(pairs) >= 2 and pairs.x.nunique() > 1 and pairs.y.nunique() > 1:
        rho = _number(pairs.x.rank(method="average").corr(pairs.y.rank(method="average")))
    # Sampling depends only on source and stable IDs, not selected values or
    # ordering, avoiding a visual preference for high-performing observations.
    pairs["sample_key"] = pairs.app_id.map(lambda value: hashlib.sha256(f"{source}:{value}".encode("utf-8")).hexdigest())
    displayed = pairs.sort_values(["sample_key", "app_id"]).head(MAX_POINTS)
    config = _base("price_outcome_scatter", f"{x_name}與{y_name}", "", "scatter", y_unit, caption, "relationships")
    config.update(points=[{"x": _number(row.x), "y": _number(row.y), "label": str(row.title), "id": str(row.app_id)} for row in displayed.itertuples()],
                  xLabel=x_name, yLabel=y_name, xUnit=x_unit, yUnit=y_unit, xScale="log1p", yScale="log1p",
                  series=[{"key": "point", "label": "遊戲", "color": GREEN}],
                  summary={"paired_rows": len(pairs), "displayed_rows": len(displayed), "spearman_rho": rho,
                           "excluded_incomplete_pairs": len(frame) - len(pairs), "sampling": "deterministic_sha256_of_source_and_app_id",
                           "correlation_basis": "all_complete_pairs_average_tied_ranks"})
    config["description"] = (f"{len(pairs):,} 對完整資料計算 Spearman 等級相關；圖中顯示 {len(displayed):,} 點（最多 {MAX_POINTS} 點的固定 ID 抽樣）。"
                             "常數欄位或少於兩對資料時不計相關。相關不代表因果，沒有擬合預測線。預設 log1p，可切換原始尺度。" + caveat)
    return config


def _heatmap(frame, source, caption, top_n):
    prepared = frame[["app_id", "groups"]].copy()
    if source == "revenue":
        values = _numeric(frame.revenue)
        bands = [("r1", "< 10,000"), ("r2", "10,000–<100,000"), ("r3", "100,000–<1,000,000"), ("r4", "≥ 1,000,000")]
        labels = pd.Series(None, index=frame.index, dtype=object)
        labels.loc[values.notna() & values.lt(10000)] = "r1"
        labels.loc[values.ge(10000) & values.lt(100000)] = "r2"
        labels.loc[values.ge(100000) & values.lt(1000000)] = "r3"
        labels.loc[values.ge(1000000)] = "r4"
        outcome = "估計總營收分組（USD）"
    else:
        bands = TIER_LABELS[source]
        labels = frame.target_tier.where(frame.target_tier.isin([key for key, _ in bands]))
        outcome = "Owners 來源區間分層" if source == "pc" else "安裝量下限分層"
    prepared["band"] = labels
    rows, excluded = [], []
    for group, subset in prepared.explode("groups").groupby("groups", sort=True):
        n = int(subset.band.notna().sum())
        if n < 30:
            excluded.append({"label": str(group), "known_rows": n, "group_rows": len(subset)})
            continue
        counts = [int(subset.band.eq(key).sum()) for key, _ in bands]
        rows.append({"label": str(group), "values": [_number(100 * count / n) for count in counts],
                     "counts": counts, "n": n, "group_rows": len(subset), "unknown_rows": len(subset) - n})
    rows.sort(key=lambda row: (-row["n"], row["label"]))
    config = _base("group_outcome_heatmap", f"玩法／類別與{outcome}", "", "heatmap", "%", caption, "relationships")
    config.update(rows=rows[:top_n], series=[{"key": key, "label": label, "color": GREEN} for key, label in bands],
                  summary={"eligible_groups": len(rows), "displayed_groups": min(top_n, len(rows)), "excluded_groups": excluded,
                           "percentage_denominator": "known_outcome_rows_within_each_group"},
                  xLabel=outcome, yLabel="玩法／類別", scale_min=0, scale_max=100)
    config["description"] = ("每列以該玩法／類別的已知分層筆數 n 作分母，列百分比合計 100%；未知結果另計，不補零。"
                             f"只顯示 n ≥ 30 的組別；{len(excluded)} 組略去。格內同時保留百分比與筆數，多玩法組別可能重疊。"
                             "這是描述性分布，不是成功機率、相關係數矩陣或因果分析。")
    return config


def analytical_charts(frame, source, unit, currency, caption, top_n=10):
    """Return four chart configs; caller owns source validation and taxonomy.

    ``groups`` must contain reviewed gameplay labels (or Android categories).
    Filters and cohort exclusions must already be applied by the caller.
    """
    if source not in {"pc", "mobile", "revenue"}:
        raise ValueError("Unknown analytical chart source.")
    if type(top_n) is not int or top_n not in (10, 20):
        raise ValueError("top_n must be 10 or 20.")
    if source == "pc":
        values = _numeric(frame.price)
        name = "觀測價格"
        metric_unit = currency if currency != "unknown" else "來源數值（幣別未核實）"
    elif source == "mobile":
        values, name, metric_unit = _numeric(frame.volume_lower), "安裝量下限", unit
    else:
        values, name, metric_unit = _numeric(frame.revenue), "估計累積總營收", "USD"
    return [_histogram(values, name, metric_unit, caption),
            _boxplots(frame, values, name, metric_unit, caption, top_n),
            _scatter(frame, source, unit, currency, caption),
            _heatmap(frame, source, caption, top_n)]
