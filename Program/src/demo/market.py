"""Independent descriptive charts from verified, versioned historical snapshots.

Research rows are restricted to the already materialised training membership.
Imported source files supply descriptive values omitted by the narrow comparison
contract; they never change that contract, the research split or model features.
"""
import copy
import hashlib
import json
import math
from datetime import datetime, timezone

import duckdb
import pandas as pd

from imports.repository import DEFAULT_VERSION
from market_taxonomy import gameplay, other_labels, tag_groups, metadata as taxonomy_metadata
from market_analytics import analytical_charts


MANIFEST = "reports/2026-10-06/analysis_v1/manifest.json"
EXPECTED_MANIFEST = "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6"
COLORS = ["#176b54", "#64a992", "#d19035"]
MAX_SAFE_CHART_NUMBER = 2 ** 53 - 1
SOURCE_URLS = {
    "pc": "https://www.kaggle.com/datasets/artermiloff/steam-games-dataset",
    "mobile": "https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps",
}
TIERS = {
    "pc": [("O1_source_interval_up_to_20k", "來源區間上限 ≤ 20,000"),
           ("O2_source_intervals_20k_to_100k", "來源區間 20,000–100,000"),
           ("O3_source_intervals_100k_plus", "來源區間下限 ≥ 100,000")],
    "mobile": [("M1_under_1k", "安裝量下限 < 1,000"),
               ("M2_1k_to_under_100k", "安裝量下限 1,000–<100,000"),
               ("M3_100k_plus", "安裝量下限 ≥ 100,000")],
}
SOURCES = {"pc": "Steam 歷史樣本", "mobile": "Android 歷史樣本", "revenue": "Steam 2024 營收樣本"}


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _number(value):
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite chart value")
    if abs(number) > MAX_SAFE_CHART_NUMBER:
        raise ValueError("Chart value exceeds the browser's safe numeric range (9,007,199,254,740,991); narrow the selection or review the imported values.")
    return int(number) if number.is_integer() else round(number, 6)


def _text_date(value):
    return None if pd.isna(value) else value.strftime("%Y-%m-%d")


def _sum(series):
    # All missing is unavailable, never a fabricated zero. Float arithmetic also
    # avoids overflowing int64 when a permitted imported cohort is very large.
    return _number(series.astype(float).sum(min_count=1))


def _median(series):
    return _number(series.median()) if series.notna().any() else None


def _list(value):
    return list(value) if value is not None else []


class MarketStore:
    def __init__(self, comparison_store, revenue_store=None):
        self.comparison = comparison_store
        self.revenue = revenue_store
        self.root = comparison_store.root
        self.cache = {}

    def _unavailable(self, source, message):
        return {"id": source, "name": SOURCES[source], "snapshot": "", "version_id": "",
                "available": False, "groups": [], "tag_groups": [], "year_min": None, "year_max": None,
                "rank_metrics": [{"id": "volume", "label": "數量"}],
                "description": "此資料來源暫時未能通過本機資料檢查。",
                "limitations": [message]}

    def options(self):
        sources = []
        with self.comparison.lock:
            for source in SOURCES:
                try:
                    data = self._load(source)
                    sources.append(copy.deepcopy(data["source"]))
                except (OSError, ValueError, KeyError, TypeError, duckdb.Error) as exc:
                    sources.append(self._unavailable(source, str(exc)))
        return {"sources": sources}

    def _load(self, source):
        version = (self.revenue.data["metadata"]["version"] if self.revenue is not None else "unavailable") if source == "revenue" else self.comparison.active[source]
        key = (source, version)
        if key not in self.cache:
            data = self._load_revenue() if source == "revenue" else self._load_platform(source, version)
            # Keep at most one active snapshot per source; imported versions can
            # be large and need not remain resident after activation changes.
            self.cache = {k: v for k, v in self.cache.items() if k[0] != source}
            self.cache[key] = data
        return self.cache[key]

    def _load_platform(self, source, version):
        spec = copy.deepcopy(self.comparison.options[source])
        db = self.comparison.db
        hashes = {}
        if version == DEFAULT_VERSION:
            path = self.root / MANIFEST
            if _sha(path) != EXPECTED_MANIFEST:
                raise ValueError("Frozen analysis manifest changed; market charts are unavailable.")
            manifest = json.loads(path.read_text(encoding="utf-8"))
            rel = f"data/interim/cleaning_candidate_v1/{source}_candidates.parquet"
            fingerprint = _sha(self.root / rel)
            if fingerprint != manifest["inputs"][rel]:
                raise ValueError("Descriptive source checksum changed; review the candidate data.")
            hashes[MANIFEST] = EXPECTED_MANIFEST
            hashes[rel] = fingerprint
            for kind in ("features", "labels_splits"):
                name = f"data/processed/analysis_v1/{source}_{kind}.parquet"
                hashes[name] = manifest["outputs"][name]
            dimensions = "a.genres, a.price_observed AS price" if source == "pc" else "a.category, a.free, a.ad_supported, a.in_app_purchases, a.price_usd AS price"
            volumes = "c.owners_lower AS volume_lower, c.owners_upper AS volume_upper" if source == "pc" else "c.minimum_installs AS volume_lower, c.minimum_installs AS volume_upper"
            frame = db.execute(f"""SELECT a.app_id, a.target_tier, {dimensions},
                c.title, c.release_date, c.reference_date AS observed_date, {volumes},
                c.app_id IS NOT NULL AS detail_available
                FROM {source} a LEFT JOIN read_parquet(?) c USING(app_id)""", [str(self.root / rel)]).fetchdf()
            if _sha(self.root / rel) != fingerprint:
                raise ValueError("Descriptive source changed while loading.")
            currency = "unknown" if source == "pc" else "USD"
            scope = "Frozen research training membership only; calibration and test rows are excluded."
            urls = [SOURCE_URLS[source]]
            observation_basis = "configured_snapshot_date_proxy" if source == "pc" else "per_row_scraped_date"
            observation_fallback_rows = int(frame.detail_available.sum()) if source == "pc" else 0
        else:
            manifest, parquet = self.comparison.repository.load(source, version)
            raw = pd.read_csv(parquet.parent / "source.csv", dtype=str, keep_default_na=False)
            active = db.execute(f"SELECT * FROM {source}").fetchdf()
            numeric = ["owner_lower", "owner_upper", "price_observed"] if source == "pc" else ["minimum_installs", "price", "currency"]
            details = raw[["app_id", "release_date", "observed_date"] + numeric]
            frame = active.merge(details, on="app_id", how="left", validate="one_to_one", indicator=True)
            if not frame["_merge"].eq("both").all():
                raise ValueError("Imported descriptive source does not cover the eligible snapshot.")
            frame["detail_available"] = True
            observation_fallback_rows = int(frame["observed_date"].eq("").sum())
            frame["observed_date"] = frame["observed_date"].replace("", manifest["metadata"]["snapshot_date"])
            lower = "owner_lower" if source == "pc" else "minimum_installs"
            upper = "owner_upper" if source == "pc" else "minimum_installs"
            frame["volume_lower"] = pd.to_numeric(frame[lower], errors="raise")
            frame["volume_upper"] = pd.to_numeric(frame[upper], errors="raise")
            price = "price_observed" if source == "pc" else "price"
            frame["price"] = pd.to_numeric(frame[price].replace("", None), errors="raise")
            currency = manifest["metadata"]["price_currency"] if source == "pc" else "USD"
            if source == "mobile":
                frame.loc[frame["currency"].ne("USD"), "price"] = float("nan")
            hashes = {f"application/{version}/{name}": value for name, value in manifest["files"].items()}
            scope = "Eligible rows of the active imported application snapshot; not research training or test data."
            urls = [manifest["metadata"]["source_url"]] if manifest["metadata"]["source_url"] else []
            observation_basis = "declared_per_row_date_with_snapshot_fallback"
        if len(frame) != spec["row_count"] or frame.app_id.duplicated().any():
            raise ValueError("Market membership is inconsistent with the active comparison snapshot.")
        frame["app_id"] = frame.app_id.astype(str)
        frame["title"] = frame.title.where(frame.title.notna(), frame.app_id.map(lambda x: f"ID {x}（名稱未載入）"))
        frame["release_date"] = pd.to_datetime(frame.release_date, errors="raise")
        frame["observed_date"] = pd.to_datetime(frame.observed_date, errors="raise")
        frame["volume_lower"] = pd.to_numeric(frame.volume_lower).astype(float)
        frame["volume_upper"] = pd.to_numeric(frame.volume_upper).astype(float)
        frame["price"] = pd.to_numeric(frame.price).astype(float)
        frame["groups"] = frame.genres.map(_list) if source == "pc" else frame.category.map(lambda x: [str(x)])
        if source == "mobile":
            for name in ("free", "ad_supported", "in_app_purchases"):
                frame[name] = frame[name].map(lambda x: None if pd.isna(x) else bool(x))
        unit = "估計擁有者區間" if source == "pc" else "安裝量下限"
        limits = [
            "歷史快照中的樣本，並非目前完整遊戲市場；不跨平台合併排名。",
            "時間軸按遊戲發售日期分組，並非當年新增銷售、下載量或同一遊戲的時間序列。較早發售遊戲有較長累積時間。",
            "樣本數、數量總和及每款遊戲中位數回答不同問題；不能據此推論因果、預測銷量或收益。",
        ]
        if source == "pc":
            limits += ["Owners 是來源估計區間，並非精確購買量、售出份數或獨立玩家人數。依下限排序不代表區間重疊的遊戲有確定先後。",
                       "Steam 樣本僅包含研究／匯入規則保留的正價遊戲；多類型遊戲會出現在多組，組別總和不能相加為市場總量。",
                       "玩法類型依本項目的明示對照表展示；Indie、Early Access、內容及軟件標籤另設篩選，原始標籤與研究納入規則不變。"]
            if currency == "unknown":
                limits.append("Steam 價格幣別未獲來源確認，價格分組只使用來源數值，不標示為美元或與其他幣別合併。")
            if version == DEFAULT_VERSION:
                limits.append("Steam 的 2025-03-13 觀測日期是清理規則使用的快照代理日期，並非逐遊戲已確認的實際擷取時間。")
        else:
            limits += ["安裝量是來源累積安裝下限，不是精確下載次數、銷售量或獨立使用者數。",
                       "Android 僅涵蓋既定 16 個遊戲類別；免費／收費、廣告及內購為觀測時標記，未知值另列。"]
        missing = int((~frame.detail_available).sum())
        if missing:
            limits.append(f"{missing} 款保留樣本未有已核實的名稱／日期／數量詳細資料；保留於類型及分層計數，數量與日期圖只使用已知值。")
        if spec.get("data_kind") == "synthetic":
            limits.insert(0, "此版本為人工示範資料，不能解讀為真實市場證據。")
        if version != DEFAULT_VERSION and observation_fallback_rows:
            limits.append(f"{observation_fallback_rows:,} 筆未填觀測日期的匯入記錄使用所提供的快照日期作代理；這不是額外查證的擷取時間。")
        provenance = {"source_id": source, "version_id": version, "partition": spec["partition"],
                      "scope": scope, "input_hashes": hashes, "detail_rows": len(frame)-missing,
                      "missing_detail_rows": missing, "release_date_rows": int(frame.release_date.notna().sum()),
                      "observation_date_min": _text_date(frame.observed_date.min()),
                      "observation_date_max": _text_date(frame.observed_date.max()),
                      "observation_date_basis": observation_basis,
                      "observation_date_proxy_rows": observation_fallback_rows,
                      "source_urls": urls, "temporal_basis": "release_cohort_not_longitudinal",
                      "data_kind": spec.get("data_kind", "historical"), "price_currency": currency}
        return self._package(source, version, spec["snapshot"], frame, unit, limits, provenance,
                             "既定納入規則下的歷史樣本；所有圖表均隨篩選條件更新。")

    def _load_revenue(self):
        if self.revenue is None:
            raise ValueError("The independently verified Steam revenue artifact is unavailable.")
        meta = copy.deepcopy(self.revenue.data["metadata"])
        frame = pd.DataFrame(copy.deepcopy(self.revenue.data["rows"]))
        frame["app_id"] = frame.steam_id.astype(str)
        frame["title"] = frame["name"]
        frame["groups"] = frame.genres.map(_list)
        frame["release_date"] = pd.to_datetime(frame.release_date, errors="raise")
        frame["volume_lower"] = frame.copies_sold.astype(float)
        frame["volume_upper"] = frame.copies_sold.astype(float)
        frame["detail_available"] = True
        for column in ("price", "revenue", "volume_lower"):
            if not frame[column].map(lambda x: math.isfinite(float(x)) and x >= 0).all():
                raise ValueError("Invalid independently prepared revenue values")
        limits = [
            f"此頁預設使用全部 {len(frame):,} 筆來源記錄，包括 {int(frame.price.eq(0).sum())} 筆觀測價格為零的遊戲；與營收詳情頁的正價預設不同。篩選後數量會減少。",
            "樣本按高營收選入，不能代表全部 Steam 遊戲，亦不能估計一般遊戲的成功機率。",
            "售出份數與累積總營收是來源估計，不是已核實收入、利潤或淨回款；零觀測價格不等於已確認發售時免費。",
            "發售月份比較的是不同遊戲在來源快照中的累積估計，並非該月實際新增銷售或營收，亦非時間序列。",
            "類型取自較後的 2025 年 3 月資料；多類型組別互相重疊，不能相加為市場總量。",
        ] + meta.get("limitations", [])
        provenance = {"source_id": "revenue", "version_id": meta["version"], "partition": "independent_revenue_cohort",
                      "scope": meta["scope"], "input_hashes": {"revenue_source": meta["source_sha256"], "genre_metadata": meta["metadata_sha256"]},
                      "detail_rows": len(frame), "missing_detail_rows": 0,
                      "release_date_rows": int(frame.release_date.notna().sum()),
                      "observation_date_min": None, "observation_date_max": None,
                      "source_urls": [meta["source_url"]], "temporal_basis": "release_cohort_not_longitudinal",
                      "data_kind": "historical", "price_currency": meta.get("currency", "USD"),
                      "source_metadata": meta}
        return self._package("revenue", meta["version"], meta["source_snapshot"], frame, "估計售出份數", limits,
                             provenance, "獨立的 2024 高營收 Steam 發售樣本；含零觀測價格記錄，並非全市場。")

    def _package(self, source, version, snapshot, frame, unit, limits, provenance, description):
        frame['source_labels'] = frame.groups.map(list)
        if source != 'mobile':
            frame['groups'] = frame.source_labels.map(gameplay)
            frame['source_tags'] = frame.source_labels.map(other_labels)
            tags = tag_groups([v for labels in frame.source_labels for v in labels])
            limits.append('附加標籤只表示來源有列出該標記；沒有標記不等於沒有該特徵。內容／發行標籤的完整性及跨年份一致性未獲核實。')
        else:
            frame['source_tags'] = [[] for _ in range(len(frame))]
            tags = []
        provenance['label_taxonomy'] = taxonomy_metadata()
        provenance['rows_without_gameplay_group'] = int(frame.groups.map(len).eq(0).sum())
        groups = sorted({value for values in frame.groups for value in values})
        years = frame.release_date.dt.year.dropna()
        metrics = [{"id": "volume", "label": unit}]
        if source == "revenue":
            metrics.append({"id": "revenue", "label": "估計累積總營收（USD）"})
        source_obj = {"id": source, "name": SOURCES[source], "snapshot": snapshot, "version_id": version,
                      "available": True, "groups": groups, "tag_groups": tags,
                      "group_label": 'Google Play 遊戲類別' if source == 'mobile' else '玩法類型',
                      "year_min": int(years.min()) if len(years) else None,
                      "year_max": int(years.max()) if len(years) else None, "rank_metrics": metrics,
                      "description": description, "limitations": limits}
        source_obj['data_kind'] = provenance.get('data_kind', 'historical')
        if source_obj['data_kind'] == 'synthetic':
            source_obj['name'] += '（人工示例）'
            source_obj['description'] = '此版本為人工示範資料，不代表真實市場。' + description
        return {"source": source_obj, "frame": frame, "provenance": provenance, "unit": unit}

    def query(self, payload):
        expected = {"source", "version_id", "group", "year_from", "year_to", "top_n", "rank_metric"}
        if not isinstance(payload, dict) or set(payload) not in (expected, expected | {'tag'}):
            raise ValueError("Expected source, version_id, group, year_from, year_to, top_n and rank_metric.")
        payload = {'tag': '', **payload}
        source = payload["source"]
        if not isinstance(source, str) or source not in SOURCES:
            raise ValueError("Unknown market source.")
        for field in ("version_id", "group", "tag", "rank_metric"):
            if not isinstance(payload[field], str):
                raise ValueError("Market selector values must be strings.")
        if type(payload["top_n"]) is not int or payload["top_n"] not in (10, 20):
            raise ValueError("top_n must be 10 or 20.")
        for name in ("year_from", "year_to"):
            if payload[name] is not None and (type(payload[name]) is not int or not 1 <= payload[name] <= 9999):
                raise ValueError("Years must be integer years or null.")
        if payload["year_from"] is not None and payload["year_to"] is not None and payload["year_from"] > payload["year_to"]:
            raise ValueError("The start year must not exceed the end year.")
        with self.comparison.lock:
            data = self._load(source)
            if payload["version_id"] != data["source"]["version_id"]:
                raise ValueError("The active source version changed; refresh the market page.")
            if payload["group"] and payload["group"] not in data["source"]["groups"]:
                raise ValueError("Unknown genre or category for this source.")
            if payload['tag'] and payload['tag'] not in {v for g in data['source']['tag_groups'] for v in g['values']}:
                raise ValueError('Unknown additional source label; gameplay genres and other labels have separate filters.')
            if payload["rank_metric"] not in {item["id"] for item in data["source"]["rank_metrics"]}:
                raise ValueError("Unsupported ranking metric for this source.")
            frame = data["frame"]
            if payload["group"]:
                frame = frame[frame.groups.map(lambda xs: payload["group"] in xs)]
            if payload['tag']:
                frame = frame[frame.source_tags.map(lambda xs: payload['tag'] in xs)]
            years = frame.release_date.dt.year
            if payload["year_from"] is not None:
                frame = frame[years >= payload["year_from"]]
                years = frame.release_date.dt.year
            if payload["year_to"] is not None:
                frame = frame[years <= payload["year_to"]]
            return self._analyze(data, frame, payload)

    def _analyze(self, data, frame, filters):
        source = data["source"]["id"]
        pc = source == "pc"
        revenue = source == "revenue"
        unit = data["unit"]
        top = filters["top_n"]
        caption = (f"{data['source']['name']} · 快照 {data['source']['snapshot']} · {data['source']['version_id']} · "
                   f"{data['source']['group_label']} {filters['group'] or '全部'} · 附加標籤 {filters['tag'] or '不限'} · 發售年 {filters['year_from'] or '不限'}–{filters['year_to'] or '不限'} · n={len(frame):,}")
        charts = []

        def chart(ident, title, description, rows, series, chart_unit, kind="bar", y_label=None):
            charts.append({"id": ident, "title": title, "description": description, "type": kind,
                           "rows": [{"label": str(label), "values": [_number(v) for v in values]} for label, values in rows],
                           "series": [{"key": key, "label": label, "color": COLORS[i % len(COLORS)]} for i, (key, label) in enumerate(series)],
                           "unit": chart_unit, "yLabel": y_label or chart_unit, "source": caption})

        volume_series = [("lower", "估計下限"), ("upper", "估計上限")] if pc else [("value", unit)]

        def volumes(group, median=False):
            function = _median if median else _sum
            low = function(group.volume_lower)
            return [low, function(group.volume_upper)] if pc else [low]

        expanded = frame.explode("groups")
        grouped = [(str(label), subset) for label, subset in expanded.groupby("groups", sort=True)]
        group_counts = sorted([(label, [len(subset)]) for label, subset in grouped], key=lambda r: (-r[1][0], r[0]))[:top]
        group_word = data['source']['group_label']
        count_description = ('每款遊戲使用一個來源類別。' if source == 'mobile' else '同一遊戲可歸入多個玩法類型。')
        chart("group_count", f"{group_word}的遊戲數量", "已篩選樣本的遊戲數；" + count_description + "點選長條可篩選該組。", group_counts, [("count", "遊戲數")], "款")
        for row in charts[-1]['rows']:
            row['filter'] = {'group': row['label']}
        totals = [(label, volumes(subset)) for label, subset in grouped]
        totals.sort(key=lambda r: (r[1][0] is None, -(r[1][0] or 0), r[0]))
        chart("group_volume_total", f"{group_word}的{unit}總和", "依下限或來源估計總和排序；總和受組別遊戲數影響，並非獨立使用者或市場份額。", totals[:top], volume_series, unit)
        medians = [(f"{label} (n={int(subset.volume_lower.notna().sum())})", volumes(subset, True)) for label, subset in grouped]
        medians.sort(key=lambda r: (r[1][0] is None, -(r[1][0] or 0), r[0]))
        chart("group_volume_median", f"每款遊戲的{unit}中位數", "n 是數量資料可用的遊戲數；中位數不等於下一款遊戲的預期表現。", medians[:top], volume_series, unit)
        if revenue:
            for metric, title, function in [("total", "類型估計累積總營收", _sum), ("median", "類型每款遊戲營收中位數", _median)]:
                rows = [(f"{label} (n={len(subset)})", [function(subset.revenue)]) for label, subset in grouped]
                rows.sort(key=lambda r: (r[1][0] is None, -(r[1][0] or 0), r[0]))
                chart(f"group_revenue_{metric}", title, "來源估計總營收，並非利潤；多類型組別互相重疊。", rows[:top], [("revenue", "估計總營收")], "USD")
        else:
            upper = TIERS[source][-1][0]
            rows = [(f"{label} (n={len(subset)})", [100 * subset.target_tier.eq(upper).mean()]) for label, subset in grouped if len(subset) >= 30]
            rows.sort(key=lambda r: (-r[1][0], r[0]))
            chart("group_high_tier_share", "較高數量分層的組內比例", "只列 n ≥ 30 的組別；分母是該組全部樣本。30 為顯示門檻，並非統計充分性的保證。", rows[:top], [("percent", "較高分層比例")], "%")
            chart("outcome_tiers", "來源數量分層分布", "沿用既定 owners／安裝下限分層，保留完整已篩選樣本。", [(label, [int(frame.target_tier.eq(key).sum())]) for key, label in TIERS[source]], [("count", "遊戲數")], "款")
        date_rows = frame[frame.release_date.notna()].copy()
        if revenue:
            date_rows["cohort"] = date_rows.release_date.dt.strftime("%Y-%m")
            timeline = [str(value) for value in pd.period_range(date_rows.release_date.min(), date_rows.release_date.max(), freq="M")] if len(date_rows) else []
        else:
            date_rows["cohort"] = date_rows.release_date.dt.year.astype(int)
            timeline = list(range(int(date_rows.cohort.min()), int(date_rows.cohort.max()) + 1)) if len(date_rows) else []
        cohorts = {label: subset for label, subset in date_rows.groupby("cohort")}
        count_rows, volume_rows = [], []
        for label in timeline:
            subset = cohorts.get(label)
            count_rows.append((label, [len(subset) if subset is not None else 0]))
            volume_rows.append((label, volumes(subset, True) if subset is not None else [None] * len(volume_series)))
        date_word = "發售月份" if revenue else "發售年份"
        chart("release_count", f"按{date_word}分組的遊戲數", f"時間軸是{date_word}，不是下載或銷售發生時間。僅計入發售日期已知的 {len(date_rows):,} 款遊戲；當期年份／月份可能未完整。", count_rows, [("count", "遊戲數")], "款", "line")
        chart("release_volume_median", f"按{date_word}比較累積數量中位數", "每個點代表不同發售批次在資料快照中的累積表現；不是同一遊戲的成長線。空批次沒有中位數，不以零補值。", volume_rows, volume_series, unit, "line")
        if revenue or pc:
            price_groups = [
                ("價格為 0", frame[frame.price.eq(0)]),
                ("0 < 價格 < 10", frame[frame.price.gt(0) & frame.price.lt(10)]),
                ("10 ≤ 價格 < 20", frame[frame.price.ge(10) & frame.price.lt(20)]),
                ("20 ≤ 價格 < 30", frame[frame.price.ge(20) & frame.price.lt(30)]),
                ("價格 ≥ 30", frame[frame.price.ge(30)]),
                ("價格未知", frame[frame.price.isna()]),
            ]
            if revenue:
                chart("price_revenue_median", "觀測價格分組與營收中位數", "幣別依來源約定為 USD；觀測價格不是發售定價。組別差異不代表提高價格會增加營收。", [(f"{label} (n={len(subset)})", [_median(subset.revenue)]) for label, subset in price_groups], [("revenue", "估計營收中位數")], "USD")
            else:
                currency = data["provenance"]["price_currency"]
                currency_note = "來源幣別未確認" if currency == "unknown" else f"價格幣別 {currency}"
                chart("business_count", "觀測價格分布", f"{currency_note}；使用觀測時價格，不能視作發售定價。", [(label, [len(subset)]) for label, subset in price_groups], [("count", "遊戲數")], "款")
                chart("business_volume_median", "價格分組與 owners 中位區間", f"{currency_note}；價格與表現只是樣本關聯，並非因果或收入估計。", [(f"{label} (n={len(subset)})", volumes(subset, True)) for label, subset in price_groups], volume_series, unit)
        else:
            business = []
            for field, label, true_label, false_label in [("free", "下載收費", "免費", "收費"), ("ad_supported", "廣告", "有", "無"), ("in_app_purchases", "內購", "有", "無")]:
                for flag, word in [(True, true_label), (False, false_label), (None, "未知")]:
                    mask = frame[field].isna() if flag is None else frame[field].eq(flag)
                    business.append((f"{label}：{word}", frame[mask]))
            chart("business_count", "免費、廣告與內購的樣本數", "三個觀測屬性分開比較，同一遊戲可出現在三組；未知值不當作否。", [(label, [len(subset)]) for label, subset in business], [("count", "遊戲數")], "款")
            chart("business_volume_median", "營運模式與安裝下限中位數", "觀測屬性分組的描述性比較；不代表廣告或內購造成下載差異。", [(f"{label} (n={len(subset)})", volumes(subset, True)) for label, subset in business], volume_series, unit)
        if revenue:
            ranked_revenue = frame.sort_values(["revenue", "app_id"], ascending=[False, True])
            total = _sum(ranked_revenue.revenue)
            concentration = []
            if total and len(ranked_revenue):
                cumulative = ranked_revenue.revenue.cumsum().tolist()
                positions = sorted({0, len(ranked_revenue)} | {math.ceil(len(ranked_revenue) * i / 100) for i in range(1, 101)})
                concentration = [(str(rank), [0 if rank == 0 else 100 * cumulative[rank - 1] / total]) for rank in positions]
            chart("revenue_concentration", "營收集中程度", "橫軸為按估計營收排序後的遊戲名次，縱軸為累積營收百分比；此圖沒有時間軸。", concentration, [("percent", "累積營收比例")], "%", "line")
        metric = "revenue" if filters["rank_metric"] == "revenue" else "volume_lower"
        ranked = frame[frame[metric].notna()].sort_values([metric, "app_id"], ascending=[False, True]).head(top)
        top_series = [("revenue", "估計總營收")] if metric == "revenue" else volume_series
        rank_unit = "USD" if metric == "revenue" else unit
        chart("top_games", f"遊戲排名：{rank_unit}", "只列目前篩選樣本；同值按 ID 穩定排序。Owners 區間可能重疊，排名不等於確定的購買量先後。" if pc else "只列目前篩選樣本，使用來源估計或安裝下限；同值按 ID 穩定排序。", [(row.title, [row.revenue] if metric == "revenue" else ([row.volume_lower, row.volume_upper] if pc else [row.volume_lower])) for row in ranked.itertuples()], top_series, rank_unit)
        columns = [{"key": "rank", "label": "排名"}, {"key": "title", "label": "遊戲"}, {"key": "release_date", "label": "發售日期"}]
        if pc:
            columns += [{"key": "volume_lower", "label": "Owners 估計下限"}, {"key": "volume_upper", "label": "Owners 估計上限"}]
        elif revenue:
            columns += [{"key": "copies_sold", "label": "估計售出份數"}, {"key": "revenue", "label": "估計總營收 USD"}]
        else:
            columns += [{"key": "minimum_installs", "label": "安裝量下限"}]
        columns += [{"key": "groups", "label": group_word}]
        if source != 'mobile':
            columns += [{'key': 'source_tags', 'label': '其他來源標籤'}]
        leaders = []
        for rank, row in enumerate(ranked.itertuples(), 1):
            record = {"rank": rank, "title": row.title, "release_date": _text_date(row.release_date), "groups": " / ".join(row.groups), 'source_tags': ' / '.join(row.source_tags), "app_id": row.app_id}
            if pc:
                record.update(volume_lower=_number(row.volume_lower), volume_upper=_number(row.volume_upper))
            elif revenue:
                record.update(steam_id=row.app_id, copies_sold=_number(row.copies_sold), revenue=_number(row.revenue), price=_number(row.price))
            else:
                record["minimum_installs"] = _number(row.volume_lower)
            leaders.append(record)
        summary = [{"label": "篩選後遊戲數", "value": len(frame), "unit": "款"},
                   {"label": "數量資料可用", "value": int(frame.volume_lower.notna().sum()), "unit": "款"},
                   {"label": f"{unit}總和" if not pc else "Owners 估計下限總和", "value": _sum(frame.volume_lower), "unit": unit}]
        if pc:
            summary.append({"label": "Owners 估計上限總和", "value": _sum(frame.volume_upper), "unit": unit})
        elif revenue:
            summary.append({"label": "估計累積總營收", "value": _sum(frame.revenue), "unit": "USD"})
        else:
            summary.append({"label": "每款安裝下限中位數", "value": _median(frame.volume_lower), "unit": unit})
        provenance = copy.deepcopy(data["provenance"])
        provenance.update(filtered_rows=len(frame), filtered_detail_rows=int(frame.detail_available.sum()),
                          filtered_release_date_rows=len(date_rows))
        notes = list(data["source"]["limitations"])
        if 0 < len(frame) < 30:
            notes.insert(0, "目前篩選少於 30 款遊戲，結果對個別遊戲較敏感。")
        if frame.groups.map(len).eq(0).any():
            notes.append(f"{int(frame.groups.map(len).eq(0).sum())} 款樣本沒有已對照的玩法類型；仍計入總覽、日期及排名，原始標籤保留，不會強行歸入玩法組。")
        if len(frame) == 0:
            notes.insert(0, "目前篩選沒有符合遊戲；沒有樣本不代表市場不存在該類遊戲。")
        sections = {'group_count': 'overview', 'group_volume_total': 'overview',
                    'group_volume_median': 'distribution', 'outcome_tiers': 'distribution',
                    'group_high_tier_share': 'relationships', 'business_count': 'distribution',
                    'business_volume_median': 'relationships', 'group_revenue_total': 'overview',
                    'group_revenue_median': 'distribution', 'price_revenue_median': 'relationships',
                    'revenue_concentration': 'distribution', 'release_count': 'cohorts',
                    'release_volume_median': 'cohorts', 'top_games': 'rankings'}
        for item in charts:
            item['section'] = sections[item['id']]
            item['integerTicks'] = item['unit'] == '款'
        charts.extend(analytical_charts(frame, source, unit, data['provenance']['price_currency'], caption, top_n=top))
        return {"schema_version": "market_analysis_v2", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": copy.deepcopy(data["source"]), "filters": dict(filters), "summary": summary,
                "charts": charts, "leaders": {"title": f"遊戲排名：{rank_unit}", "columns": columns, "rows": leaders},
                "notes": notes, "provenance": provenance, "empty": len(frame) == 0}
