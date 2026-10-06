"""Full-file, bounded-memory profiles. No training, imputation, or row removal."""
import json
import math
from audit_common import *

NUMERIC = set("price discount dlc_count peak_ccu required_age metacritic_score user_score positive negative achievements recommendations average_playtime_forever average_playtime_2weeks median_playtime_forever median_playtime_2weeks rating rating_count minimum_installs maximum_installs positive_ratings negative_ratings average_playtime median_playtime positive_ratio user_reviews price_final price_original discount num_reviews_total num_reviews_recent pct_pos_total pct_pos_recent helpful funny hours products reviews".split())
BOOL = set("free ad_supported in_app_purchases editors_choice windows mac linux is_recommended steam_deck".split())
DATES = set("release_date released last_updated scraped_time date date_release".split())
TOP = set("estimated_owners owners category content_rating required_age rating free ad_supported in_app_purchases currency genres categories developers publishers supported_languages tags installs".split())

def missing(col):
    return f"({col} IS NULL OR trim({col})='' OR lower(trim({col})) IN ('nan','none','null','n/a'))"

def date_expr(col):
    return f"coalesce(try_strptime({col}, ['%b %d, %Y','%B %d, %Y','%Y-%m-%d','%Y-%m-%d %H:%M:%S','%b %Y','%B %Y']), try_cast({col} AS TIMESTAMP))"

def getdict(conn, sql):
    cur=conn.execute(sql)
    return dict(zip([x[0] for x in cur.description],cur.fetchone()))

def profile_column(conn, table, name, original, n):
    col=q(name);m=missing(col);x=f"try_cast({col} AS DOUBLE)"
    row=getdict(conn,f"SELECT count(*) FILTER (WHERE {m}) AS missing_count, count(DISTINCT {col}) FILTER (WHERE NOT {m}) AS unique_nonmissing, count(*) FILTER (WHERE trim({col}) IN ('[]','{{}}')) AS empty_collection_count, count(*) FILTER (WHERE NOT {m} AND {x} IS NOT NULL AND isfinite({x})) AS finite_numeric_count FROM {q(table)}")
    row.update({"dataset":table,"column":name,"source_column":original,"rows":n,"stored_type":"VARCHAR audit view","missing_fraction":row["missing_count"]/n if n else None,"invalid_count":None,"invalid_rule":"not assessed"})
    available=n-row["missing_count"]
    if name in NUMERIC or (available>0 and row["finite_numeric_count"]==available and name not in {"app_id","user_id","review_id","developer_id"}):
        row["observed_type"]="numeric" if row["finite_numeric_count"]==available else "numeric_with_parse_failures"
        extra=getdict(conn,f"SELECT count(*) FILTER (WHERE NOT {m} AND ({x} IS NULL OR NOT isfinite({x}))) AS numeric_parse_invalid, count(*) FILTER (WHERE {x}<0) AS negative_count, count(*) FILTER (WHERE {x}=0) AS zero_count, min({x}) FILTER (WHERE isfinite({x})) AS minimum, max({x}) FILTER (WHERE isfinite({x})) AS maximum, quantile_cont({x},[0.25,0.5,0.75,0.9,0.99]) FILTER (WHERE isfinite({x})) AS quantiles FROM {q(table)}")
        row.update(extra)
        rule=f"NOT {m} AND ({x} IS NULL OR NOT isfinite({x}) OR {x}<0"
        upper=5 if name=="rating" and table.startswith("google") else 100 if name in {"discount","metacritic_score","positive_ratio","pct_pos_total","pct_pos_recent"} else None
        if upper is not None:rule+=f" OR {x}>{upper}"
        rule+=")"
        row["invalid_count"]=conn.execute(f"SELECT count(*) FROM {q(table)} WHERE {rule}").fetchone()[0]
        row["invalid_rule"]="finite numeric >=0" + (f" and <= {upper}" if upper else "")
    elif name in BOOL:
        row["observed_type"]="boolean_text"
        row["invalid_count"]=conn.execute(f"SELECT count(*) FROM {q(table)} WHERE NOT {m} AND lower({col}) NOT IN ('true','false','0','1')").fetchone()[0]
        row["invalid_rule"]="true/false/0/1 (case-insensitive)"
    elif name in DATES:
        dt=date_expr(col)
        row["observed_type"]="date_text"
        row.update(getdict(conn,f"SELECT min({dt}) AS date_minimum,max({dt}) AS date_maximum,count(*) FILTER (WHERE NOT {m} AND {dt} IS NULL) AS invalid_count,count(*) FILTER (WHERE {dt}>TIMESTAMP '{DATE} 23:59:59') AS future_relative_to_audit,count(*) FILTER (WHERE {dt}<TIMESTAMP '1970-01-01') AS before_1970 FROM {q(table)}"))
        row["invalid_rule"]="nonmissing date not parsed by documented ISO/English month formats; month-only parsed to first day"
    else:
        row["observed_type"]="empty" if available==0 else "text_or_serialized_collection"
    if name in TOP:
        vals=conn.execute(f"SELECT {col},count(*) AS n FROM {q(table)} WHERE NOT {m} GROUP BY 1 ORDER BY n DESC,1 LIMIT 12").fetchall()
        row["top_values"]=json.dumps([{ "value":str(a)[:250],"count":b} for a,b in vals],ensure_ascii=False)
    for k,v in list(row.items()):
        if isinstance(v,list):row[k]=json.dumps(v)
        if isinstance(v,float) and not math.isfinite(v):row[k]=None
    return row

def table_profile(conn,key,source,header,path=None):
    normalize_view(conn,"input_source",source,header)
    conn.execute(f"CREATE TABLE {q(key)} AS SELECT " + ",".join(f"cast({q(canonical(h))} AS VARCHAR) AS {q(canonical(h))}" for h in header) + " FROM input_source")
    n=conn.execute(f"SELECT count(*) FROM {q(key)}").fetchone()[0]
    cols=[canonical(x) for x in header]
    ident=next((x for x in ("app_id","review_id","user_id","appid") if x in cols),None)
    # Review ID is the row key, while app_id is intentionally repeated in recommendations.
    if key=="rec_recommendations":ident="review_id"
    duplicate_rows=conn.execute(f"SELECT coalesce(sum(n-1),0) FROM (SELECT {','.join(q(c) for c in cols)},count(*) n FROM {q(key)} GROUP BY {','.join(str(i+1) for i in range(len(cols)))}) WHERE n>1").fetchone()[0]
    info={"dataset":key,"rows":n,"columns":len(cols),"duplicate_rows":duplicate_rows,"key_column":ident,"duplicate_key_excess":None,"missing_key_count":None,"original_columns":header,"canonical_columns":cols}
    if ident:
        info.update(getdict(conn,f"SELECT count(*) FILTER (WHERE NOT {missing(q(ident))})-count(DISTINCT {q(ident)}) FILTER (WHERE NOT {missing(q(ident))}) AS duplicate_key_excess, count(*) FILTER (WHERE {missing(q(ident))}) AS missing_key_count FROM {q(key)}"))
    rows=[]
    for i,(original,col) in enumerate(zip(header,cols)):
        row=profile_column(conn,key,col,original,n)
        row.update({"duplicate_rows":duplicate_rows,"duplicate_key_excess":info["duplicate_key_excess"]})
        rows.append(row)
        if i and i%20==0:print(key,f"profiled {i}/{len(cols)} columns",flush=True)
    save_json(REPORTS / "profiles" / (key+".json"),{"table":info,"columns":rows})
    if key in {"fronkon_local","fronkon_hf","fronkon_json","google_games","google_sports_ambiguous","nik_steam","rec_games"} or key.startswith("artem_"):
        conn.execute(f"COPY {q(key)} TO {lit(INTERIM / (key+'.parquet'))} (FORMAT PARQUET, COMPRESSION ZSTD)")
    return info,rows

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("--only",nargs="*");ap.add_argument("--resume",action="store_true");args=ap.parse_args()
    validation=json.loads((REPORTS / "header_validation.json").read_text())
    if not validation["header_interpretation_verified"]:
        raise ValueError("Header validation failed; no interpretation allowed")
    conn=connection()
    for item in sources():
        key=item["key"]
        if args.only and key not in args.only:continue
        if args.resume and (REPORTS / "profiles" / (key+".json")).exists():continue
        print("START",key,flush=True)
        p=item["path"]
        if p.suffix==".csv":source,header=csv_source(p,item.get("repaired",False))
        else:
            source=f"read_parquet({lit(p)})"
            header=[x[0] for x in conn.execute("DESCRIBE SELECT * FROM "+source).fetchall()]
        info,rows=table_profile(conn,key,source,header,p)
        print("DONE",key,info["rows"],"duplicate rows",info["duplicate_rows"],flush=True)
        if key=="google_all":
            cats=conn.execute('SELECT category,count(*) FROM google_all GROUP BY 1 ORDER BY 1').fetchall()
            save_csv(REPORTS / "google_categories.csv",[{"category":k,"rows":v,"included_as_game":k in GAME_CATEGORIES,"ambiguous":k=='Sports',"rule":"16 exclusive game labels; Sports held out because app/game category collision"} for k,v in cats])
            selector="SELECT * FROM google_all WHERE category IN ("+",".join(lit(x) for x in GAME_CATEGORIES)+")"
            game_header=[canonical(x) for x in header]
            ginfo,grows=table_profile(conn,"google_games","("+selector+")",game_header)
            print("GAME_SUBSET",ginfo["rows"],flush=True)
            conn.execute("DROP TABLE google_games")
            table_profile(conn,"google_sports_ambiguous","(SELECT * FROM google_all WHERE category='Sports')",game_header)
            conn.execute("DROP TABLE google_sports_ambiguous")
        conn.execute(f"DROP TABLE {q(key)}")
    tables=[];quality=[]
    for p in sorted((REPORTS / "profiles").glob("*.json")):
        data=json.loads(p.read_text(encoding="utf-8"));tables.append(data["table"]);quality.extend(data["columns"])
    save_csv(REPORTS / "data_quality_summary.csv",quality)
    save_json(REPORTS / "profile_tables.json",tables)
    conn.close()

if __name__=="__main__":
    main()
