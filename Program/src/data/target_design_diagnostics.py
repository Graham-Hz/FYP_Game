"""Compare target definitions on explicit provisional cohorts; no fitted models."""
import ast
import json
import re
import numpy as np
import pandas as pd
from audit_common import INTERIM, REPORTS, DATE, connection, lit, save_csv, save_json, sha256
from profile_datasets import date_expr, missing

OUT = REPORTS / 'research_design'
PC = 'artem_games_march2025_full'
MOBILE = 'google_games'

def parse_collection(value):
    if value is None or pd.isna(value) or value == '':
        return []
    parsed = ast.literal_eval(value)
    if isinstance(parsed, dict):
        return list(parsed)
    if not isinstance(parsed, list):
        raise ValueError('Expected a list or dict; do not silently split on commas')
    return parsed

def class_counts(labels, platform, target, scope):
    valid = labels.dropna()
    rows = []
    for label, count in valid.value_counts().sort_index().items():
        rows.append({'platform': platform, 'scope': scope, 'target': target,
                     'class': label, 'rows': int(count), 'fraction_of_eligible': count/len(valid),
                     'eligible_rows': len(valid), 'unlabelled_rows': len(labels)-len(valid),
                     'majority_share_not_model_accuracy': valid.value_counts().max()/len(valid)})
    return rows

def owner_labels(df):
    intervals = df.estimated_owners.str.extract(r'^(\d+)\s*-\s*(\d+)$').astype('Int64')
    lower, upper = intervals[0], intervals[1]
    valid = lower.notna() & upper.notna() & (lower >= 0) & (upper > 0) & (lower <= upper)
    label = pd.Series(pd.NA, index=df.index, dtype='string')
    label.loc[valid & (upper <= 20_000)] = 'O1_source_interval_up_to_20k'
    label.loc[valid & (lower >= 20_000) & (upper <= 100_000)] = 'O2_source_intervals_20k_to_100k'
    label.loc[valid & (lower >= 100_000)] = 'O3_source_intervals_100k_plus'
    assert (label.notna() == valid).all(), 'A source interval straddles a proposed threshold'
    return label, (lower.eq(0) & upper.eq(0)).fillna(False)

def mobile_labels(values, detailed=False):
    labels = pd.Series(pd.NA, index=values.index, dtype='string')
    valid = values.notna() & values.ge(0)
    labels.loc[valid & values.lt(1000)] = 'M1_under_1k'
    labels.loc[valid & values.ge(1000) & values.lt(100000)] = 'M2_1k_to_under_100k'
    labels.loc[valid & values.ge(100000)] = 'M3_100k_plus'
    if detailed:
        labels.loc[valid & values.ge(100000) & values.lt(1000000)] = 'M3_100k_to_under_1m'
        labels.loc[valid & values.ge(1000000)] = 'M4_1m_plus'
    return labels

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    conn = connection()
    paths = {key: INTERIM/(key+'.parquet') for key in [PC, MOBILE, 'artem_games_may2024_full']}
    pc_fields = 'app_id,name,release_date,genres,categories,tags,developers,publishers,supported_languages,price,required_age,positive,negative,estimated_owners,num_reviews_total,pct_pos_total'
    pc = conn.execute(f'SELECT {pc_fields} FROM read_parquet({lit(paths[PC])})').df()
    # Same explicit provisional cohort as the feasibility report; no row-level cleaned file saved.
    where = f"NOT {missing('name')} AND NOT {missing('genres')} AND trim(genres) NOT IN ('[]','{{}}') AND {date_expr('release_date')}<=DATE '2025-03-13' AND NOT regexp_matches(lower(name),'(^|[^a-z])(playtest|demo)([^a-z]|$)')"
    cohort_ids = conn.execute(f'SELECT app_id FROM read_parquet({lit(paths[PC])}) WHERE {where}').df().app_id
    cohort = pc.loc[pc.app_id.isin(cohort_ids)].copy()
    assert len(cohort)==89450, 'Cohort differs from audited rule; review before using cached conclusions'
    assert pc.app_id.is_unique
    classes=[];sensitivity=[];bias=[]
    for scope,df in [('full',pc),('provisional_cohort',cohort)]:
        labels,unknown=owner_labels(df)
        classes += class_counts(labels,'PC','owners_3_tiers',scope)
        p=pd.to_numeric(df.positive,errors='coerce');ng=pd.to_numeric(df.negative,errors='coerce')
        volume=(p+ng).where(p.ge(0)&ng.ge(0))
        review_labels=pd.cut(volume,[-1,0,9,99,999,np.inf],labels=['R0_zero_observed','R1_1_to_9','R2_10_to_99','R3_100_to_999','R4_1000_plus']).astype('string')
        classes += class_counts(review_labels,'PC','review_volume_diagnostic_bins',scope)
        direct=pd.to_numeric(df.num_reviews_total,errors='coerce')
        counts={'rows':len(df),'owner_labels_available':int(labels.notna().sum()),'owners_0_0':int(unknown.sum()),
                'review_components_nonnegative':int(volume.notna().sum()),'review_sum_zero':int(volume.eq(0).sum()),
                'review_sum_zero_but_num_reviews_total_positive':int((volume.eq(0)&direct.gt(0)).sum()),
                'num_reviews_total_nonnegative':int(direct.ge(0).sum()),
                'positive_both_but_counts_differ':int((volume.gt(0)&direct.gt(0)&volume.ne(direct)).sum()),
                'both_positive_count_comparisons':int((volume.gt(0)&direct.gt(0)).sum()),
                'review_volume_quantiles':{str(q):float(volume.quantile(q)) for q in [0,.25,.5,.75,.9,.99,1]},
                'review_sum_zero_and_owners_unknown':int((volume.eq(0)&unknown).sum())}
        save_json(OUT/(f'pc_{scope}_target_diagnostics.json'),counts)
        if scope=='provisional_cohort':
            df['owner_label']=labels;df['owner_unknown']=unknown
            df['price_state']=np.where(pd.to_numeric(df.price,errors='coerce').gt(0),'positive_observed_price','zero_or_unavailable_observed_price')
            age=(pd.Timestamp('2025-03-13')-pd.to_datetime(df.release_date,format='mixed',errors='coerce')).dt.days
            df['age_group']=pd.cut(age,[-1,180,365,1095,np.inf],labels=['0_to_180_days','181_to_365_days','366_to_1095_days','over_1095_days']).astype('string')
            for col in ['price_state','age_group']:
                for group,part in df.groupby(col,dropna=False):
                    bias.append({'group_by':col,'group':str(group),'rows':len(part),'owners_unknown':int(part.owner_unknown.sum()),'unknown_fraction':float(part.owner_unknown.mean())})
            for minimum in [0,180,365]:
                selected=df.loc[age.ge(minimum)]
                sensitivity.append({'platform':'PC','rule':f'age_at_least_{minimum}_days_at_reference_date','cohort_rows':len(selected),'valid_owner_labels':int(selected.owner_label.notna().sum()),'note':'reference date is dataset publication proxy, not per-record collection timestamp'})
            genre_lists=df.genres.map(parse_collection)
            software={'Animation & Modeling','Audio Production','Design & Illustration','Education','Photo Editing','Software Training','Utilities','Video Production','Web Publishing','Accounting','Game Development'}
            software_only=genre_lists.map(lambda xs: bool(xs) and set(xs).issubset(software))
            sensitivity.append({'platform':'PC','rule':'exclude_only_documented_software_genre_labels_heuristic','cohort_rows':int((~software_only).sum()),'valid_owner_labels':int(df.loc[~software_only,'owner_label'].notna().sum()),'note':'Mixed genres remain; not a verified product-type classification'})
            devs=df.developers.map(parse_collection)
            counts_devs=devs.explode().dropna().value_counts()
            feature_stats={'developer_unique_names':len(counts_devs),'largest_developer_game_count':int(counts_devs.max()),'rows_with_multiple_developers':int(devs.map(len).gt(1).sum()),'rows_without_developer':int(devs.map(len).eq(0).sum()),'unique_genre_tokens':int(genre_lists.explode().nunique()),'software_only_genre_rows':int(software_only.sum()),'required_age_zero':int(pd.to_numeric(df.required_age,errors='coerce').eq(0).sum()),'required_age_negative':int(pd.to_numeric(df.required_age,errors='coerce').lt(0).sum())}
            save_json(OUT/'pc_feature_diagnostics.json',feature_stats)
    mob_fields='app_id,app_name,category,rating,rating_count,minimum_installs,maximum_installs,price,free,currency,ad_supported,in_app_purchases,content_rating,released,scraped_time,developer_id'
    mobile=conn.execute(f'SELECT {mob_fields} FROM read_parquet({lit(paths[MOBILE])})').df()
    assert mobile.app_id.is_unique
    valid=pd.to_numeric(mobile.minimum_installs,errors='coerce').ge(0)&mobile.app_name.notna()&mobile.app_name.str.strip().ne('')
    # Match the earlier audit's declared missing-token rule for this reference cohort.
    # These may be legitimate titles; record them for column-specific cleaning review.
    title_token=mobile.app_name.str.strip().str.lower().isin(['nan','none','null','n/a'])
    save_csv(OUT/'title_missing_token_review.csv',mobile.loc[title_token,['app_id','app_name','category']].to_dict('records'))
    valid &= ~title_token
    release=pd.to_datetime(mobile.released,format='mixed',errors='coerce')
    scrape=pd.to_datetime(mobile.scraped_time,format='mixed',errors='coerce')
    valid &= release.notna()&release.le(scrape)
    mcohort=mobile.loc[valid].copy()
    assert len(mcohort)==318298
    for scope,df in [('conservative_game_categories',mobile),('provisional_cohort',mcohort)]:
        installs=pd.to_numeric(df.minimum_installs,errors='coerce')
        for detailed in [False,True]:classes+=class_counts(mobile_labels(installs,detailed),'Mobile','installs_4_tiers' if detailed else 'installs_3_tiers',scope)
    age=(scrape-release).dt.days
    for minimum in [0,180,365]:
        count=int((valid&age.ge(minimum)).sum())
        sensitivity.append({'platform':'Mobile','rule':f'age_at_least_{minimum}_days_at_row_scraped_time','cohort_rows':count,'valid_owner_labels':None,'note':'Valid install labels available for all rows in this cohort'})
    mstats={'rows':len(mcohort),'free_count':int(mcohort.free.str.lower().eq('true').sum()),'paid_count':int(mcohort.free.str.lower().eq('false').sum()),'ad_supported':mcohort.ad_supported.value_counts(dropna=False).to_dict(),'iap':mcohort.in_app_purchases.value_counts(dropna=False).to_dict(),'currency':mcohort.currency.value_counts(dropna=False).to_dict(),'content_ratings':mcohort.content_rating.value_counts(dropna=False).to_dict(),'developer_unique_ids':int(mcohort.developer_id.nunique()),'largest_developer_count':int(mcohort.developer_id.value_counts().max()),'missing_developer_id':int(mcohort.developer_id.isna().sum())}
    save_json(OUT/'mobile_feature_diagnostics.json',mstats)
    # Paired snapshots: no assumption that cumulative measures are monotone or identically collected.
    old=conn.execute(f'SELECT app_id,positive,negative,estimated_owners FROM read_parquet({lit(paths["artem_games_may2024_full"])})').df()
    merged=pc[['app_id','positive','negative','estimated_owners']].merge(old,on='app_id',suffixes=('_2025','_2024'),validate='one_to_one')
    r25=pd.to_numeric(merged.positive_2025)+pd.to_numeric(merged.negative_2025)
    r24=pd.to_numeric(merged.positive_2024)+pd.to_numeric(merged.negative_2024)
    paired={'shared_ids':len(merged),'review_sum_decreased':int(r25.lt(r24).sum()),'review_components_identical':int((merged.positive_2025.eq(merged.positive_2024)&merged.negative_2025.eq(merged.negative_2024)).sum()),'owners_label_identical':int(merged.estimated_owners_2025.eq(merged.estimated_owners_2024).sum()),'interpretation':'Descriptive comparison only; decreases do not prove an error or negative sales. Per-field timing and API filters are not established.'}
    save_json(OUT/'snapshot_pair_diagnostics.json',paired)
    save_csv(OUT/'target_candidate_balance.csv',classes)
    save_csv(OUT/'cohort_sensitivity.csv',sensitivity)
    save_csv(OUT/'owner_unknown_bias.csv',bias)
    # Independent reconciliation of proposed owners labels on the same cohort via SQL.
    sql_valid=conn.execute(f"SELECT count(*) FROM read_parquet({lit(paths[PC])}) WHERE {where} AND estimated_owners<>'0 - 0'").fetchone()[0]
    assert sql_valid==sum(x['rows'] for x in classes if x['scope']=='provisional_cohort' and x['target']=='owners_3_tiers')
    for platform,scope,target in {(x['platform'],x['scope'],x['target']) for x in classes}:
        rows=[x for x in classes if (x['platform'],x['scope'],x['target'])==(platform,scope,target)]
        assert sum(x['rows'] for x in rows)==rows[0]['eligible_rows']
        assert abs(sum(x['fraction_of_eligible'] for x in rows)-1)<1e-12
    save_json(OUT/'diagnostics_manifest.json',{'date':DATE,'input_sha256':{str(p):sha256(p) for p in paths.values()},'status':'passed','checks':['unique AppIDs','cohort counts reconcile with previous audit','owners interval boundary mapping','independent SQL owners eligibility','all class totals and proportions reconcile'],'model_training':False,'scope':'All target distributions explored before a locked evaluation split; these are design-stage diagnostics, not held-out performance.'})
    print(json.dumps({'pc_cohort':len(cohort),'mobile_cohort':len(mcohort),'paired_snapshots':paired,'verification':'passed'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
