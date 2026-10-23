"""Descriptive metrics for a selected revenue sample, never success forecasts."""
import math


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def price_band(price):
    if price == 0:
        return "0"
    if price < 10:
        return "0 < price < 10"
    if price < 20:
        return "10 <= price < 20"
    if price < 30:
        return "20 <= price < 30"
    return "price >= 30"


def summary(rows):
    values = [r["revenue"] for r in rows]
    total = math.fsum(values)
    top_n = math.ceil(len(values) * 0.1)
    top = math.fsum(sorted(values, reverse=True)[:top_n])
    return {"count": len(values), "total_revenue": total if values else None,
            "median_revenue": percentile(values, .5), "q25": percentile(values, .25),
            "q75": percentile(values, .75), "mean_revenue": total / len(values) if values else None,
            "top_decile_count": top_n, "top_decile_share": top / total if total > 0 else None,
            "genre_matched_count": sum(r["genre_status"] == "matched" for r in rows),
            "small_sample": 0 < len(values) < 30}


def groups(rows, field):
    buckets = {}
    for row in rows:
        labels = row[field] if isinstance(row[field], list) else [row[field]]
        for label in labels:
            buckets.setdefault(label, []).append(row)
    return [{"label": key, **summary(value)} for key, value in sorted(buckets.items())]


def analyze(rows, filters=None):
    filters = filters or {}
    if set(filters) - {"mode", "genre", "publisher", "q"}:
        raise ValueError("Unknown revenue filter")
    if any(not isinstance(v, str) for v in filters.values()):
        raise ValueError("Filters must be strings")
    mode = filters.get("mode", "positive")
    if mode not in {"positive", "zero", "all"}:
        raise ValueError("Invalid price group")
    genre, publisher, query = (filters.get(k, "") for k in ("genre", "publisher", "q"))
    if len(query) > 100:
        raise ValueError("Search is limited to 100 characters")
    if genre and genre not in {g for r in rows for g in r["genres"]}:
        raise ValueError("Unknown genre")
    if publisher and publisher not in {r["publisher_class"] for r in rows}:
        raise ValueError("Unknown publisher class")
    chosen = [r for r in rows if (mode == "all" or (r["price"] > 0 if mode == "positive" else r["price"] == 0))
              and (not genre or genre in r["genres"])
              and (not publisher or publisher == r["publisher_class"])
              and (not query or query.casefold() in r["name"].casefold())]
    limits = [("< 100,000", 0, 100000), ("100,000 to < 1 million", 100000, 1000000),
              ("1 to < 10 million", 1000000, 10000000), (">= 10 million", 10000000, math.inf)]
    distribution = [{"label": label, "count": sum(low <= r["revenue"] < high for r in chosen)}
                    for label, low, high in limits]
    return {"filters": {"mode": mode, "genre": genre, "publisher": publisher, "q": query},
            "summary": summary(chosen), "distribution": distribution,
            "by_price": groups(chosen, "price_band"), "by_genre": groups(chosen, "genres"),
            "rows": sorted(chosen, key=lambda r: (-r["revenue"], r["steam_id"]))}
