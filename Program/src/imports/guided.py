"""Explicit, user-confirmed field mapping for game snapshot exploration.

This contract is separate from application_csv_v1.  It preserves usable
exploration records and obtains a stricter comparison subset from the unchanged
legacy validator.  No inferred sales semantics, currency conversion, model
training, or arbitrary time-series ingestion takes place here.
"""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pyarrow as pa

from analysis.game_taxonomy import gameplay
from imports import contracts

VERSION = "application_guided_csv_v1"
MAX_COLUMNS = 256
MAX_SAFE_NUMBER = 2 ** 53 - 1
OPTION_VALUES = {
    "delimiter": {",", ";", "\t"},
    "date_format": {"iso", "dmy", "mdy"},
    "list_separator": {"json", ";", "|", ","},
    "boolean_format": {"true_false", "yes_no", "one_zero"},
    "number_format": {"plain", "thousands_comma"},
    "id_policy": {"source", "row_number"},
}
DEFAULT_OPTIONS = {"delimiter": ",", "date_format": "iso", "list_separator": "json",
                   "boolean_format": "true_false", "number_format": "plain", "id_policy": "source"}
LABELS = {
    "app_id": ("遊戲識別碼", "同一快照不可重複；沒有來源 ID 時，可明確選擇只供本檔案使用的列編號。"),
    "title": ("遊戲名稱", "必須對照；空白名稱的紀錄不納入探索。"),
    "release_date": ("發售日期", "不是下載／銷售發生日期；缺少時仍可使用其他有效欄位。"),
    "observed_date": ("資料觀察日期", "留空時使用來源快照日期作代理，並留下紀錄。"),
    "genres": ("遊戲類型／來源標籤", "可使用 JSON 陣列或明確指定的分隔符；玩法與其他標籤分開展示。"),
    "planning_categories": ("規劃功能標籤", "選填；只接受既定的遊玩功能，例如 Single-player、Co-op。"),
    "developers": ("開發者", "選填；缺少時仍可探索，但不能進入較嚴格的規劃比較樣本。"),
    "price_observed": ("觀察價格", "非負數值；幣別由來源設定確認，不自動換算貨幣。"),
    "owner_lower": ("估計擁有者下界", "必須和上界一起提供；不可用售出份數、下載量或收入代替。"),
    "owner_upper": ("估計擁有者上界", "必須和下界一起提供；0–0 按來源規則視為未知。"),
    "category": ("Google Play 遊戲類別", "使用既定 16 類遊戲；未識別類別保留原文，但不混入類別比較。"),
    "developer_id": ("開發者識別資料", "選填；缺少時仍可使用其他探索分析。"),
    "free": ("免費下載標記", "空白表示未知；格式由下方選項明確指定。"),
    "ad_supported": ("廣告標記", "空白表示未知，不自動當成沒有廣告。"),
    "in_app_purchases": ("應用程式內購標記", "空白表示未知，不自動當成沒有內購。"),
    "minimum_installs": ("累積安裝量下限", "需要來源提供的下限；不是精確下載次數、售出份數或營收。"),
    "price": ("觀察價格", "非負數值；目前 Android 價格圖只使用已確認的 USD 紀錄。"),
    "currency": ("每列價格幣別", "三字母代碼，例如 USD；未知或非 USD 價格不混入美元圖表。"),
}
ALIASES = {
    "app_id": {"app_id", "appid", "app id", "steam id", "steamid", "game id", "package name"},
    "title": {"title", "name", "game name", "app name"},
    "release_date": {"release_date", "release date", "released", "launch date"},
    "observed_date": {"observed_date", "observed date", "scraped time", "scrape date", "snapshot date"},
    "genres": {"genres", "genre", "game genres", "game genre"},
    "planning_categories": {"planning_categories", "planning categories"},
    "developers": {"developers", "developer", "studio"},
    "price_observed": {"price_observed", "observed price", "price"},
    "owner_lower": {"owner_lower", "owners_lower", "owner lower", "owners lower", "owners lower bound"},
    "owner_upper": {"owner_upper", "owners_upper", "owner upper", "owners upper", "owners upper bound"},
    "category": {"category", "game category", "genre"},
    "developer_id": {"developer_id", "developer id", "developer", "studio"},
    "free": {"free", "is free"},
    "ad_supported": {"ad_supported", "ad supported", "contains ads"},
    "in_app_purchases": {"in_app_purchases", "in app purchases", "iap"},
    "minimum_installs": {"minimum_installs", "minimum installs", "installs lower bound"},
    "price": {"price", "observed price"},
    "currency": {"currency", "price currency"},
}
EXPLORATION_SCHEMAS = {
    "pc": pa.schema([
        ("app_id", pa.string()), ("title", pa.string()), ("release_date", pa.string()),
        ("observed_date", pa.string()), ("genres", pa.list_(pa.string())),
        ("planning_categories", pa.list_(pa.string())), ("developers", pa.list_(pa.string())),
        ("price_observed", pa.float64()), ("owner_lower", pa.int64()), ("owner_upper", pa.int64()),
        ("target_tier", pa.string()),
    ]),
    "mobile": pa.schema([
        ("app_id", pa.string()), ("title", pa.string()), ("release_date", pa.string()),
        ("observed_date", pa.string()), ("category", pa.string()), ("developer_id", pa.string()),
        ("free", pa.bool_()), ("ad_supported", pa.bool_()), ("in_app_purchases", pa.bool_()),
        ("minimum_installs", pa.int64()), ("price", pa.float64()), ("currency", pa.string()),
        ("target_tier", pa.string()),
    ]),
}
LEDGER_SCHEMA = pa.schema([
    ("row", pa.int64()), ("app_id", pa.string()), ("included", pa.bool_()),
    ("comparison_included", pa.bool_()), ("invalid", pa.bool_()),
    ("exclusions", pa.list_(pa.string())), ("comparison_exclusions", pa.list_(pa.string())),
    ("warnings", pa.list_(pa.string())), ("error_fields", pa.list_(pa.string())),
])


def rule_fingerprint():
    digest = hashlib.sha256(Path(__file__).read_bytes())
    digest.update(contracts.rule_fingerprint().encode("ascii"))
    digest.update((contracts.ROOT / "src/analysis/game_taxonomy.py").read_bytes())
    return digest.hexdigest()


def _text(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= contracts.MAX_BYTES:
        raise ValueError("CSV 必須非空且不超過 64 MiB。")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("CSV 必須使用 UTF-8 編碼。") from None
    if "\x00" in text:
        raise ValueError("CSV 包含 NUL 字元。")
    return text


def _reader(text, delimiter):
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise ValueError("CSV 缺少有效表頭。") from None
    if not header or len(header) > MAX_COLUMNS or any(not h.strip() or len(h) > 300 for h in header):
        raise ValueError("CSV 需有非空欄名；最多 256 欄，每個欄名最多 300 字。")
    if len(header) != len(set(header)):
        raise ValueError("CSV 欄名重複，請先為每一欄提供唯一名稱。")
    return header, reader


def _normal_name(value):
    return re.sub(r"[\s_-]+", " ", value.strip().casefold())


def inspect(raw, platform):
    """Suggest header aliases; suggestions never authorize semantic conversion."""
    if not isinstance(platform, str) or platform not in contracts.HEADERS:
        raise ValueError("平台必須是 pc 或 mobile。")
    text = _text(raw)
    try:
        delimiter = csv.Sniffer().sniff(text[:65536], delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","
    header, reader = _reader(text, delimiter)
    sample = []
    try:
        for index, values in enumerate(reader):
            if index >= 5:
                break
            if len(values) != len(header):
                raise ValueError("預覽中的欄位數量與表頭不同；請檢查 CSV 分隔符及引號。")
            sample.append(dict(zip(header, (v[:300] for v in values))))
    except csv.Error as exc:
        raise ValueError(f"CSV 格式錯誤：{exc}") from None
    suggestions = {}
    for field in contracts.HEADERS[platform]:
        candidates = [name for name in header if _normal_name(name) in {_normal_name(x) for x in ALIASES[field]}]
        # Two equally plausible columns require a deliberate choice.
        if len(candidates) == 1:
            suggestions[field] = candidates[0]
    reused = Counter(suggestions.values())
    suggestions = {k: v for k, v in suggestions.items() if reused[v] == 1}
    return {
        "contract_version": VERSION, "headers": header, "sample": sample,
        "suggestions": suggestions, "delimiter": delimiter,
        "fields": [{"id": key, "label": LABELS[key][0], "description": LABELS[key][1]}
                   for key in contracts.HEADERS[platform]],
        "guidance": [
            "建議只依欄名提供，請核對實際內容及來源定義後確認；來源網址不會被自動開啟或核實。",
            "每行代表一款遊戲的快照。每月／每日重複紀錄需要另一種時間序列格式，這裡不自動合併。",
            "Owners、安裝下限、售出份數和營收不能互相代替；未對照欄位保存在原始檔，不參與分析。",
        ],
    }


def _options(options):
    if not isinstance(options, dict) or set(options) - (set(OPTION_VALUES) | {"confirmed_semantics"}):
        raise ValueError("匯入選項包含未支援的設定。")
    if options.get("confirmed_semantics") is not True:
        raise ValueError("請先確認平台、每行資料的單位、日期、貨幣及數量指標的實際意思。")
    result = {**DEFAULT_OPTIONS, **options}
    for key, choices in OPTION_VALUES.items():
        if not isinstance(result[key], str) or result[key] not in choices:
            raise ValueError(f"不支援的格式設定：{key}。")
    return result


def _date(value, date_format):
    if not value:
        return None
    if date_format == "iso":
        result = contracts.iso_date(value)
    else:
        match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
        if not match:
            raise ValueError("此日期設定需要 DD/MM/YYYY 或 MM/DD/YYYY；不自動猜測混合格式。")
        a, b, year = map(int, match.groups())
        try:
            result = date(year, b, a) if date_format == "dmy" else date(year, a, b)
        except ValueError:
            raise ValueError("日期不存在，或不符合已選擇的年月日順序。") from None
    if not 1678 <= result.year <= 2261:
        raise ValueError("目前圖表支援的日期年份為 1678–2261。")
    return result.isoformat()


def _numeric(value, integer, number_format):
    if number_format == "thousands_comma" and "," in value:
        if not re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", value):
            raise ValueError("千分位格式不正確，例如 1,000；不接受貨幣符號、k 或 +。")
        value = value.replace(",", "")
    parsed = contracts.number(value, integer)
    if parsed is not None and parsed > MAX_SAFE_NUMBER:
        raise ValueError("數值超過網頁可準確表示的範圍 9,007,199,254,740,991。")
    return parsed


def _boolean(value, boolean_format):
    if not value:
        return None
    choices = {"true_false": {"true": True, "false": False},
               "yes_no": {"yes": True, "no": False}, "one_zero": {"1": True, "0": False}}[boolean_format]
    if value.casefold() not in choices:
        raise ValueError("布林值不符合已選擇的格式；空白才表示未知。")
    return choices[value.casefold()]


def _list(value, separator):
    if not value:
        return []
    if separator == "json":
        return contracts.string_list(value)
    return contracts.string_list(json.dumps([v.strip() for v in value.split(separator) if v.strip()], ensure_ascii=False))


def _serialize(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _readiness(rows, platform, comparison_rows):
    total = len(rows)
    def volume(row):
        return row["owner_lower"] is not None and row["owner_upper"] is not None if platform == "pc" else row["minimum_installs"] is not None
    def price(row):
        return row["price_observed"] is not None if platform == "pc" else row["price"] is not None and row["currency"] == "USD"
    def groups(row):
        return bool(gameplay(row["genres"])) if platform == "pc" else row["category"] is not None
    relation = ("price_volume", "價格與數量關係", sum(price(r) and volume(r) for r in rows),
                "需要同一紀錄同時有有效價格與數量；相關係數另檢查樣本量及變異。") if platform == "pc" else (
                "age_installs", "發售日數與安裝量關係", sum(volume(r) and r["release_date"] is not None for r in rows),
                "需要同一紀錄同時有發售日期、觀測日期及安裝下限；相關係數另檢查樣本量及變異。")
    definitions = [
        ("genre_counts", "遊戲類型數量", sum(groups(r) for r in rows), "需要本項目可識別的玩法類型／Google Play 遊戲類別。"),
        ("price_distribution", "價格分布", sum(price(r) for r in rows), "需要有效價格；Android 只使用已確認的 USD，Steam 使用已宣告的同一幣別。"),
        ("volume_distribution", "數量分布與排名", sum(volume(r) for r in rows), "需要已確認的 owners 區間／累積安裝下限；不能以營收或銷量代替。"),
        relation,
        ("release_cohorts", "按發售時間比較", sum(r["release_date"] is not None for r in rows), "需要有效發售日期；這不是逐月銷售時間序列。"),
        ("comparison", "Step 1 規劃分層比較", comparison_rows, "另外要求既定日期、開發者、類型及數量分層等條件；不影響其他探索圖表。"),
    ]
    return [{"id": key, "label": label, "usable_rows": count, "total_rows": total,
             "status": "unavailable" if count == 0 else "limited" if count < total else "available",
             "reason": reason} for key, label, count, reason in definitions]


def prepare(raw, metadata, mapping, options):
    """Normalize confirmed mappings and retain independent exploration eligibility."""
    meta = contracts.metadata_check(metadata)
    options = _options(options)
    _date(meta["snapshot_date"], "iso")
    header, reader = _reader(_text(raw), options["delimiter"])
    platform = meta["platform"]
    if not isinstance(mapping, dict) or set(mapping) - set(contracts.HEADERS[platform]):
        raise ValueError("欄位對照包含未支援的目的欄位。")
    if any(not isinstance(v, str) or (v and v not in header) for v in mapping.values()):
        raise ValueError("對照必須指向這份 CSV 中存在的欄名，或留空。")
    mapping = {k: v for k, v in mapping.items() if v}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("同一來源欄位不能重複指定給不同意思的欄位。")
    useful = {"genres", "release_date", "price_observed", "owner_lower", "owner_upper"} if platform == "pc" else {
        "category", "release_date", "price", "minimum_installs", "free", "ad_supported", "in_app_purchases"}
    if "title" not in mapping or not set(mapping) & useful:
        raise ValueError("請對照遊戲名稱，以及至少一個可供分析的類型、日期、價格或數量欄位。")
    if options["id_policy"] == "source" and "app_id" not in mapping:
        raise ValueError("請對照來源 ID，或明確選擇本檔案專用的列編號。")
    if options["id_policy"] == "row_number" and "app_id" in mapping:
        raise ValueError("使用本檔案列編號時，請把來源 ID 對照留空，避免混淆。")
    if platform == "pc" and (("owner_lower" in mapping) != ("owner_upper" in mapping)):
        raise ValueError("估計擁有者上下界必須一起對照；只有單一數字時不要推斷另一個界限。")
    analysis, cleaning = contracts.policies()
    errors, warnings, excluded_counts = Counter(), Counter(), Counter()
    issues, parsed_records, ledger, ids = [], [], [], set()
    raw_hash = hashlib.sha256(raw).hexdigest()
    def issue(row, field, message):
        errors[field] += 1
        if len(issues) < contracts.MAX_ISSUES:
            issues.append({"row": row, "field": field, "message": message})
    total = 0
    try:
        for total, values in enumerate(reader, 1):
            line = total + 1
            if total > contracts.MAX_ROWS:
                raise ValueError("CSV 超過 500,000 筆上限。")
            entry = {"row": line, "app_id": "", "included": False, "comparison_included": False,
                     "invalid": False, "exclusions": [], "comparison_exclusions": [], "warnings": [], "error_fields": []}
            ledger.append(entry)
            if len(values) != len(header):
                issue(line, "row_width", "欄位數量與表頭不同。")
                entry.update(invalid=True, error_fields=["row_width"])
                continue
            source = dict(zip(header, values))
            canonical = {key: source[mapping[key]].strip() if key in mapping else "" for key in contracts.HEADERS[platform]}
            if options["id_policy"] == "row_number":
                canonical["app_id"] = f"local-row-{raw_hash[:16]}-{total}"
                entry["warnings"].append("local_row_id_not_platform_identity")
            entry["app_id"] = canonical["app_id"]
            def bad(field, message):
                issue(line, field, message)
                entry["error_fields"].append(field)
            if not canonical["app_id"] or len(canonical["app_id"]) > 300:
                bad("app_id", "ID 不可空白且最多 300 字。")
            elif canonical["app_id"] in ids:
                bad("app_id", "同一快照內 ID 重複；不會自動刪除、合併或視為時間序列。")
            ids.add(canonical["app_id"])
            if len(canonical["title"]) > 500:
                bad("title", "名稱最多 500 字。")
            typed = dict(canonical)
            parsers = {"release_date": lambda x: _date(x, options["date_format"]),
                       "observed_date": lambda x: _date(x, options["date_format"])}
            if platform == "pc":
                parsers.update({key: lambda x: _list(x, options["list_separator"]) for key in ("genres", "developers", "planning_categories")})
                parsers.update({key: lambda x: _numeric(x, True, options["number_format"]) for key in ("owner_lower", "owner_upper")})
                parsers["price_observed"] = lambda x: _numeric(x, False, options["number_format"])
            else:
                parsers.update({key: lambda x: _boolean(x, options["boolean_format"]) for key in ("free", "ad_supported", "in_app_purchases")})
                parsers["minimum_installs"] = lambda x: _numeric(x, True, options["number_format"])
                parsers["price"] = lambda x: _numeric(x, False, options["number_format"])
            for field, parser in parsers.items():
                try:
                    typed[field] = parser(canonical[field])
                except (ValueError, OverflowError) as exc:
                    typed[field] = None
                    bad(field, str(exc))
            if entry["error_fields"]:
                entry["invalid"] = True
                continue
            if platform == "pc":
                if set(typed["planning_categories"]) - set(analysis["pc_planning_categories"]):
                    bad("planning_categories", "包含未支援的規劃功能；可取消這個選填欄位的對照。")
                lower, upper = typed["owner_lower"], typed["owner_upper"]
                if (lower is None) != (upper is None) or (lower is not None and lower > upper):
                    bad("owner_interval", "上下界必須同時有值，且下界不大於上界。")
            else:
                typed["currency"] = typed["currency"].upper()
                if typed["currency"] and not re.fullmatch(r"[A-Z]{3}", typed["currency"]):
                    bad("currency", "幣別須為三個字母，未知則留空。")
                if len(typed["developer_id"]) > 500 or len(typed["category"]) > 200:
                    bad("category_or_developer", "類別最多 200 字，開發者最多 500 字。")
            if typed["observed_date"] and typed["observed_date"] > meta["snapshot_date"]:
                bad("observed_date", "觀察日期不可晚於此快照的截至日期。")
            if entry["error_fields"]:
                entry["invalid"] = True
                continue
            parsed_records.append((entry, typed))
    except csv.Error as exc:
        raise ValueError(f"CSV 格式錯誤：{exc}") from None
    if not total:
        issue(1, "rows", "CSV 只有表頭，請加入實際資料。")

    # Normalized CSV preserves the confirmed content, including values that are
    # not eligible for a particular analysis.  Explorer masking is separate.
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=contracts.HEADERS[platform])
    writer.writeheader()
    writer.writerows({key: _serialize(record[key]) for key in contracts.HEADERS[platform]} for _, record in parsed_records)
    normalized_csv = output.getvalue().encode("utf-8-sig")
    strict, comparison, strict_ledger = contracts.validate(normalized_csv, meta)
    # All legacy format restrictions are deliberately checked above; missing
    # optional values and cohort restrictions should only affect eligibility.
    for problem in strict["issues"]:
        if problem["field"] == "rows" and not parsed_records:
            continue
        index = problem["row"] - 2
        source_line = parsed_records[index][0]["row"] if 0 <= index < len(parsed_records) else 1
        issue(source_line, problem["field"], problem["message"])
    strict_by_row = {item["row"]: item for item in strict_ledger.to_pylist()}
    exploration = []
    for index, (entry, original) in enumerate(parsed_records, 2):
        strict_entry = strict_by_row.get(index)
        if strict_entry:
            entry["comparison_included"] = strict_entry["included"]
            entry["comparison_exclusions"] = strict_entry["exclusions"]
        row = dict(original)
        if not row["title"]:
            entry["exclusions"].append("missing_title")
        if not row["observed_date"]:
            row["observed_date"] = meta["snapshot_date"]
            entry["warnings"].append("observation_uses_snapshot_proxy")
        if row["release_date"] and row["release_date"] > row["observed_date"]:
            row["release_date"] = None
            entry["warnings"].append("release_after_observation_masked")
        if not original["release_date"]:
            entry["warnings"].append("missing_release_date")
        row["target_tier"] = None
        if platform == "pc":
            genres = row["genres"]
            if genres and set(genres) <= set(cleaning["software_only_genres"]):
                entry["exclusions"].append("software_only_heuristic")
            if genres and not gameplay(genres):
                entry["warnings"].append("no_recognized_gameplay_genre")
            lower, upper = row["owner_lower"], row["owner_upper"]
            if lower is None or upper == 0:
                row["owner_lower"] = row["owner_upper"] = None
                entry["warnings"].append("unknown_owners")
            elif upper <= 20000:
                row["target_tier"] = contracts.PC_TIERS[0]
            elif lower >= 100000:
                row["target_tier"] = contracts.PC_TIERS[2]
            elif lower >= 20000 and upper <= 100000:
                row["target_tier"] = contracts.PC_TIERS[1]
            else:
                entry["warnings"].append("owner_interval_straddles_tiers")
            if not any((genres, row["price_observed"] is not None, row["owner_lower"] is not None, row["release_date"] is not None)):
                entry["exclusions"].append("no_usable_analysis_fields")
        else:
            if row["category"] not in contracts.GAME_CATEGORIES:
                row["category"] = None
                entry["warnings"].append("unknown_game_category_masked")
            if row["price"] is not None and ((row["free"] is True and row["price"] > 0) or (row["free"] is False and row["price"] == 0)):
                row["free"] = None
                entry["warnings"].append("free_price_conflict_masked")
            if row["currency"] != "USD" or row["price"] is None:
                entry["warnings"].append("usd_price_unavailable")
            installs = row["minimum_installs"]
            if installs is not None:
                row["target_tier"] = contracts.MOBILE_TIERS[0 if installs < 1000 else 1 if installs < 100000 else 2]
            if not any((row["category"], installs is not None, row["price"] is not None and row["currency"] == "USD",
                        row["release_date"] is not None, any(row[k] is not None for k in ("free", "ad_supported", "in_app_purchases")))):
                entry["exclusions"].append("no_usable_analysis_fields")
        entry["included"] = not entry["exclusions"]
        excluded_counts.update(entry["exclusions"])
        if entry["included"]:
            exploration.append(row)
    for entry in ledger:
        warnings.update(entry["warnings"])
    exploration_warnings = Counter(warning for entry in ledger if entry["included"] for warning in entry["warnings"])
    summary = {
        "contract_version": VERSION, "rule_sha256": rule_fingerprint(), "metadata": meta,
        "input_sha256": raw_hash, "input_bytes": len(raw),
        "normalized_sha256": hashlib.sha256(normalized_csv).hexdigest(),
        "mapping": mapping, "options": options, "unmapped_columns": [name for name in header if name not in mapping.values()],
        "total_rows": total, "eligible_rows": comparison.num_rows, "exploration_rows": len(exploration),
        "excluded_rows": sum(not x["included"] and not x["invalid"] for x in ledger),
        "invalid_rows": sum(x["invalid"] for x in ledger),
        "error_count": sum(errors.values()), "errors_by_field": dict(errors), "issues": issues,
        "issues_truncated": sum(errors.values()) > len(issues), "warnings": dict(warnings),
        "exploration_warnings": dict(exploration_warnings),
        "exclusions": dict(excluded_counts), "comparison_exclusions": strict["exclusions"], "tiers": strict["tiers"],
        "can_import": not errors and bool(exploration), "sample": exploration[:5],
        "analysis_readiness": _readiness(exploration, platform, comparison.num_rows),
        "readiness_basis": "Field coverage before chart-specific minimum sample and variation checks; not a claim of statistical adequacy.",
        "scope": "Confirmed game snapshot mapping; exploration and comparison eligibility are separate. No research changes, model training or longitudinal sales inference.",
        "identity_basis": "source_id" if options["id_policy"] == "source" else "local_row_id_not_platform_identity",
    }
    return {"summary": summary, "comparison": comparison,
            "exploration": pa.Table.from_pylist(exploration, schema=EXPLORATION_SCHEMAS[platform]),
            "ledger": pa.Table.from_pylist(ledger, schema=LEDGER_SCHEMA), "normalized_csv": normalized_csv}
