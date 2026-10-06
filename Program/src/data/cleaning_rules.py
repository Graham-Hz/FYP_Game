"""Conservative parsers: preserve ambiguous text and separate unknown labels."""
import ast
import math
import re

import pandas as pd


def title_missing(value):
    return value is None or pd.isna(value) or not str(value).strip()


def collection(value):
    """Parse source list syntax, never silently split developer names on commas."""
    if title_missing(value):
        return [], "missing"
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return [], "invalid"
    if not isinstance(parsed, list) or any(not isinstance(x, str) for x in parsed):
        return [], "invalid"
    cleaned = list(dict.fromkeys(x.strip() for x in parsed if x.strip()))
    return cleaned, "valid" if cleaned else "empty"


def nonnegative(values, integer=False):
    number = pd.to_numeric(values, errors="coerce")
    valid = number.notna() & number.ge(0) & number.map(lambda x: pd.notna(x) and math.isfinite(x))
    if integer:
        valid &= number.mod(1).eq(0)
    return number.where(valid).astype("Int64" if integer else "Float64")


def boolean(values):
    return values.astype("string").str.strip().str.lower().map({"true": True, "false": False}).astype("boolean")


def owner_interval(value):
    """Return lower, upper, tier, status without converting intervals to point sales."""
    if title_missing(value):
        return None, None, None, "missing"
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", str(value).strip())
    if not match:
        return None, None, None, "invalid"
    lower, upper = map(int, match.groups())
    if lower > upper:
        return lower, upper, None, "invalid"
    if upper == 0:
        return lower, upper, None, "unknown_0_0"
    if upper <= 20_000:
        tier = "O1_source_interval_up_to_20k"
    elif lower >= 100_000:
        tier = "O3_source_intervals_100k_plus"
    elif lower >= 20_000 and upper <= 100_000:
        tier = "O2_source_intervals_20k_to_100k"
    else:
        return lower, upper, None, "straddles_threshold"
    return lower, upper, tier, "labelled"


def install_tiers(values):
    labels = pd.Series(pd.NA, index=values.index, dtype="string")
    labels.loc[values.lt(1000).fillna(False)] = "M1_under_1k"
    labels.loc[(values.ge(1000) & values.lt(100000)).fillna(False)] = "M2_1k_to_under_100k"
    labels.loc[values.ge(100000).fillna(False)] = "M3_100k_plus"
    return labels
