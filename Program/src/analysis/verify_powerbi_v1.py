"""Independently compare Power BI CSV interchange cells with frozen train rows."""
from pathlib import Path
import hashlib
import json
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def band(value):
    if pd.isna(value):
        return 'Unknown', 5
    for upper, label, order in [(180, '0-179 days', 1), (365, '180-364 days', 2), (1095, '365-1094 days', 3)]:
        if value < upper:
            return label, order
    return '1095+ days', 4


def main():
    out = ROOT / 'data/processed/powerbi_v1'
    report = ROOT / 'reports/2026-10-11/lecture_review'
    manifest = json.loads((report/'powerbi_export_verification.json').read_text(encoding='utf-8'))
    for relative, spec in (manifest['inputs'] | manifest['outputs']).items():
        expected = spec['sha256'] if isinstance(spec, dict) else spec
        if digest(ROOT/relative) != expected:
            raise ValueError(f'Changed artifact: {relative}')
    count = 0
    for platform in ['pc', 'mobile']:
        features = pd.read_parquet(ROOT/f'data/processed/analysis_v1/{platform}_features.parquet')
        labels = pd.read_parquet(ROOT/f'data/processed/analysis_v1/{platform}_labels_splits.parquet')
        expected = features.merge(labels.loc[labels.split.eq('train'), ['app_id', 'target_tier']], on='app_id', validate='one_to_one')
        actual = pd.read_csv(out/f'{platform}_games.csv', dtype={'app_id': str}, keep_default_na=False)
        expected['tier_order'] = expected.target_tier.str[1].astype(int)
        bands = expected.age_days.map(band)
        expected['age_band'], expected['age_band_order'] = bands.str[0], bands.str[1]
        for col in actual.columns:
            if col in ['windows','mac','linux','categories_unavailable','languages_unavailable','free','ad_supported','in_app_purchases','price_usd_unavailable','free_unavailable']:
                expected[col] = expected[col].map(lambda v: 'Unknown' if pd.isna(v) else ('Yes' if v else 'No'))
            elif col in ['price_observed','price_usd','age_days','tier_order','age_band_order']:
                actual[col] = pd.to_numeric(actual[col], errors='raise').astype('float64')
                expected[col] = expected[col].astype('float64')
            else:
                expected[col] = expected[col].fillna('')
        assert_frame_equal(actual.sort_values('app_id').reset_index(drop=True), expected[actual.columns].sort_values('app_id').reset_index(drop=True), check_dtype=False, rtol=1e-12, atol=1e-12)
        count += len(actual)
        if platform == 'pc':
            pairs = {(r.app_id, g) for r in expected.itertuples() for g in (set(r.genres) if r.genres is not None and len(r.genres) else {'<empty_or_missing>'})}
            bridge = pd.read_csv(out/'pc_genres.csv', dtype=str, keep_default_na=False)
            assert len(bridge) == len(pairs) and set(bridge.itertuples(index=False, name=None)) == pairs
            genres = pd.read_csv(out/'genre.csv', dtype=str, keep_default_na=False)
            assert genres.genre.is_unique and set(genres.genre) == {g for _, g in pairs}
    result = {'all_exported_game_cells_match_frozen_train': True, 'pc_genre_pairs_match': True,
              'genre_dimension_matches': True, 'games_checked': count, 'bridge_pairs_checked': len(pairs),
              'numeric_tolerance': 1e-12, 'power_bi_ui_tested': False,
              'export_record_sha256': digest(report/'powerbi_export_verification.json'),
              'verifier_sha256': digest(Path(__file__))}
    (report/'powerbi_independent_verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
