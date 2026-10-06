"""Shared audit paths and explicit, reviewable name mappings."""
import csv
import hashlib
import json
import re
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
DATA = WORKSPACE / "Dataset"
DATE = "2026-10-05"
REPORTS = ROOT / "reports" / DATE
INTERIM = ROOT / "data/interim"
META = ROOT / "data/raw/source_metadata" / DATE
ALIASES = {
    "appid": "app_id", "appID": "app_id", "AppID": "app_id",
    "average_playtime_two_weeks": "average_playtime_2weeks",
    "median_playtime_two_weeks": "median_playtime_2weeks",
}
# 'Sports' is both an app category and a game category. This CSV has no genreId/type.
# Exclude it from the conservative game subset; retain it separately for sensitivity analysis.
GAME_CATEGORIES = ["Action", "Adventure", "Arcade", "Board", "Card", "Casino", "Casual", "Educational", "Music", "Puzzle", "Racing", "Role Playing", "Simulation", "Strategy", "Trivia", "Word"]
FOLDERS = {
    "Steam Games Dataset": "fronkongames/steam-games-dataset",
    "Steam Games Dataset 2025": "artermiloff/steam-games-dataset",
    "Google Play Store Apps": "gauthamp10/google-playstore-apps",
    "Steam Store Games (Clean dataset)": "nikdavis/steam-store-games",
    "Game Recommendations on Steam": "antonkozyriev/game-recommendations-on-steam",
}

def canonical(name):
    if name in ALIASES:
        return ALIASES[name]
    out = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return ALIASES.get(out, out)

def q(name):
    return '"' + name.replace('"', '""') + '"'

def lit(value):
    return "'" + str(value).replace("'", "''") + "'"

def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def connection():
    INTERIM.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    conn.execute("SET memory_limit='4GB'")
    conn.execute("SET threads=2")
    conn.execute("SET preserve_insertion_order=false")
    conn.execute("SET temp_directory=" + lit(INTERIM / "duckdb_temp"))
    return conn

def csv_header(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))

def csv_source(path, repaired=False):
    header = csv_header(path)
    if repaired:
        if header.count("DiscountDLC count") != 1:
            raise ValueError("Unexpected malformed header; do not infer a repair")
        i = header.index("DiscountDLC count")
        header[i:i+1] = ["Discount", "DLC count"]
    # Explicit positional names avoid DuckDB or pandas inferring an index from a malformed header.
    names = "[" + ",".join(lit(x) for x in header) + "]"
    return f"read_csv({lit(path)}, delim=',', quote='\"', escape='\"', header=false, skip=1, names={names}, all_varchar=true, nullstr='', strict_mode=true, ignore_errors=false, max_line_size=20000000)", header

def normalize_view(conn, name, source, header):
    if len({canonical(x) for x in header}) != len(header):
        raise ValueError("Canonical column name collision")
    conn.execute(f"CREATE OR REPLACE VIEW {q(name)} AS SELECT " + ",".join(f"{q(x)} AS {q(canonical(x))}" for x in header) + " FROM " + source)

def sources():
    result = []
    for p in sorted(DATA.rglob("*.csv")):
        folder = p.parent.name
        key = {
            "Steam Games Dataset": "fronkon_local",
            "Steam Games Dataset 2025": "artem_" + p.stem,
            "Google Play Store Apps": "google_all",
            "Steam Store Games (Clean dataset)": "nik_" + p.stem,
            "Game Recommendations on Steam": "rec_" + p.stem,
        }[folder]
        result.append({"key":key, "path":p, "repo":FOLDERS[folder], "repaired":key=="fronkon_local"})
    lock = json.loads((META / "sources_lock.json").read_text())
    hf = lock["hf"]["FronkonGames/steam-games-dataset"]
    result.append({"key":"fronkon_hf", "path":ROOT / hf["download"]["path"], "repo":"FronkonGames/steam-games-dataset", "revision":hf["revision"]})
    result.append({"key":"fronkon_json", "path":INTERIM / "fronkon_local_json.parquet", "repo":"fronkongames/steam-games-dataset", "original_path":DATA / "Steam Games Dataset/games.json"})
    return result
