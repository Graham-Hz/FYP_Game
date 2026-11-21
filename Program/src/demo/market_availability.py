"""Chart readiness for the exact filtered sample, separate from inference quality.

Readiness explains whether a descriptive view has the fields/observations it
needs. Existing display thresholds are not statistical-significance guarantees.
No missing values, chart values or frozen research records are changed here.
"""
import pandas as pd
from market_analytics import TIER_LABELS


def _result(total, valid, requirements, *, status=None, reason=None, action=None, **facts):
    total, valid = int(total), int(valid)
    if status is None:
        status = "unavailable" if not valid else "limited" if valid < total else "available"
    if reason is None:
        reason = (f"目前有 {valid:,} 款遊戲符合這張圖的資料要求。" if status == "available" else
                  f"這張圖可使用 {valid:,}／{total:,} 款遊戲；其餘記錄缺少所需資料，沒有補成零。" if valid else
                  "目前沒有符合這張圖資料要求的遊戲。")
    if action is None:
        action = "" if status == "available" else "可放寬篩選條件，或匯入包含所需資料的相容 CSV，再重新分析。"
    return {"status": status, "reason": reason, "action": action,
            "valid_rows": valid, "total_rows": total, "missing_rows": total - valid,
            "requirements": requirements, **facts}


def _comparison_readiness(comparison, metric=None):
    samples = [comparison["selected"], comparison["baseline"]]
    total = sum(item["n"] for item in samples)
    counts = [item["statistics"][metric]["n"] if metric else item["known_outcome_rows"] for item in samples]
    valid = sum(counts)
    requirements = ["所選組與對照組各至少有 1 款具備所需數值／分層的遊戲。",
                    "兩組必須來自相同資料版本與年份條件；重疊作品會另外標示。"]
    facts = {"selected_valid_rows": int(counts[0]), "baseline_valid_rows": int(counts[1]),
             "count_basis": "sum_of_two_cohorts_including_any_overlap"}
    if not total or not valid:
        return _result(total, valid, requirements, status="unavailable",
                       reason="兩組都沒有可比較的已知數值／分層資料。",
                       action="放寬條件或更換對照組；若資料缺少數值，請先補齊相容 CSV。", **facts)
    if not all(counts):
        return _result(total, valid, requirements, status="limited",
                       reason="其中一組沒有可比較的已知資料；只展示有資料的一組，不能解讀兩組差異。",
                       action="放寬年份／標籤篩選或更換對照組，直到兩組都有所需資料。", **facts)
    return _result(total, valid, requirements, **facts)


def annotate_charts(charts, frame, source, *, comparison=None):
    """Add availability metadata; retain original chart rows for evidence exports.

    valid_rows counts unique filtered games, except cohort charts where the
    explicit count_basis includes both groups and any overlapping membership.
    """
    n = len(frame)
    grouped = frame.groups.map(bool).astype(bool)
    known_volume = frame.volume_lower.notna()
    known_price = frame.price.notna()
    known_date = frame.release_date.notna()
    metric = "price" if source == "pc" else "volume_lower" if source == "mobile" else "revenue"
    numeric_name = "觀測價格" if source == "pc" else "安裝量下限" if source == "mobile" else "估計累積營收"
    known_metric = frame[metric].notna()
    known_outcome = frame.revenue.notna() if source == "revenue" else frame.target_tier.isin([key for key, _ in TIER_LABELS[source]])
    # Membership is expanded only for group thresholds; reported game counts
    # below use index membership so multi-genre games are counted once.
    expanded = frame[["groups"]].explode("groups")

    def group_info(known, minimum):
        usable = expanded.loc[expanded.index.isin(frame.index[known])]
        sizes = usable.groupby("groups", sort=False).size()
        eligible = set(sizes[sizes >= minimum].index)
        mask = known & frame.groups.map(lambda labels: any(label in eligible for label in labels)).astype(bool)
        all_groups = set(expanded.groups.dropna())
        return mask, len(eligible), len(all_groups - eligible)

    for chart in charts:
        ident = chart["id"]
        requirements = ["至少有 1 款符合目前篩選條件的遊戲。"]
        if comparison is not None and (ident == "cohort_comparison" or
                                       ident == "group_volume_median"):
            chart["availability"] = _comparison_readiness(
                comparison, "volume_lower" if ident == "group_volume_median" else
                "revenue" if source == "revenue" else None)
            continue
        if not n:
            chart["availability"] = _result(0, 0, requirements, reason="目前篩選沒有符合的遊戲，因此無法產生這張圖。",
                                             action="清除類型、標籤或年份限制後重新分析。沒有樣本不代表市場不存在這類遊戲。")
            continue
        ready = None
        if ident == "group_count":
            ready = _result(n, grouped.sum(), ["至少有 1 款具備已對照玩法／類別的遊戲。"],
                            action=None if grouped.all() else "可改用全部類型，或核對匯入 CSV 的玩法／類別。未對照標籤不會強行歸類。")
        elif ident in {"group_volume_total", "group_volume_median", "group_revenue_total", "group_revenue_median"}:
            known = frame.revenue.notna() if "revenue" in ident else known_volume
            ready = _result(n, (grouped & known).sum(), ["至少有 1 款同時具備玩法／類別及所需數值的遊戲。"])
        elif ident in {"genre_boxplot", "group_outcome_heatmap", "group_high_tier_share"}:
            minimum = 5 if ident == "genre_boxplot" else 30
            known = known_metric if ident == "genre_boxplot" else known_outcome
            mask, eligible, excluded = group_info(known, minimum)
            requirement = f"每個展示組別至少 {minimum} 款{'具備所需數值的' if ident == 'genre_boxplot' else '分層已知的'}遊戲。"
            threshold_note = f"{minimum} 是此圖的顯示規則，不代表已達統計可靠性。"
            status = "unavailable" if not eligible or not mask.any() else "limited" if excluded or mask.sum() < n else "available"
            reason = (f"目前沒有組別符合每組至少 {minimum} 款的顯示要求；{excluded} 組未達要求。" if not eligible else
                      f"{eligible} 組可顯示，{excluded} 組未達此圖的資料要求；使用 {int(mask.sum()):,} 款不同遊戲。")
            if eligible and not mask.any():
                reason = "組別筆數雖達顯示門檻，但沒有已知數量分層，不能把缺少結果當作零比例。"
            elif not eligible and not excluded:
                reason = "目前遊戲沒有可對照的玩法／類別，無法建立這張圖的組別。"
            ready = _result(n, mask.sum(), [requirement, threshold_note], status=status,
                            reason=reason, eligible_groups=eligible, excluded_groups=excluded,
                            minimum_rows_per_group=minimum)
        elif ident == "outcome_tiers":
            ready = _result(n, known_outcome.sum(), ["比較來源數量分層需要已知數量；未知或區間無法分層的記錄只計為缺失筆數。"])
            if not known_outcome.any():
                ready.update(status="limited", reason="數量分層全部未知或區間跨越分層邊界；只展示無法分層的筆數，不能比較分層表現。",
                             action="若要比較分層表現，需提供可分類的來源數量；跨界 owners 區間仍可用於數量圖，不必強行分類。")
        elif ident in {"release_count", "release_volume_median"}:
            valid = known_date if ident == "release_count" else known_date & known_volume
            frequency = frame.loc[valid, "release_date"].dt.to_period("M" if source == "revenue" else "Y")
            periods = int(frequency.nunique())
            requirements = ["每個資料點需要有效發售日期；數量中位數還需要已知數量。",
                            "至少 2 個有資料的發售批次才能比較不同批次。"]
            if not valid.any():
                ready = _result(n, 0, requirements, reason="沒有同時具備有效發售日期及此圖所需數值的遊戲。" if ident != "release_count" else "目前沒有有效發售日期，無法按年份／月份分組。",
                                action="匯入含有效 release_date 的相容 CSV，或放寬年份條件。", observed_periods=0)
            elif periods < 2:
                ready = _result(n, valid.sum(), requirements, status="limited",
                                reason="目前只有 1 個有資料的發售批次；可顯示該批次數值，不能解讀為時間走勢。",
                                action="放寬年份條件或加入其他發售批次；這仍是批次比較，不是逐期銷售紀錄。", observed_periods=periods)
            else:
                ready = _result(n, valid.sum(), requirements, observed_periods=periods)
        elif ident in {"outcome_histogram", "price_histogram"}:
            histogram_known = known_price if ident == "price_histogram" else known_metric
            histogram_field = "price" if ident == "price_histogram" else metric
            histogram_name = "來源明示為 USD 的觀測價格" if ident == "price_histogram" else numeric_name
            distinct = int(frame.loc[histogram_known, histogram_field].nunique())
            requirements = [f"至少有 1 款具備{histogram_name}的遊戲；零是有效數值。"]
            if histogram_known.any() and (histogram_known.sum() < 2 or distinct < 2):
                ready = _result(n, histogram_known.sum(), requirements, status="limited",
                                reason="目前只有 1 筆有效數值。" if histogram_known.sum() == 1 else "所有有效數值都相同，圖中只會出現一個有資料的區間。",
                                action="可查看此數值的筆數；若要觀察分布差異，請放寬條件或加入其他有效記錄。", distinct_values=distinct)
            else:
                ready = _result(n, histogram_known.sum(), requirements, distinct_values=distinct)
        elif ident == "price_outcome_scatter":
            if source == "mobile":
                x = (frame.observed_date - frame.release_date).dt.total_seconds() / 86400
                y = frame.volume_lower
                requirements = ["同一款遊戲須有有效發售日期、觀測日期及安裝量下限。"]
            else:
                x, y = frame.price, frame.revenue if source == "revenue" else frame.volume_lower
                requirements = ["同一款遊戲須有已知觀測價格及數量／營收，才構成一對資料。"]
            requirements += ["計算等級相關至少需要 2 對資料，且兩個欄位都不能全為相同數值。"]
            pair = x.notna() & y.notna()
            pairs, dx, dy = int(pair.sum()), int(x[pair].nunique()), int(y[pair].nunique())
            facts = {"paired_rows": pairs, "distinct_x_values": dx, "distinct_y_values": dy}
            if pairs == 0:
                ready = _result(n, 0, requirements, reason="沒有同時包含兩個軸所需資料的遊戲，無法繪製散點圖。", **facts)
            elif pairs < 2 or dx < 2 or dy < 2:
                ready = _result(n, pairs, requirements, status="limited",
                                reason="只有 1 對完整資料；可看資料點，但無法計算相關。" if pairs < 2 else "至少一個欄位的有效數值全部相同；可看資料點，但無法計算相關。",
                                action="放寬條件或補充有效記錄。沒有相關係數不等於相關為零；本圖沒有擬合預測線。", **facts)
            else:
                ready = _result(n, pairs, requirements, **facts)
        elif ident in {"business_count", "business_volume_median", "price_revenue_median"}:
            known = frame[["free", "ad_supported", "in_app_purchases"]].notna().any(axis=1) if source == "mobile" else known_price
            if ident != "business_count":
                known = known & (frame.revenue.notna() if ident == "price_revenue_median" else known_volume)
            requirements = ["至少有 1 款具備下載收費／廣告／內購任一已知標記的遊戲。" if source == "mobile" else "至少有 1 款具備已知觀測價格的遊戲。"]
            if ident != "business_count":
                requirements.append("同一款遊戲還需要已知數量／營收。")
            if not known.any() and ident == "business_count":
                ready = _result(n, 0, requirements, status="limited", reason="相關屬性全部未知；這張圖只顯示缺少資料的筆數，無法比較不同價格／營運模式。",
                                action="核對 CSV 的價格或營運模式欄位；未知不代表價格為零、收費或沒有廣告／內購。")
            else:
                ready = _result(n, known.sum(), requirements)
            if source == "mobile":
                coverage = {field: int(frame[field].notna().sum()) for field in ("free", "ad_supported", "in_app_purchases")}
                ready["field_coverage"] = coverage
                if ready["status"] == "available" and any(value < n for value in coverage.values()):
                    ready.update(status="limited", reason="部分營運屬性未提供；各屬性按自己的已知／未知筆數顯示，不能互相補值。",
                                 action="查看各組的有效筆數；若要比較缺失的營運模式，請補充對應 CSV 欄位。")
        elif ident == "revenue_concentration":
            known = frame.revenue.notna()
            positive_total = float(frame.revenue.sum()) > 0
            ready = _result(n, known.sum(), ["至少有 1 款已知估計營收，且營收總和必須大於零，才能計算累積百分比。"],
                            status=None if positive_total else "unavailable",
                            reason=None if positive_total else "已知估計營收的總和為零或沒有已知營收，累積百分比沒有定義。",
                            action=None if positive_total else "檢查來源營收資料或放寬篩選；零營收會保留為零，不能轉成虛構百分比。")
        elif ident == "top_games":
            valid = frame.revenue.notna() if chart["unit"] == "USD" else known_volume
            ready = _result(n, valid.sum(), ["至少有 1 款具備目前排名指標數值的遊戲。"])
        if ready is None:
            # Fail closed for a future chart that has not defined its inputs.
            ready = _result(n, 0, requirements, status="unavailable",
                            reason="這張圖尚未提供可核對的資料要求。", action="請使用其他分析圖表。")
        chart["availability"] = ready
    if comparison is not None:
        comparison["chart"]["availability"] = _comparison_readiness(comparison, "revenue" if source == "revenue" else None)
    return charts
