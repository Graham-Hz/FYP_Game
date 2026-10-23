"""Transparent genre/price reference retrieval; no revenue-based ranking."""
import math
from fractions import Fraction
from decimal import Decimal

# Restrict matching to gameplay genres. Provider labels such as Indie, Early
# Access and Free To Play, and software categories, are not gameplay similarity.
REFERENCE_GENRES = frozenset({"Action", "Adventure", "Casual", "Massively Multiplayer",
                              "RPG", "Racing", "Simulation", "Sports", "Strategy"})
METHOD = {
    "version": "genre_price_references_v1",
    "eligibility": "At least one shared supported gameplay genre; separate positive and zero observed-price cohorts; optional symmetric price-ratio bound.",
    "genre_similarity": "Jaccard = shared gameplay genres / union of requested and candidate gameplay genres. Non-gameplay source labels are excluded.",
    "ranking": ["genre similarity descending", "absolute observed-price difference ascending", "numeric Steam ID ascending"],
    "ranking_inputs": ["gameplay genres", "observed price", "Steam ID for ties"],
    "outcome_use": "Revenue is attached after selection for historical reference only; it does not affect candidate eligibility or ranking.",
    "supported_genres": sorted(REFERENCE_GENRES),
    "interpretation": "Selected high-revenue historical sample, not a representative market or forecast. Matching does not establish equal quality, budget, audience or launch conditions.",
}


def comparable_games(rows, request):
    if not isinstance(request, dict) or set(request) != {"genres", "price", "limit", "price_factor"}:
        raise ValueError("Expected genres, price, limit and price_factor")
    genres, price, limit, factor = (request[k] for k in ("genres", "price", "limit", "price_factor"))
    if not isinstance(genres, list) or not 1 <= len(genres) <= len(REFERENCE_GENRES) or any(not isinstance(g, str) for g in genres):
        raise ValueError("Select at least one supported gameplay genre")
    requested = set(genres)
    if len(requested) != len(genres) or not requested <= REFERENCE_GENRES:
        raise ValueError("Duplicate or unsupported gameplay genre")
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not 0 <= price <= 1000 or not math.isfinite(price):
        raise ValueError("Price must be finite and between 0 and 1000 USD")
    if type(limit) is not int or limit not in {5, 10, 20}:
        raise ValueError("Reference count must be 5, 10 or 20")
    if factor is not None and (isinstance(factor, bool) or not isinstance(factor, (int, float)) or factor not in {1.5, 2, 3}):
        raise ValueError("Price factor must be 1.5, 2, 3 or null")
    target_price = Decimal(str(price))
    ratio = Decimal(str(factor)) if factor is not None else None
    eligible = []
    coverage = {"source_rows": len(rows), "supported_genre_rows": 0,
                "same_price_cohort_rows": 0, "shared_genre_rows": 0, "within_price_range_rows": 0}
    for row in rows:
        candidate = set(row["genres"]) & REFERENCE_GENRES
        if not candidate:
            continue
        coverage["supported_genre_rows"] += 1
        if (price == 0) != (row["price"] == 0):
            continue
        coverage["same_price_cohort_rows"] += 1
        shared = requested & candidate
        if not shared:
            continue
        coverage["shared_genre_rows"] += 1
        # Zero-price queries only see zero-price candidates; ratio is inapplicable.
        candidate_price = Decimal(str(row["price"]))
        if price > 0 and ratio is not None and (candidate_price * ratio < target_price or candidate_price > target_price * ratio):
            continue
        coverage["within_price_range_rows"] += 1
        union = requested | candidate
        eligible.append((Fraction(len(shared), len(union)), abs(candidate_price - target_price), row,
                         sorted(shared), sorted(candidate), len(union)))
    eligible.sort(key=lambda item: (-item[0], item[1], int(item[2]["steam_id"])))
    selected = [{**row, "match": {"shared_genres": shared, "candidate_gameplay_genres": candidate,
                 "shared_count": len(shared), "union_count": union, "genre_similarity": float(score),
                 "price_difference_usd": float(difference)}}
                for score, difference, row, shared, candidate, union in eligible[:limit]]
    lower, upper = (0, 0) if price == 0 else ((None, None) if ratio is None else (float(target_price / ratio), float(target_price * ratio)))
    return {"request": {"genres": sorted(requested), "price": price, "limit": limit, "price_factor": factor},
            "method": METHOD, "coverage": coverage, "candidate_count": len(eligible), "returned_count": len(selected),
            "price_range": {"minimum": lower, "maximum": upper, "inclusive": True},
            "status": "no_matches" if not selected else "fewer_than_requested" if len(selected) < limit else "available",
            "rows": selected}
