"""Validate every CSV record width, hash original files, and verify header interpretation against JSON."""
import csv
from collections import Counter
from decimal import Decimal
import itertools
import json
import zipfile
import ijson
import pyarrow as pa
import pyarrow.parquet as pq
from audit_common import DATA, INTERIM, META, REPORTS, canonical, save_json, sha256

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--skip-inventory',action='store_true');args=parser.parse_args()
    csv.field_size_limit(20_000_000)
    REPORTS.mkdir(parents=True, exist_ok=True)
    INTERIM.mkdir(parents=True, exist_ok=True)
    facts = {}
    for p in sorted(DATA.rglob("*")):
        if args.skip_inventory:
            break
        if not p.is_file() or p.suffix.lower() not in {".csv", ".json", ".zip"}:
            continue
        entry = {"path":str(p.relative_to(DATA)), "bytes":p.stat().st_size, "sha256":sha256(p)}
        if p.suffix == ".csv":
            with p.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, strict=True)
                header = next(reader)
                widths = Counter(len(row) for row in reader)
            entry.update({"header_columns":len(header), "row_widths":dict(widths), "rows":sum(widths.values()), "header":header, "encoding":"utf-8-sig strict decode; original BOM not asserted"})
        elif p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                entry["members"] = [{"name":x.filename,"bytes":x.file_size,"crc32":x.CRC,"zip_timestamp":x.date_time} for x in z.infolist()]
        facts[entry["path"]] = entry
        print(entry["path"],entry.get("rows"), entry.get("row_widths"), flush=True)
    if not args.skip_inventory:
        save_json(REPORTS / "structure_and_hashes.json", facts)

    csv_path = DATA / "Steam Games Dataset/games.csv"
    json_path = DATA / "Steam Games Dataset/games.json"
    checks = Counter()
    field_names = set()
    field_presence = Counter()
    ids = set()
    mismatch_counts = Counter()
    scalar_map = None
    buffer = []
    writer = None
    json_schema = None
    with csv_path.open(encoding="utf-8-sig", newline="") as cf, json_path.open("rb") as jf:
        reader = csv.reader(cf, strict=True)
        original = next(reader)
        fixed = original.copy()
        idx = fixed.index("DiscountDLC count")
        fixed[idx:idx+1] = ["Discount", "DLC count"]
        columns = [canonical(x) for x in fixed]
        csv_rows={}
        for row in reader:
            if len(row)!=len(columns):raise ValueError('Unexpected CSV width')
            if row[0] in csv_rows:raise ValueError('Duplicate CSV ID')
            csv_rows[row[0]]=row
        checks['csv_records']=len(csv_rows)
        for app_id, record in ijson.kvitems(jf, "", use_float=True):
            csv_row=csv_rows.get(app_id)
            checks["json_records"] += 1
            field_names.update(record)
            field_presence.update(record.keys())
            if app_id in ids:
                checks["duplicate_json_keys"] += 1
            ids.add(app_id)
            values = dict(zip(columns,csv_row)) if csv_row else None
            checks['shared_records' if csv_row else 'json_only_records']+=1
            if scalar_map is None:
                scalar_map = [k for k in columns if k in record and isinstance(record[k],(int,float,bool))]
                scalar_map += ["estimated_owners", "release_date", "score_rank"]
            for col in scalar_map:
                if values is None:continue
                a,b=values[col],record.get(col)
                if isinstance(b,bool): equal=a.lower()==str(b).lower()
                elif isinstance(b,(int,float)):
                    try: equal=Decimal(a)==Decimal(str(b))
                    except Exception: equal=False
                else: equal=a==str(b or "")
                if not equal:mismatch_counts[col]+=1
                checks["scalar_comparisons"]+=1
            # Retain JSON values as JSON text for nested fields, never silently flatten them.
            if json_schema is None:
                json_schema = pa.schema([pa.field("app_id",pa.string())]+[pa.field(k,pa.string()) for k in sorted(record)])
                writer=pq.ParquetWriter(INTERIM / "fronkon_local_json.parquet",json_schema,compression="zstd")
            converted={"app_id":app_id}
            converted.update({k:json.dumps(v,ensure_ascii=False,separators=(",",":")) if isinstance(v,(list,dict)) else str(v) if v is not None else None for k,v in record.items()})
            buffer.append(converted)
            if len(buffer)>=5000:
                writer.write_table(pa.Table.from_pylist(buffer,schema=json_schema));buffer=[]
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=json_schema))
        if writer:writer.close()
        checks['csv_only_records']=len(set(csv_rows)-ids)
    evidence={"checks":dict(checks),"compared_scalar_fields":scalar_map,"mismatches_by_field":dict(mismatch_counts),"json_fields":sorted(field_names),"json_field_presence":dict(field_presence),"proposed_header":fixed,"original_header":original,"source_evidence":"ConvertToCSV_source.txt positions Discount then DLC count; local JSON cross-check", "header_interpretation_verified":not mismatch_counts and not checks["duplicate_json_keys"]}
    save_json(REPORTS / "header_validation.json",evidence)
    print("HEADER_VALIDATION",evidence["checks"],evidence["mismatches_by_field"],flush=True)
    # JSON-lines supplementary metadata, without retaining user-level data in reports.
    p=DATA / "Game Recommendations on Steam/games_metadata.json"
    rows=0;keys=set();identifiers=set();dups=0
    with p.open(encoding="utf-8") as f:
        for line in f:
            row=json.loads(line);rows+=1;keys.update(row)
            ident=row.get("app_id")
            dups+=ident in identifiers;identifiers.add(ident)
    save_json(REPORTS / "json_metadata_structure.json",{"rows":rows,"fields":sorted(keys),"duplicate_app_ids":dups})

if __name__ == "__main__":
    main()
