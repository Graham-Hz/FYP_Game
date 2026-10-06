"""Build the inventory and human-readable audit notes from measured evidence."""
import csv
import json
from audit_common import *

def read(name):
    return json.loads((REPORTS/name).read_text(encoding='utf-8'))

def main():
    lock=json.loads((META/'sources_lock.json').read_text())
    structure=read('structure_and_hashes.json')
    profiles={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (REPORTS/'profiles').glob('*.json')}
    def col(key,name):return next(x for x in profiles[key]['columns'] if x['column']==name)
    def n(key):return profiles[key]['table']['rows']
    def pct(count,total):return f'{count/total:.2%}'
    upstream={
        'fronkongames/steam-games-dataset':('Steam Store API and SteamSpy','FronkonGames Steam-Games-Scraper','https://github.com/FronkonGames/Steam-Games-Scraper'),
        'artermiloff/steam-games-dataset':('Steam Store pages, Steam API and SteamSpy','Store scraping and FronkonGames scraper','https://github.com/FronkonGames/Steam-Games-Scraper'),
        'gauthamp10/google-playstore-apps':('Google Play Store','Author reports June 2021 collection using cloud scraper; Scrapy and google-play-scraper mentioned','https://github.com/gauthamp10/Google-Playstore-Dataset'),
        'nikdavis/steam-store-games':('Steam Store and SteamSpy APIs','Author reports collection around May 2019','https://nik-davis.github.io/posts/2019/steam-data-collection/'),
        'antonkozyriev/game-recommendations-on-steam':('Steam Official Store','Collected and preprocessed recommendations; user identifiers anonymized by author','https://www.kaggle.com/datasets/antonkozyriev/game-recommendations-on-steam'),
    }
    mapped={str(x.get('original_path',x['path']).relative_to(DATA)):x for x in sources() if x.get('original_path',x['path']).is_relative_to(DATA)}
    inventory=[]
    for rel,entry in structure.items():
        path=Path(rel);folder=path.parts[0] if len(path.parts)>1 else path.stem
        repo=FOLDERS[folder];meta=lock['kaggle'][repo];up=upstream[repo]
        item=mapped.get(rel,{});key=item.get('key');profile=profiles.get(key,{}).get('table',{})
        row={"dataset":key or folder,"file":'Dataset/'+rel.replace('\\','/'),"platform":'Kaggle local download',"source_url":'https://www.kaggle.com/datasets/'+repo,"author":repo.split('/')[0],"upstream_source":up[0],"collection_method":up[1],"upstream_documentation":up[2],"license_as_reported":meta.get('licenseName'),"metadata_retrieved_date":DATE,"local_download_date":'unknown',"exact_local_host_version":'unknown; raw SHA-256 pinned',"current_host_version_not_local_version":meta.get('currentVersionNumber'),"current_host_update_not_local_snapshot":meta.get('lastUpdated'),"downloads":meta.get('downloadCount'),"download_metric":'Kaggle cumulative dataset downloads',"bytes":entry['bytes'],"sha256":entry['sha256'],"format":path.suffix.lstrip('.'),"rows":entry.get('rows'),"raw_header_columns":entry.get('header_columns'),"interpreted_columns":profile.get('columns'),"row_widths":json.dumps(entry.get('row_widths',{})),"audit_level":'full column profile' if profile else 'archive/file hash and structure only',"duplicate_rows":profile.get('duplicate_rows'),"duplicate_key_excess":profile.get('duplicate_key_excess'),"encoding":entry.get('encoding',''),"source_timezone":'unknown unless source supplies it'}
        if key=='fronkon_json':row['rows']=n(key);row['raw_header_columns']=43;row['note']='42 JSON record fields plus top-level app ID; JSON streamed to an audit-only Parquet'
        if key=='fronkon_local':row['note']='39 header labels vs 40 fields; evidence-verified in-memory split of DiscountDLC count; bytes equal HF pinned games.csv'
        if folder=='Google Play Store Apps':row['snapshot_evidence']='2021-06-15 to 2021-06-16 observed Scraped Time; full date coverage in profiles'
        if path.name=='games_metadata.json':
            js=read('json_metadata_structure.json');row.update(rows=js['rows'],interpreted_columns=len(js['fields']),audit_level='full JSONL structure and key check',duplicate_key_excess=js['duplicate_app_ids'])
        inventory.append(row)
    for repo,meta in lock['hf'].items():
        for f in meta['files']:
            if not f['path'].endswith(('.csv','.json','.jsonl','.parquet')):continue
            is_main=repo=='FronkonGames/steam-games-dataset'
            downloaded=is_main and f['path']=='data/train-00000-of-00001.parquet'
            license=meta.get('license') or ('CC BY-NC 4.0 (dataset card)' if repo=='adde023/steam-reviews' else 'unknown')
            inventory.append({'dataset':'fronkon_hf' if downloaded else repo,'file':f['path'],'platform':'Hugging Face','source_url':f'https://huggingface.co/datasets/{repo}/blob/{meta["revision"]}/{f["path"]}','author':repo.split('/')[0],'upstream_source':'Steam Store API and SteamSpy' if is_main else 'RAWG API' if 'video-games' in repo else 'Steam User Reviews API via kieranpoc/steam-reviews on Kaggle','license_as_reported':license,'metadata_retrieved_date':DATE,'exact_local_host_version':meta['revision'],'current_host_update_not_local_snapshot':meta['last_modified'],'downloads':meta['downloads_last_month'],'download_metric':'Hugging Face repository downloads in last month; repeated per file, do not sum','bytes':f['size'],'sha256':(f.get('lfs') or {}).get('oid',''),'hash_provenance':'remote LFS metadata; verified locally for downloaded Parquet and matching CSV','format':Path(f['path']).suffix.lstrip('.'),'rows':n('fronkon_hf') if downloaded else n('fronkon_local') if is_main and f['path']=='games.csv' else None,'interpreted_columns':41 if downloaded else 40 if is_main and f['path']=='games.csv' else None,'audit_level':'full column profile; downloaded pinned file' if downloaded else 'identical local CSV hash; audited locally' if is_main and f['path']=='games.csv' else 'remote metadata only; not downloaded','note':'Repository update date does not prove each file was regenerated; card count is not a measured row count.'})
    save_csv(REPORTS/'dataset_inventory.csv',inventory)
    hv=read('header_validation.json');checks=read('cross_field_checks.json');authorclean=read('author_cleaning_comparison.json')
    def check(key,kind):return next(x for x in checks if x['dataset']==key and x['check']==kind)
    stat=read('target_statistics.json')
    def target(key,name):return next(x for x in stat if x['dataset']==key and x['candidate']==name)
    pc='artem_games_march2025_full';mobile='google_games'
    owner=check(pc,'owner_intervals');reviews=check(pc,'review_support_thresholds');m=check(mobile,'mobile_cross_field')
    target_table=[]
    for key in ['fronkon_local','fronkon_json','fronkon_hf',pc,'artem_games_march2025_cleaned']:
        ow=check(key,'owner_intervals');rv=check(key,'review_support_thresholds')
        target_table.append(f"| `{key}` | {n(key):,} | {ow['zero_zero_unknown']:,} | {rv['no_reviews']:,} | {col(key,'peak_ccu')['zero_count']:,} | {rv['at_least_50_reviews']:,} |")
    target_md=f'''# 預測目標可行性審核

審核日期：{DATE}（Asia/Hong_Kong）。這是工作筆記及方法建議，並非已完成研究的結論或提交稿。尚未訓練模型，尚未選定最終 target。

## 已測得的 PC 分布

| 審核版本 | 記錄數 | owners 為 0 - 0 | 正負評論合計為零 | CCU 為零 | 至少 50 則正負評論 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(target_table)}

### Estimated owners

**事實**：March 2025 full 有 {owner['nonzero_intervals']:,} 筆非零區間；{owner['zero_zero_unknown']:,} 筆為 `0 - 0`；格式錯誤或上下界顛倒為 {owner['malformed_or_reversed']}。逐區間分布見 `owners_distribution.csv`。

**解釋與未知**：它是 SteamSpy 估算區間，不是官方銷量。`0 - 0` 的資料生成原因未充分確認，不能當作零銷量或失敗案例。把區間中點當真實數量會引入人為精確度。免費遊戲 owners 也不等於付費購買者。

**候選方案**：先評估非零區間的有序分類，對細分類與合併類別做敏感度分析。門檻須有研究問題依據，不能挑選令 accuracy 較高的門檻。排除未知區間會改變樣本組成，須報告排除比例及類型分布。

### 評論量與口碑

**事實**：March 2025 full 的 `positive + negative` 中位數為 {target(pc,'review_volume_positive_plus_negative')['quantiles'][1]:g}，零值 {reviews['no_reviews']:,} 筆。所有候選的分位數見 `target_statistics.json`。

**候選方案**：評論量可用作歷史曝光／參與程度代理；比較 `log1p` 回歸及分級分類。不得稱為收入或商業成功。以評論量作 target 時，排除 positive、negative、recommendations、review counts 及由它們計算的比例等結果欄位作輸入。

口碑可用正評比例作次要結果，但零評論時比例未定義。至少 10／50／100 則評論的樣本量已計算；50 並非既定採用門檻。小樣本比例必須考慮不確定性或平滑，且門檻會造成選擇偏差。

**資料問題**：March 2025 full 的 `num_reviews_total` 與 `pct_pos_total` 各有 {col(pc,'num_reviews_total')['negative_count']:,} 筆 -1；這是無效領域值／疑似缺失標記，尚不可當作有效評論數或比例。`required_age` 有 1 筆 -1，零值也不能解讀成玩家平均年齡。

### CCU、遊玩時間及複合成功分數

March 2025 full 的 CCU 零值比例為 {pct(col(pc,'peak_ccu')['zero_count'],n(pc))}。CCU 的時間窗口及更新方式尚待確認，因此不建議作唯一主 target。遊玩時間也需釐清單位、採樣及零值語義。

目前不建議建立複合成功分數：owners、評論量、CCU、評分不代表同一結果，任意加權欠缺效度證據，亦可能把同一人氣訊號重複計算。

## 已測得的手機遊戲分布

**事實**：從 2,312,944 筆 Google Play 應用記錄中，以 16 個明確遊戲 category 標籤保留 {n(mobile):,} 筆。另有 {n('google_sports_ambiguous'):,} 筆 Sports 標籤記錄混有遊戲及一般體育 App，獨立存放於審核中間資料，不納入保守樣本。

- `Minimum Installs` 缺失 {col(mobile,'minimum_installs')['missing_count']:,} 筆，零值 {col(mobile,'minimum_installs')['zero_count']:,} 筆；中位數 1,000。
- 三級範例（尚未定案）：少於 1,000 為 156,155 筆，1,000 至低於 100,000 為 119,905 筆，至少 100,000 為 52,372 筆，另有 81 筆缺失。這是原始保守樣本分布，並非完成所有 cohort 規則後的訓練類別比例。
- `Rating` 及 `Rating Count` 各缺失 {col(mobile,'rating')['missing_count']:,} 筆；{m['zero_rating_with_zero_count']:,} 筆評分與評分數同時為零。不能把未獲評分解讀成極差口碑。
- `Installs` 移除逗號及 `+` 後，與 `Minimum Installs` 的不一致數為 {m['install_label_minimum_mismatch']}。它們並非兩個獨立訊號。
- `Maximum Installs < Minimum Installs` 為 {m['maximum_less_than_minimum']} 筆，但 Maximum Installs 的上游定義仍未核實，不能僅憑欄名宣稱它是區間上界或官方精確下載次數。
- 原始發行日期缺失 {col(mobile,'released')['missing_count']:,} 筆；觀察日期為 2021-06-15 至 2021-06-16。這是歷史截面，不能稱為 2026 年市場。

**候選方案**：以可解釋的安裝量分級作 Mobile 主 target 候選；保留原始 `Installs` 標籤，將 `Minimum Installs` 視為公開分級的下界。`Maximum Installs` 暫不作主 target。Rating 可作具評分支持量要求的次要分析。

## 決策時點與洩漏控制

系統定位是早期開發規劃。特徵須依「使用者當時能否知道」審查，不能只依相關性挑選。

| 特徵群 | 預定用途 | 限制 |
|---|---|---|
| Genre/category、擬定內容分級、平台與語言 | 開發規劃輸入候選 | 當前資料值可能經上市後更改；內容分級不代表實際受眾人口 |
| Price、free/paid、ads、IAP | 歷史同類產品比較 | 觀察到的是快照狀態，並非已證實的首發策略；不能做因果最佳化 |
| Owners、CCU、評論、評分、遊玩時間 | 結果／描述性基準 | 原則上不輸入早期預測模型 |
| User tags | 描述或敏感度分析 | 可隨上市後回饋形成，不能默認首發前可得 |
| Developer/publisher | 群組切分、解釋候選 | 高基數及同公司洩漏風險；名稱不能直接當業績能力 |
| Release date、上市至快照時間 | 控制曝光期及分層 | 不得以未來才能知道的累積結果宣稱上市前預測 |

## 評估設計建議

1. 先界定 cohort、target、資料時點及最低支持量；再劃分資料。所有編碼、缺失處理、類別合併及調參只在訓練資料擬合。
2. 分類比較 majority baseline、簡單線性／有序模型與少量樹模型；報告 macro-F1、balanced accuracy、逐類 recall、混淆矩陣。有序 target 另報有序誤差；需要機率輸出時檢查校準。
3. 回歸比較中位數 baseline 與少量候選模型；同時報告原尺度 MAE、對數尺度誤差及分組表現，不能只看 R²。
4. 評估 release-cohort 切分及 developer/publisher 群組切分。單一截面的 release-year holdout 並不自動等於真實前瞻測試；2024／2025 快照可研究時間穩健性，但須先審核同 AppID 的特徵時點。
5. 使用固定 seed 42，固定測試集；報告不確定性、零值／缺失處理及不同樣本篩選的敏感度。
6. PC 與 Mobile 以同一研究框架分別評估，不直接合併 owners 與 installs，不以不同年份截面比較哪個平台較賺錢。

**需要決定但本次未代為定案**：PC 以 owners 區間還是評論量為主、Mobile 分級門檻、是否接受歷史決策支援定位、導師是否批准雙平台範圍。

來源：本地全檔審核輸出；[Steam dataset source](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset)；[Google Play dataset source](https://www.kaggle.com/datasets/gauthamp10/google-playstore-apps)；[Google 官方 App/Game 類別](https://support.google.com/googleplay/android-developer/answer/9859673?hl=en)。
'''
    (REPORTS/'target_feasibility.md').write_text(target_md,encoding='utf-8')
    download_rows=[]
    for repo,meta in lock['kaggle'].items():download_rows.append(f"| [{repo}](https://www.kaggle.com/datasets/{repo}) | {meta['downloadCount']:,} | {meta['licenseName']} |")
    report=f'''# 遊戲開發決策支援系統資料集可行性報告

審核日期：{DATE}（Asia/Hong_Kong）。本文件是可檢查的專案工作筆記，不是供直接提交的 FYP 論文。事實來自本地檔案全量檢查及已保存的來源 metadata；建議與尚未確認事項分開列出。

## 建議決定

**建議以 Artemiy 的 March 2025 full 作 PC 第一主候選，以 Google Play 的 2021 年保守遊戲子集作 Mobile 主候選，進入研究問題與清理規則確認階段。** 這是可行性建議，尚未替你或導師確定最終資料集／題目／target。

PC 建議從原版開始自行建立可追溯清理流程，作者 cleaned 版用於敏感度比較。理由是它有明確的 2025 年 3 月資料說明、47 欄、可用 genres/tags，以及可比較的 2024 版本。這不代表較新 FronkonGames 資料沒有價值，而是它的 CSV、JSON、Parquet 不同步，且資料時點與更新語義仍需較多核實。

Mobile 可支援歷史安裝量、類型與變現狀態研究；不能支援直接的營收預測或 2026 年即時市場機會判斷。若研究問題堅持「目前市場」或「未來收入」，現有核心資料不足，需另行收集適當資料。

## 主候選的實測結構

| 檔案／審核版本 | 行數 | 欄數 | 判定與用途 |
|---|---:|---:|---|
| FronkonGames 本地 CSV | {n('fronkon_local'):,} | 表頭 39；每行 40 | 有條件保留為替代／穩健性資料；需已核實的表頭解讀 |
| FronkonGames 本地 JSON | {n('fronkon_json'):,} | 42 欄＋AppID | 保留替代候選；精確原始版本與逐筆觀察時間未知 |
| FronkonGames HF Parquet | {n('fronkon_hf'):,} | 41 | 暫緩作主資料，tags 全空且非 CSV 的完整替代 |
| Artemiy March 2025 full | {n(pc):,} | 47 | 建議 PC 主候選；自行清理 |
| Artemiy March 2025 cleaned | {n('artem_games_march2025_cleaned'):,} | 47 | 作者清理對照，非直接當作已驗證乾淨資料 |
| Artemiy May 2024 full／cleaned | {n('artem_games_may2024_full'):,}／{n('artem_games_may2024_cleaned'):,} | 46 | 歷史穩健性候選，尚未建立縱向模型 |
| Google Play 全部 App | {n('google_all'):,} | 24 | 篩選來源，不能把全數當作遊戲 |
| Google Play 保守遊戲子集 | {n(mobile):,} | 24 | 建議 Mobile 主候選，不含 Sports |
| Sports 歧義子集 | {n('google_sports_ambiguous'):,} | 24 | 獨立保留，需額外 type/genreId 證據才納入 |

檔案 bytes、SHA-256、來源、授權、版本證據見 `dataset_inventory.csv`。CSV 用嚴格 UTF-8 解碼及 CSV parser 檢查所有記錄，不以換行數推算行數；巢狀 JSON 採串流讀取。

## Steam 格式和版本差異

**事實**：原 CSV 全部 125,855 行均有 40 個值，表頭只有 39 個名稱。`DiscountDLC count` 應拆為 `Discount`、`DLC count`，其依據為原作者目前匯出程式的欄位順序，以及本地 JSON 的 AppID 對齊比較。共檢查 {hv['checks']['scalar_comparisons']:,} 個純量值，未發現不一致。原檔未修改，只在審核讀取時提供 40 個欄名。

**事實**：本地 CSV 的 SHA-256 為 `1b48008b01a799d82385d6e66ba0cb65dd477b6aa4b6c2ec8c443025ab6880ad`，與 HF revision `{lock['hf']['FronkonGames/steam-games-dataset']['revision']}` 所列 `games.csv` 的 LFS SHA-256 相同。因此可以確認該 CSV 的位元組相同；不能由此斷言該 repository 內的 Parquet／JSON 也相同。

HF Parquet 只有 124,146 筆，全部 AppID 可在本地 CSV 找到，少了 1,709 筆。在共有記錄上，owners、price、positive、negative、release date 均一致；name 有 59 筆字串不同。兩份資料的文字及集合欄位有不同序列化方式，`aligned_value_comparison.csv` 明確區分數字、布林與字串比較，不能把所有字串差異都解讀為內容更新。

HF Parquet 的 124,146 筆 tags 全為空陣列；本地 CSV 則有 42,502 筆 tags 缺失，其餘存在標籤。HF dataset card 宣稱的 143,395 筆也不是所下載 Parquet 的行數。Repository 更新日不可等同每個檔案的採集日或同步更新日。

本地 JSON 有 141,335 筆，比 CSV 多 15,480 筆；全部 CSV AppID 均存在於 JSON。JSON 不等於該 HF revision 的遠端 JSON（雜湊及大小不同）。本地 CSV 和 JSON 都含 1 筆晚於本次審核日的 release date。這些情況要求保留版本區別及篩選紀錄，不能只使用「Steam Games Dataset」一個名稱。

## 資料品質及樣本界定

- PC 主候選 AppID 沒有重複，完整列也沒有重複。但標題有 {check(pc,'title_duplicates')['duplicate_title_excess']:,} 筆重複超額；同名不一定是同一遊戲，不能依 title 直接去重。
- March 2025 full 有 {col(pc,'genres')['empty_collection_count']:,} 筆空 genres、{col(pc,'tags')['empty_collection_count']:,} 筆空 tags。`num_reviews_total`／`pct_pos_total` 各有 39,575 筆 -1；對這些欄位，零缺失率不代表完整。
- 作者 cleaned 比 full 少 {authorclean['removed']:,} 個 AppID；其中 {authorclean['removed_title_playtest_or_demo']:,} 筆標題含 playtest/demo，{authorclean['removed_empty_genres']:,} 筆 genres 為空。這两個集合互相重疊，不能相加。兩版共有 ID 的逐欄差異已另行比較；作者所有清理決策及判定依據仍未完整取得。
- Google Play 的 Sports 同時是 App 及 Game 類別，官方文件及本地標題樣本均支持此歧義。16 個其餘遊戲標籤得到 328,513 筆；含 Sports 的寬鬆候選為 375,996 筆。這是 category-based 篩選，不是人工驗證每個產品，仍可能有錯誤分類及漏收。
- 保守手機子集中有 81 筆 Minimum Installs 缺失，6,930 筆 Rating／Rating Count 缺失，110,027 筆沒有評分支持量。免費／付費與價格、安裝標籤與下界、release/update 與 scrape 的交叉檢查已執行；不一致計數見 `cross_field_checks.json`。
- `proposed_cohort_counts.csv` 記錄逐步篩選的影響。示範規則下，March 2025 full 保留 89,450 筆；Mobile 要求已知 title、安裝下界及合理發行日期後保留 318,298 筆。這些尚非最終訓練樣本，也未保證全為正式遊戲；名稱 heuristic 及排除缺失日期需要敏感度分析。

所有 null、空白字串及文字 `nan/none/null/n/a` 在本次 profile 中視為缺失；`[]`／`{{}}` 另列 empty collection。零值不自動視為缺失。數值欄 invalid 包括不可解析、非有限、負值及指定範圍超界；無領域規則的欄位留空而非填零。`unique_nonmissing` 對列表是整個序列化值的基數，非拆解後單一 tag 的基數。

## 補充資料

| 候選 | 建議 | 原因 |
|---|---|---|
| Nik Davis Steam 2019 | 接受為歷史補充 | 27,075 筆主表，18 欄；太舊，不宜描述目前 PC 市場 |
| Game Recommendations on Steam | 接受為按需補充 | 50,872 筆產品、14,306,064 位用戶、41,154,794 筆推薦；推薦 CSV 沒有 review text，不能直接作文本情緒分析 |
| RAWG Hugging Face | 暫緩 | 已保存來源及 revision；本次只核對 metadata，未下載全量，未證明 join 品質 |
| Steam Reviews Hugging Face | 暫緩 | repository 約 23.46 GB；card 稱 1.13 億評論；本次沒有下載全量或驗證行數，後續只考慮有研究目的的固定抽樣 |

已計算部分本地資料的 AppID 重疊，見 `supplementary_join_coverage.csv`。AppID 可連接不代表可忽略時間差、產品類型、授權或欄位意義。

## 來源與認受性證據

以下為 {DATE} 保存的 Kaggle API metadata，均超過 1,000 次下載。這證明使用量指標達到背景文件提到的偏好，不代表導師正式接受或資料必定可靠。

| 資料集 | Kaggle 累計下載數 | 平台列示授權 |
|---|---:|---|
{chr(10).join(download_rows)}

HF Steam／RAWG／Steam Reviews 的近月下載數分別為 2,076／305／2,102；此期間口徑與 Kaggle 累計數不同，不能直接排名。每個 remote file 的 inventory 列重複 repository 下載數，不應加總。來源說明已保存在 `data/raw/source_metadata/{DATE}/`；下載量及平台 metadata 的保存日與原始資料採集日分開記錄。

Steam 上游為 Steam Store API／SteamSpy；Google Play 為作者從 Google Play 抓取的 2021 年截面；RAWG card 指向 RAWG API；Steam Reviews card 指向 Kaggle kieranpoc 原資料，列示 CC BY-NC 4.0。本次記錄發布者的授權聲明，未將 hosting 平台當作原始資料生產者，也未推定發布者授權可覆蓋所有第三方內容。

尚未做正式文獻檢索或逐一驗證其他研究採用情況；下載數不可替代文獻支持。Steam HF 頁面有 DOI `10.57967/hf/0511`，但 DOI 不代表所有 revision／檔案相同。

## 對研究及程式設計的影響

**建議**：將共同問題界定為「歷史同類遊戲的市場觸及與口碑基準，如何支援早期規劃」。PC 與 Mobile 共用研究及 UI 框架，但分開資料時期、target 與模型。使用者可選平台及規劃條件，查看相似產品、觀察分布、支持樣本量與限制；若模型通過評估才加入校準過的預測區間／機率。

**假說，尚未驗證**：genre、價格狀態、語言及變現狀態與表現代理指標可能有關。關聯不等於改變定價或加入 IAP 會造成業績提升。品牌、行銷預算、開發品質與曝光資源等重要因素缺失。

**主要限制**：單一截面有存活者偏差及不同上市時間的累積曝光差；Steam 部分欄位混合來源及更新時點。2021 Mobile 和 2025 PC 不能用絕對數值直接比較平台前景。以名稱排除 demo/playtest 只是可檢查的啟發式，不能保證正式發行身份。

候選 target、洩漏欄位、baseline、評估指標及群組／時間切分建議詳見 `target_feasibility.md`。未訓練任何模型，也未生成「哪種遊戲必定成功」的結論。

## 重現方法與仍待確認事項

環境及完整指令見 `Program/README.md`。依賴由 `uv.lock` 固定。原本 `Dataset/` 保持原位且只讀，以全檔 SHA-256 記錄；新增的 HF 原始下載放在 `Program/data/raw/`，審核用 Parquet 在 `data/interim/`，沒有建立 final cleaned data。DuckDB 記憶體上限設為 4 GB、2 threads，必要時寫入磁碟暫存；這不是整個 Python 程序的絕對記憶體上限。

審核所有本地 CSV；兩個 JSON 的檢查程度在 inventory 標明；ZIP 只列出成員及計算 archive 雜湊，未重複解壓並 profile 每份副本。RAWG／HF Reviews 僅 metadata。所有 row count／缺失／基數與 key 檢查皆為全檔，不是抽样推估；外部資料 card 的聲稱另行標示。

**未解決但已明確記錄**：原本 Kaggle 下載的精確版本號及日期；FronkonGames 各記錄的採集時點；Maximum Installs、0 - 0 owners 及部分零值／-1 的生成語義；作者完整清理規則；導師對雙平台及歷史資料的接受程度；最終研究問題、target、模型及應用框架。這些未知不妨礙本次審核，但會限制後續建模與最終主張。

## 來源連結

- [固定 Steam HF revision](https://huggingface.co/datasets/FronkonGames/steam-games-dataset/tree/{lock['hf']['FronkonGames/steam-games-dataset']['revision']})
- [Steam 作者匯出程式](https://github.com/FronkonGames/Steam-Games-Scraper/blob/main/ConvertToCSV.py)，本次副本另存，main URL 本身非版本固定。
- [Google Play 原作者 repository](https://github.com/gauthamp10/Google-Playstore-Dataset)
- [Google 官方 App 與 Game categories](https://support.google.com/googleplay/android-developer/answer/9859673?hl=en)
- [HF 下載數計算說明](https://huggingface.co/docs/hub/datasets-download-stats)
- [RAWG 固定 revision](https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset/tree/{lock['hf']['atalaydenknalbant/video-games-dataset']['revision']})
- [Steam Reviews 固定 revision](https://huggingface.co/datasets/adde023/steam-reviews/tree/{lock['hf']['adde023/steam-reviews']['revision']})
'''
    (REPORTS/'dataset_feasibility_report.md').write_text(report,encoding='utf-8')
    save_json(ROOT/'data/raw/existing_local_sources.json',{'audit_date':DATE,'policy':'Existing user Dataset directory stays unchanged and is read-only input. No relocation or duplication. Newly downloaded sources live under Program/data/raw.','files':[{k:v for k,v in e.items() if k in ['path','bytes','sha256']} for e in structure.values()]})
    print('Wrote five required deliverables and provenance inventory:',len(inventory),'file/version rows',flush=True)

if __name__=='__main__':main()
