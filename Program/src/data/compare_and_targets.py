"""Key-aligned version comparisons and target/cohort feasibility, without selecting a final target."""
import json
import pyarrow.parquet as pq
from audit_common import *
from profile_datasets import NUMERIC, BOOL, missing, date_expr, getdict

def numeric_summary(conn,table,name,expr,valid='true'):
    result=getdict(conn,f"SELECT count(*) AS rows, count(x) AS parsed_nonnull, count(*) FILTER(WHERE x IS NULL) AS missing_or_unparsed, count(*) FILTER(WHERE x=0) AS zero_count, count(*) FILTER(WHERE x<0) AS negative_count, count(*) FILTER(WHERE {valid} AND isfinite(x)) AS eligible_numeric_count, min(x) FILTER(WHERE {valid} AND isfinite(x)) AS minimum, max(x) FILTER(WHERE {valid} AND isfinite(x)) AS maximum, quantile_cont(x,[0.25,0.5,0.75,0.9,0.99]) FILTER(WHERE {valid} AND isfinite(x)) AS quantiles FROM (SELECT {expr} AS x FROM {q(table)})")
    result.update({"dataset":table,"candidate":name,"expression":expr,"validity_rule":valid})
    return result

def compare(conn,left,right,profiles):
    lc=profiles[left]['table']['canonical_columns'];rc=profiles[right]['table']['canonical_columns']
    if profiles[left]['table']['duplicate_key_excess'] or profiles[right]['table']['duplicate_key_excess']:
        raise ValueError('Ambiguous join key; comparisons cannot proceed')
    n=conn.execute(f'SELECT count(*) FROM {q(left)} l JOIN {q(right)} r USING(app_id)').fetchone()[0]
    summary={'left':left,'right':right,'shared_ids':n,'left_only_ids':profiles[left]['table']['rows']-n,'right_only_ids':profiles[right]['table']['rows']-n}
    vals=[];schema=[]
    for col in sorted(set(lc)|set(rc)):
        ln=profiles[left]['table']['original_columns'][lc.index(col)] if col in lc else ''
        rn=profiles[right]['table']['original_columns'][rc.index(col)] if col in rc else ''
        status='matched' if ln==rn else 'renamed' if ln and rn else 'left_only' if ln else 'right_only'
        schema.append({'left':left,'right':right,'canonical_column':col,'left_column':ln,'right_column':rn,'status':status,'left_observed_type':next((x['observed_type'] for x in profiles[left]['columns'] if x['column']==col),''),'right_observed_type':next((x['observed_type'] for x in profiles[right]['columns'] if x['column']==col),''),'semantic_equivalence':'name mapping only; source definitions and serialization checked separately'})
        if col not in lc or col not in rc:continue
        a='l.'+q(col);b='r.'+q(col)
        raw=f'{a} IS DISTINCT FROM {b}'
        if col in NUMERIC:
            sem=f'try_cast({a} AS DOUBLE) IS DISTINCT FROM try_cast({b} AS DOUBLE)';method='numeric cast equality'
        elif col in BOOL:
            sem=f'lower({a}) IS DISTINCT FROM lower({b})';method='case-insensitive boolean text'
        else:
            sem=raw;method='literal equality; collection serialization may differ'
        counts=getdict(conn,f'SELECT count(*) FILTER(WHERE {raw}) AS literal_differences,count(*) FILTER(WHERE {sem}) AS compared_value_differences FROM {q(left)} l JOIN {q(right)} r USING(app_id)')
        vals.append({'left':left,'right':right,'column':col,'aligned_rows':n,'comparison':method,**counts})
    return summary,schema,vals

def main():
    conn=connection()
    profiles={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (REPORTS/'profiles').glob('*.json')}
    keys=['fronkon_local','fronkon_hf','fronkon_json','artem_games_march2025_full','artem_games_march2025_cleaned','artem_games_may2024_full','artem_games_may2024_cleaned','google_games','google_sports_ambiguous','nik_steam','rec_games']
    for key in keys:
        conn.execute(f'CREATE VIEW {q(key)} AS SELECT * FROM read_parquet({lit(INTERIM/(key+".parquet"))})')
    schemas=[];values=[];comparisons=[]
    hf_item=next(x for x in sources() if x['key']=='fronkon_hf')
    hf_schema=pq.ParquetFile(hf_item['path']).schema_arrow
    native_hf={canonical(f.name):str(f.type) for f in hf_schema}
    save_json(REPORTS/'hf_native_schema.json',{'revision':hf_item['revision'],'fields':native_hf})
    pairs=[('fronkon_local','fronkon_hf'),('fronkon_local','fronkon_json'),('fronkon_local','artem_games_march2025_full'),('artem_games_march2025_full','artem_games_march2025_cleaned'),('artem_games_may2024_full','artem_games_may2024_cleaned')]
    for left,right in pairs:
        summary,schema,vals=compare(conn,left,right,profiles)
        comparisons.append(summary);schemas.extend(schema);values.extend(vals)
        print('COMPARE',summary,flush=True)
    for row in schemas:
        for side in ['left','right']:
            row[side+'_source_storage_type']=native_hf.get(row['canonical_column'],'') if row[side]=='fronkon_hf' else ('JSON; see source and audit string conversion' if row[side]=='fronkon_json' else 'CSV text; no native column type')
    save_csv(REPORTS/'schema_comparison.csv',schemas)
    save_csv(REPORTS/'aligned_value_comparison.csv',values)
    save_csv(REPORTS/'version_overlap.csv',comparisons)
    targets=[];owners=[];checks=[];cohorts=[];distributions=[]
    for key in keys:
        cols=profiles[key]['table']['canonical_columns'];n=profiles[key]['table']['rows']
        if 'positive' in cols and 'negative' in cols:
            total='try_cast(positive AS DOUBLE)+try_cast(negative AS DOUBLE)'
            targets.append(numeric_summary(conn,key,'review_volume_positive_plus_negative',total,'x>=0'))
            targets.append(numeric_summary(conn,key,'positive_share_when_reviews_exist',f'try_cast(positive AS DOUBLE)/nullif({total},0)','x>=0 AND x<=1'))
            counts=getdict(conn,f'SELECT count(*) FILTER(WHERE ({total})=0) AS no_reviews,count(*) FILTER(WHERE ({total})>=10) AS at_least_10_reviews,count(*) FILTER(WHERE ({total})>=50) AS at_least_50_reviews,count(*) FILTER(WHERE ({total})>=100) AS at_least_100_reviews FROM {q(key)}')
            checks.append({'dataset':key,'check':'review_support_thresholds',**counts})
        for col in ['peak_ccu','num_reviews_total','pct_pos_total','rating','rating_count','minimum_installs','maximum_installs']:
            if col in cols:targets.append(numeric_summary(conn,key,col,f'try_cast({q(col)} AS DOUBLE)','x>=0'))
        owner_col='estimated_owners' if 'estimated_owners' in cols else 'owners' if 'owners' in cols else None
        if owner_col:
            lo=f"try_cast(regexp_extract({q(owner_col)},'^([0-9]+)\\s*-\\s*([0-9]+)$',1) AS BIGINT)"
            hi=f"try_cast(regexp_extract({q(owner_col)},'^([0-9]+)\\s*-\\s*([0-9]+)$',2) AS BIGINT)"
            counts=getdict(conn,f'SELECT count(*) FILTER(WHERE {lo} IS NULL OR {hi} IS NULL OR {lo}>{hi}) AS malformed_or_reversed,count(*) FILTER(WHERE {lo}=0 AND {hi}=0) AS zero_zero_unknown,count(*) FILTER(WHERE {hi}>0) AS nonzero_intervals,count(*) FILTER(WHERE {lo}>=20000) AS lower_bound_at_least_20000 FROM {q(key)}')
            checks.append({'dataset':key,'check':'owner_intervals',**counts})
            for label,count in conn.execute(f'SELECT {q(owner_col)},count(*) FROM {q(key)} GROUP BY 1 ORDER BY 2 DESC,1').fetchall():owners.append({'dataset':key,'interval':label,'rows':count,'fraction':count/n})
        if 'name' in cols:
            snapshot='2025-03-13' if 'march2025' in key else '2024-05-31' if 'may2024' in key else '2019-05-31' if key=='nik_steam' else DATE
            rules=[('all_records','true'),('nonempty_title',f'NOT {missing(q("name"))}')]
            if 'genres' in cols:rules.append(('nonempty_genres',f"NOT {missing(q('genres'))} AND trim(genres) NOT IN ('[]','{{}}')"))
            if 'release_date' in cols:rules.append(('release_not_after_reference_date',f"{date_expr(q('release_date'))} <= DATE '{snapshot}'"))
            rules.append(('exclude_title_playtest_demo_heuristic',"NOT regexp_matches(lower(name),'(^|[^a-z])(playtest|demo)([^a-z]|$)')"))
            combined='true';previous=n
            for label,condition in rules:
                combined+=' AND ('+condition+')';remaining=conn.execute(f'SELECT count(*) FROM {q(key)} WHERE {combined}').fetchone()[0]
                cohorts.append({'dataset':key,'step':label,'remaining_rows':remaining,'removed_at_step':previous-remaining,'reference_date':snapshot,'condition':condition,'status':'proposed audit cohort only; no cleaned dataset or model produced'})
                previous=remaining
            checks.append({'dataset':key,'check':'title_duplicates','duplicate_title_excess':conn.execute(f'SELECT count(name)-count(DISTINCT name) FROM {q(key)}').fetchone()[0]})
        if key.startswith('google_'):
            info=getdict(conn,f"SELECT count(*) FILTER(WHERE try_cast(rating AS DOUBLE)=0 AND try_cast(rating_count AS DOUBLE)=0) AS zero_rating_with_zero_count,count(*) FILTER(WHERE try_cast(rating AS DOUBLE)>0 AND try_cast(rating_count AS DOUBLE)=0) AS positive_rating_with_zero_count,count(*) FILTER(WHERE try_cast(maximum_installs AS DOUBLE)<try_cast(minimum_installs AS DOUBLE)) AS maximum_less_than_minimum,count(*) FILTER(WHERE try_cast(regexp_replace(installs,'[^0-9]','','g') AS DOUBLE) IS DISTINCT FROM try_cast(minimum_installs AS DOUBLE)) AS install_label_minimum_mismatch,count(*) FILTER(WHERE {date_expr('released')}>{date_expr('scraped_time')}) AS release_after_scrape,count(*) FILTER(WHERE {date_expr('last_updated')}>{date_expr('scraped_time')}) AS update_after_scrape,count(*) FILTER(WHERE lower(free)='true' AND try_cast(price AS DOUBLE)>0) AS free_with_positive_price FROM {q(key)}")
            checks.append({'dataset':key,'check':'mobile_cross_field',**info})
            expr="CASE WHEN try_cast(minimum_installs AS DOUBLE) IS NULL THEN 'missing' WHEN try_cast(minimum_installs AS DOUBLE)<1000 THEN '<1k' WHEN try_cast(minimum_installs AS DOUBLE)<100000 THEN '1k-<100k' ELSE '>=100k' END"
            for label,count in conn.execute(f'SELECT {expr},count(*) FROM {q(key)} GROUP BY 1 ORDER BY 1').fetchall():distributions.append({'dataset':key,'candidate':'illustrative_install_bands_not_final','class':label,'rows':count,'fraction':count/n})
            rules=[('all_records_in_this_subset','true'),('nonmissing_installs','try_cast(minimum_installs AS DOUBLE)>=0'),('nonempty_title',f'NOT {missing("app_name")}'),('known_release_date',f'{date_expr("released")} IS NOT NULL'),('release_not_after_scrape',f'{date_expr("released")}<={date_expr("scraped_time")}')]
            previous=n;combined='true'
            for label,condition in rules:
                combined+=' AND ('+condition+')';remaining=conn.execute(f'SELECT count(*) FROM {q(key)} WHERE {combined}').fetchone()[0]
                cohorts.append({'dataset':key,'step':label,'remaining_rows':remaining,'removed_at_step':previous-remaining,'condition':condition,'status':'proposed audit cohort only'})
                previous=remaining
    save_json(REPORTS/'target_statistics.json',targets)
    save_json(REPORTS/'cross_field_checks.json',checks)
    save_csv(REPORTS/'owners_distribution.csv',owners)
    save_csv(REPORTS/'candidate_class_balance.csv',distributions)
    save_csv(REPORTS/'proposed_cohort_counts.csv',cohorts)
    # A direct CSV hash comparison is meaningful; a CSV-vs-Parquet byte comparison is not.
    lock=json.loads((META/'sources_lock.json').read_text())
    structure=json.loads((REPORTS/'structure_and_hashes.json').read_text())
    local=next(v for k,v in structure.items() if k.replace('\\','/')=='Steam Games Dataset/games.csv')
    remote=next(x for x in lock['hf']['FronkonGames/steam-games-dataset']['files'] if x['path']=='games.csv')
    save_json(REPORTS/'mirror_hash_comparison.json',{'local_csv_sha256':local['sha256'],'hf_csv_lfs_sha256':remote['lfs']['oid'],'identical_csv_bytes':local['sha256']==remote['lfs']['oid'],'hf_revision':lock['hf']['FronkonGames/steam-games-dataset']['revision'],'note':'HF repository CSV and Parquet are separate artifacts with different row counts; local Kaggle download version itself is not known.'})
    # Sensitivity of the author-provided cleaned table: report actual exclusions, never infer all are duplicates.
    cleancheck=getdict(conn,"SELECT count(*) AS removed,count(*) FILTER(WHERE regexp_matches(lower(f.name),'(^|[^a-z])(playtest|demo)([^a-z]|$)')) AS removed_title_playtest_or_demo,count(*) FILTER(WHERE f.genres='[]') AS removed_empty_genres FROM artem_games_march2025_full f ANTI JOIN artem_games_march2025_cleaned c USING(app_id)")
    save_json(REPORTS/'author_cleaning_comparison.json',cleancheck)
    joins=[]
    for left,right in [('artem_games_march2025_full','rec_games'),('fronkon_local','rec_games'),('artem_games_march2025_full','nik_steam')]:
        count=conn.execute(f'SELECT count(*) FROM {q(left)} JOIN {q(right)} USING(app_id)').fetchone()[0]
        joins.append({'left':left,'right':right,'shared_app_ids':count,'join_key':'app_id','note':'Key overlap only; timing, product type, licensing and variable meaning still require validation before joining.'})
    save_csv(REPORTS/'supplementary_join_coverage.csv',joins)
    print('TARGET CHECKS',json.dumps(checks,ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
