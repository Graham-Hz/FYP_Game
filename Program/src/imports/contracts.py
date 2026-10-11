"""Strict UTF-8 CSV contract and explicit descriptive-analysis eligibility rules."""
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pyarrow as pa

ROOT = Path(__file__).resolve().parents[2]
VERSION = "application_csv_v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 500_000
MAX_ISSUES = 100
csv.field_size_limit(32768)
HEADERS = {
    "pc": "app_id,title,release_date,observed_date,genres,planning_categories,developers,price_observed,owner_lower,owner_upper".split(","),
    "mobile": "app_id,title,release_date,observed_date,category,developer_id,free,ad_supported,in_app_purchases,minimum_installs,price,currency".split(","),
}
OUTCOMES = {"pc": "estimated_owner_interval", "mobile": "minimum_installs_lower_bound"}
GAME_CATEGORIES = "Action|Adventure|Arcade|Board|Card|Casino|Casual|Educational|Music|Puzzle|Racing|Role Playing|Simulation|Strategy|Trivia|Word".split("|")
PC_TIERS = ["O1_source_interval_up_to_20k", "O2_source_intervals_20k_to_100k", "O3_source_intervals_100k_plus"]
MOBILE_TIERS = ["M1_under_1k", "M2_1k_to_under_100k", "M3_100k_plus"]
FIELDS = {
    "pc": pa.schema([("app_id", pa.string()), ("title", pa.string()), ("genres", pa.list_(pa.string())),
                     ("planning_categories", pa.list_(pa.string())), ("target_tier", pa.string())]),
    "mobile": pa.schema([("app_id", pa.string()), ("title", pa.string()), ("category", pa.string()),
                         ("free", pa.bool_()), ("ad_supported", pa.bool_()), ("in_app_purchases", pa.bool_()),
                         ("target_tier", pa.string())]),
}
LEDGER_SCHEMA = pa.schema([("row", pa.int64()), ("app_id", pa.string()), ("included", pa.bool_()),
                          ("exclusions", pa.list_(pa.string())), ("warnings", pa.list_(pa.string()))])


def policies():
    paths = [ROOT / "config/analysis_v1.json", ROOT / "config/cleaning_candidate_v1.json"]
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def rule_fingerprint():
    # Bind snapshots to the actual validator and referenced eligibility settings.
    h = hashlib.sha256(Path(__file__).read_bytes())
    for p in (ROOT / "config/analysis_v1.json", ROOT / "config/cleaning_candidate_v1.json"):
        h.update(p.read_bytes())
    return h.hexdigest()


def iso_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期必須使用 YYYY-MM-DD。")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("日期不存在。") from None


def metadata_check(meta):
    required = {"platform", "source_name", "source_url", "snapshot_date", "outcome_definition", "data_kind", "price_currency"}
    if not isinstance(meta, dict) or set(meta) != required:
        raise ValueError("來源資料欄位不完整或包含未支援的欄位。")
    if any(not isinstance(v, str) for v in meta.values()):
        raise ValueError("來源資料必須是文字。")
    meta = {k: v.strip() for k, v in meta.items()}
    if meta["platform"] not in HEADERS:
        raise ValueError("平台必須是 pc 或 mobile。")
    if not meta["source_name"] or len(meta["source_name"]) > 200:
        raise ValueError("請提供來源名稱（最多 200 字）。")
    if len(meta["source_url"]) > 2000 or (meta["source_url"] and not re.match(r"https?://[^\s]+$", meta["source_url"])):
        raise ValueError("來源網址必須是 http(s) 網址或留空。")
    iso_date(meta["snapshot_date"])
    if meta["outcome_definition"] != OUTCOMES[meta["platform"]]:
        raise ValueError("Outcome 定義與平台不符。")
    if meta["data_kind"] not in {"historical", "synthetic"}:
        raise ValueError("資料類型必須是 historical 或 synthetic。")
    if meta["platform"] == "mobile":
        if meta["price_currency"] != "per_row":
            raise ValueError("Android 幣別需由每列 currency 指明（per_row）。")
    elif meta["price_currency"] != "unknown" and not re.fullmatch(r"[A-Z]{3}", meta["price_currency"]):
        raise ValueError("Steam 幣別須為三字母代碼，未核實則填 unknown。")
    return meta


def boolean(value):
    if value == "":
        return None
    if value.lower() not in {"true", "false"}:
        raise ValueError("布林值只接受 true、false 或空白（未知）。")
    return value.lower() == "true"


def number(value, integer=False):
    if value == "":
        return None
    if integer:
        if not re.fullmatch(r"[0-9]+", value) or len(value) > 18:
            raise ValueError("數量須為非負整數（最多 18 位）。")
        return int(value)
    try:
        result = float(value)
    except ValueError:
        raise ValueError("價格須為非負有限數值或空白。") from None
    if not math.isfinite(result) or result < 0:
        raise ValueError("價格須為非負有限數值或空白。")
    return result


def string_list(value):
    if value == "":
        return []
    try:
        xs = json.loads(value)
    except (ValueError, RecursionError):
        raise ValueError('集合須為 JSON 字串陣列，例如 ["Action","Adventure"]。') from None
    if not isinstance(xs, list) or len(xs) > 100 or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in xs):
        raise ValueError("集合最多 100 個非空字串，每個最多 200 字。")
    return list(dict.fromkeys(x.strip() for x in xs))


def validate(raw, metadata):
    """Return bounded diagnostics plus typed eligible rows and a complete row ledger."""
    meta = metadata_check(metadata)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("CSV 必須非空且不超過 64 MiB。")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV 必須使用 UTF-8 編碼。") from None
    if "\x00" in text:
        raise ValueError("CSV 包含 NUL 字元。")
    platform = meta["platform"]
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise ValueError("CSV 缺少有效表頭。") from None
    if len(header) != len(set(header)) or set(header) != set(HEADERS[platform]):
        raise ValueError("CSV 表頭不符。請使用此平台的範本，勿增加、遺漏或重複欄名。")
    analysis, cleaning = policies()
    rows, ledger, issues = [], [], []
    errors, exclusions, warnings, tiers = Counter(), Counter(), Counter(), Counter()
    ids = set()
    total = 0
    def issue(row, field, message):
        errors[field] += 1
        if len(issues) < MAX_ISSUES:
            issues.append({"row": row, "field": field, "message": message})
    try:
        for total, values in enumerate(reader, 1):
            record_number = total + 1
            if total > MAX_ROWS:
                raise ValueError("CSV 超過 500,000 筆上限。")
            if len(values) != len(header):
                issue(record_number, "row_width", "欄位數量與表頭不同。")
                continue
            r = dict(zip(header, (v.strip() for v in values)))
            start_errors = sum(errors.values())
            if not r["app_id"] or len(r["app_id"]) > 300:
                issue(record_number, "app_id", "ID 不可空白且最多 300 字。")
            elif r["app_id"] in ids:
                issue(record_number, "app_id", "同一快照內 ID 重複，請先處理來源資料。")
            ids.add(r["app_id"])
            if len(r["title"]) > 500:
                issue(record_number, "title", "名稱最多 500 字。")
            excluded, warned = [], []
            if not r["title"]:
                excluded.append("missing_title")
            dates = {}
            for key in ("release_date", "observed_date"):
                if not r[key]:
                    if key == "observed_date":
                        dates[key] = iso_date(meta["snapshot_date"])
                        warned.append("observation_uses_snapshot_proxy")
                    else:
                        dates[key] = None
                        excluded.append("missing_release_date")
                else:
                    try:
                        dates[key] = iso_date(r[key])
                    except ValueError as exc:
                        dates[key] = None
                        issue(record_number, key, str(exc))
            if dates.get("release_date") and dates.get("observed_date") and dates["release_date"] > dates["observed_date"]:
                excluded.append("release_after_observation")
            if dates.get("observed_date") and dates["observed_date"] > iso_date(meta["snapshot_date"]):
                issue(record_number, "observed_date", "觀察日期不可晚於此快照的截至日期。")
            parsed = {}
            parsers = ({"genres": string_list, "planning_categories": string_list, "developers": string_list,
                        "price_observed": number, "owner_lower": lambda x: number(x, True), "owner_upper": lambda x: number(x, True)}
                       if platform == "pc" else
                       {"free": boolean, "ad_supported": boolean, "in_app_purchases": boolean,
                        "minimum_installs": lambda x: number(x, True), "price": number})
            for field, parser in parsers.items():
                try:
                    parsed[field] = parser(r[field])
                except (ValueError, OverflowError) as exc:
                    issue(record_number, field, str(exc))
            if sum(errors.values()) != start_errors:
                continue
            tier = None
            if platform == "pc":
                if set(parsed["planning_categories"]) - set(analysis["pc_planning_categories"]):
                    issue(record_number, "planning_categories", "包含未支援的規劃功能；請按欄位字典轉換。")
                if not parsed["genres"]:
                    excluded.append("missing_genres")
                elif set(parsed["genres"]) <= set(cleaning["software_only_genres"]):
                    excluded.append("software_only_heuristic")
                if not any(x.casefold() not in analysis["developer_placeholder_tokens"] for x in parsed["developers"]):
                    excluded.append("unknown_developer")
                if parsed["price_observed"] is None or parsed["price_observed"] <= 0:
                    excluded.append("nonpositive_or_missing_price")
                if re.search(cleaning["pc_demo_title_pattern"], r["title"], re.I) and r["app_id"] not in analysis["pc_demo_exceptions"]:
                    excluded.append("demo_playtest_title_heuristic")
                lower, upper = parsed["owner_lower"], parsed["owner_upper"]
                if (lower is None) != (upper is None) or (lower is not None and lower > upper):
                    issue(record_number, "owner_interval", "上下界必須同時存在且下界不大於上界。")
                elif lower is None or upper == 0:
                    excluded.append("unknown_owners")
                elif upper <= 20000:
                    tier = PC_TIERS[0]
                elif lower >= 100000:
                    tier = PC_TIERS[2]
                elif lower >= 20000 and upper <= 100000:
                    tier = PC_TIERS[1]
                else:
                    excluded.append("owner_interval_straddles_tiers")
                row = {k: parsed[k] for k in ("genres", "planning_categories")}
            else:
                if r["category"] not in GAME_CATEGORIES:
                    excluded.append("outside_game_categories")
                if r["developer_id"].casefold() in analysis["developer_placeholder_tokens"]:
                    excluded.append("unknown_developer")
                price, free = parsed["price"], parsed["free"]
                if price is not None and ((free is True and price > 0) or (free is False and price == 0)):
                    parsed["free"] = None
                    warned.append("free_price_conflict_masked")
                if r["currency"] and not re.fullmatch(r"[A-Z]{3}", r["currency"]):
                    issue(record_number, "currency", "幣別須為三個大寫字母，未知則留空。")
                if r["currency"] != "USD" or price is None:
                    warned.append("usd_price_unavailable")
                for key in ("free", "ad_supported", "in_app_purchases"):
                    if parsed[key] is None:
                        warned.append(f"unknown_{key}")
                installs = parsed["minimum_installs"]
                if installs is None:
                    excluded.append("unknown_installs")
                else:
                    tier = MOBILE_TIERS[0 if installs < 1000 else 1 if installs < 100000 else 2]
                row = {k: parsed[k] for k in ("free", "ad_supported", "in_app_purchases")}
                row["category"] = r["category"]
            if sum(errors.values()) != start_errors:
                continue
            exclusions.update(excluded)
            warnings.update(warned)
            ledger.append({"row": record_number, "app_id": r["app_id"], "included": not excluded,
                           "exclusions": excluded, "warnings": warned})
            if not excluded:
                row.update(app_id=r["app_id"], title=r["title"], target_tier=tier)
                rows.append(row)
                tiers[tier] += 1
    except csv.Error as exc:
        raise ValueError(f"CSV 格式錯誤：{exc}") from None
    if total == 0:
        issue(1, "rows", "範本只有表頭，請加入實際資料。")
    summary = {"contract_version": VERSION, "rule_sha256": rule_fingerprint(), "metadata": meta,
               "input_sha256": hashlib.sha256(raw).hexdigest(), "input_bytes": len(raw),
               "total_rows": total, "eligible_rows": len(rows), "excluded_rows": sum(not x["included"] for x in ledger),
               "invalid_rows": total - len(ledger), "error_count": sum(errors.values()), "errors_by_field": dict(errors),
               "issues": issues, "issues_truncated": sum(errors.values()) > len(issues),
               "exclusions": dict(exclusions), "warnings": dict(warnings), "tiers": dict(tiers),
               "can_import": not errors and bool(rows), "sample": rows[:5],
               "scope": "Application snapshot only; no research split, model training or automatic prediction."}
    return summary, pa.Table.from_pylist(rows, schema=FIELDS[platform]), pa.Table.from_pylist(ledger, schema=LEDGER_SCHEMA)


def template(platform):
    if platform not in HEADERS:
        raise ValueError("Unknown platform")
    out = io.StringIO(newline="")
    csv.writer(out).writerow(HEADERS[platform])
    return out.getvalue().encode("utf-8-sig")
