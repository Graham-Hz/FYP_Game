'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, className) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(className)node.className=className;return node;};
  const number = value => typeof value==='number' ? value.toLocaleString('en-US',{maximumFractionDigits:2}) : value===null||value===undefined ? '—' : String(value);
  let sources=[], source=null, result=null, revision=0, controller=null, optionsRevision=0, viewData=null, activeSection='overview';
  let analysisPayload=null, recordsState=null, recordsResult=null, recordsRevision=0, recordsController=null;
  let findingSnapshot=null, findingRevision=0, findingController=null;
  let scopeState='loading';
  const selectedCharts=new Map();
  const filterIds=['market-group','market-tag','market-compare-group','market-year-from','market-year-to','market-rank','market-top'];
  const sections=[
    {id:'overview',label:'市場總覽',title:'市場的供給與規模',description:'並排比較各玩法的作品數與累積數量。點選有互動提示的類型，可直接篩選該組。'},
    {id:'distribution',label:'數值分布',title:'多數遊戲落在哪個範圍？',description:'從分布、四分位數及分層比例，觀察典型作品和極端值。'},
    {id:'relationships',label:'變數關聯',title:'價格、玩法與表現有甚麼關聯？',description:'探索已觀察的變數關係；關聯不代表調整價格或玩法會造成表現改變。'},
    {id:'cohorts',label:'發售批次',title:'不同發售批次的差異',description:'每個點代表不同年份或月份發售的遊戲。這不是同一遊戲逐月銷量，也不是銷售發生時間。'},
    {id:'rankings',label:'作品排名',title:'查看樣本中的作品',description:'按所選指標排序及查看明細；估算區間重疊時，先後次序並不確定。'},
  ];
  const hashSection=()=>{const id=location.hash.slice(1);return sections.some(item=>item.id===id)?id:null;};
  activeSection=hashSection()||activeSection;
  const readinessLabel=status=>({available:'可顯示',limited:'有資料局限',unavailable:'資料不足',pending:'待更新'}[status]||'待檢查');
  function chartStatus(chart){return chart.availability?.status||((chart.points?.length||chart.rows?.some(row=>row.values?.some(Number.isFinite)))?'available':'unavailable');}
  function syncSection(sectionId){
    updateHeading(sectionId);
    window.GameShell?.setMarketSection(sectionId);
    if(location.hash!==`#${sectionId}`)history.replaceState(null,'',`${location.pathname}${location.search}#${sectionId}`);
  }
  function updateHeading(sectionId){
    const section=sections.find(item=>item.id===sectionId);if(!section)return;
    $('market-section-title').textContent=section.title;$('market-section-description').textContent=section.description;
    document.title=`GameScope · ${section.label}`;document.body.dataset.marketView=sectionId;
    $('market-summary').hidden=sectionId!=='overview';
    updateScope(scopeState,viewData);
  }
  function updateScope(state,data=null){
    scopeState=state;
    const current=data?.source||source,filter=data?.filters||(source?request():{});
    $('market-scope-source').textContent=current?`${current.name} · ${current.snapshot||'日期未提供'}`:'正在核對資料來源…';
    $('market-data-kind').hidden=current?.data_kind!=='synthetic';
    const parts=[filter.group||'全部類型'];
    if(filter.tag)parts.push(`標籤：${filter.tag}`);
    parts.push(filter.year_from!=null||filter.year_to!=null?`發售年份 ${filter.year_from??'不限'}–${filter.year_to??'不限'}`:'不限發售年份');
    if(filter.group&&activeSection==='distribution')parts.push(`對照：${filter.compare_group||'其他遊戲'}`);
    if(activeSection==='rankings'&&filter.rank_metric){const metric=current?.rank_metrics?.find(item=>item.id===filter.rank_metric);parts.push(`${metric?.label||filter.rank_metric} · 前 ${filter.top_n||10} 項`);}
    if(state==='applied'&&data)parts.push(`樣本 ${number(data.provenance.filtered_rows)} 款`);
    $('market-result-context').textContent=parts.join(' · ');
    $('market-scope-state').textContent=({loading:'更新中',pending:'條件未套用',error:'尚未完成分析',applied:''})[state]||'';
    $('market-filter-panel').dataset.state=state;
  }
  function pendingSections(reason='請套用目前條件以檢查圖表資料。',state='pending'){
    window.GameShell?.setMarketSections(sections.map(section=>({id:section.id,status:state,reason})));
  }
  function sectionReadiness(data,section){
    const charts=sectionCharts(data,section.id),usable=charts.filter(chart=>chartStatus(chart)!=='unavailable');
    const limited=charts.filter(chart=>chartStatus(chart)==='limited'),unavailable=charts.length-usable.length;
    return {id:section.id,status:!usable.length?'unavailable':limited.length||unavailable?'limited':'available',
      reason:!usable.length?(charts[0]?.availability?.reason||'目前篩選資料未能產生這類圖表。'):`${usable.length} / ${charts.length} 張圖可顯示${limited.length?`；其中 ${limited.length} 張資料有限`:''}${unavailable?`；${unavailable} 張資料不足`:''}`,usable:usable.length,limited:limited.length,total:charts.length};
  }
  const readinessPanel=el('details',undefined,'market-readiness');readinessPanel.id='market-readiness';readinessPanel.setAttribute('aria-label','目前分析的資料檢查');
  $('market-analysis-panel').querySelector('.market-result-heading').after(readinessPanel);
  const glossary=el('details',undefined,'market-reading-guide');glossary.id='market-reading-guide';glossary.append(el('summary','圖表用語小提示'));
  glossary.append(el('p','樣本數＝這次條件下的遊戲款數（研究記錄中也寫作 n）。中位數＝排序後的中間位置；Q1–Q3＝中央 50% 的數值範圍。'));
  const sourceMeaning=el('p');sourceMeaning.id='market-metric-meaning';glossary.append(sourceMeaning);$('market-charts').after(glossary);
  function sectionOf(chart){
    if(sections.some(section=>section.id===chart.section))return chart.section;
    if(chart.id==='top_games')return 'rankings';
    if(chart.id?.startsWith('release_'))return 'cohorts';
    if(['group_count','group_volume_total','group_revenue_total'].includes(chart.id))return 'overview';
    if(['scatter','heatmap'].includes(chart.type)||chart.id?.startsWith('business_')||chart.id?.startsWith('price_'))return 'relationships';
    return 'distribution';
  }

  function status(message,error=false,quiet=false){$('market-status').textContent=message;$('market-status').dataset.error=String(error);$('market-status').classList.toggle('market-status-quiet',quiet&&!error);}
  function clearRecords(close=true){
    recordsRevision++;if(recordsController)recordsController.abort();recordsController=null;recordsResult=null;
    $('market-records-table').replaceChildren();$('market-records-table').hidden=true;$('market-records-pagination').hidden=true;
    $('market-records-panel').setAttribute('aria-busy','false');$('market-records-search-button').disabled=false;
    if(close){recordsState=null;$('market-records-panel').hidden=true;}
  }
  function invalidate(message='條件已更改，請按「套用條件」重新分析。'){
    revision++;if(controller)controller.abort();controller=null;result=null;viewData=null;analysisPayload=null;clearRecords();$('market-results').hidden=true;
    clearFinding();
    $('market-export-json').disabled=true;$('market-export-csv').disabled=true;$('market-apply').disabled=!source?.available;
    $('market-results').setAttribute('aria-busy','false');if(message)status(message);
    updateScope('pending');
    pendingSections(message);
  }
  function option(select,value,label){const node=el('option',label);node.value=value;select.append(node);}
  function configureComparison(){
    const selected=$('market-group').value,previous=$('market-compare-group').value,select=$('market-compare-group');
    select.replaceChildren();option(select,'','其他遊戲（不含所選類型）');
    (source?.groups||[]).filter(group=>group!==selected).forEach(group=>option(select,group,group));
    select.value=selected&&[...select.options].some(item=>item.value===previous)?previous:'';
    select.disabled=!source?.available||!selected;$('market-comparison-control').hidden=!selected;
  }
  function configureSource(id){
    source=sources.find(item=>item.id===id)||null;
    if(!source){status('沒有可供分析的資料來源。',true);return;}
    $('market-source').value=source.id;
    $('market-source-heading').textContent=source.name;
    $('market-source-snapshot').textContent=`資料時間：${source.snapshot||'未提供'} · ${source.available?'可供分析':'暫時未能讀取'}`;
    $('market-data-kind').hidden=source.data_kind!=='synthetic';
    $('market-source-description').textContent=[source.description,...(!source.available?source.limitations||[]:[])].filter(Boolean).join(' ');
    document.querySelector('.market-source-detail').open=!source.available;
    $('market-version').textContent=`資料版本：${source.version_id||'未提供'}。Steam／Android 的研究或匯入版本由「Step 1 比較規劃方向」管理；營收樣本獨立保存。`;
    $('market-group-label').textContent=source.group_label||'玩法類型';
    $('market-group').replaceChildren();option($('market-group'),'','全部類型');(source.groups||[]).forEach(group=>option($('market-group'),group,group));
    $('market-tag').replaceChildren();option($('market-tag'),'','不限標籤');
    for(const bucket of source.tag_groups||[]){const group=el('optgroup');group.label=bucket.label;for(const value of bucket.values||[])option(group,value,value);$('market-tag').append(group);}
    $('market-tag-label').hidden=!(source.tag_groups||[]).some(bucket=>bucket.values?.length);
    $('market-rank').replaceChildren();(source.rank_metrics||[]).forEach(metric=>option($('market-rank'),metric.id,metric.label));
    ['market-year-from','market-year-to'].forEach(id=>{const node=$(id);node.value='';node.removeAttribute('min');node.removeAttribute('max');if(Number.isInteger(source.year_min))node.min=source.year_min;if(Number.isInteger(source.year_max))node.max=source.year_max;});
    $('market-top').value='10';
    filterIds.forEach(id=>$(id).disabled=!source.available);
    $('market-compare-group').value='';configureComparison();
    const years=Number.isInteger(source.year_min)&&Number.isInteger(source.year_max);
    $('market-year-from').disabled=!source.available||!years;$('market-year-to').disabled=!source.available||!years;
    $('market-filter-help').textContent=source.id==='mobile'?'按 Google Play 的遊戲類別分析。':'玩法類型與內容／發行標籤分開篩選；所選條件須同時符合。';
    $('market-apply').disabled=!source.available;$('market-reset').disabled=!source.available;
    updateScope(source.available?'pending':'error');
  }
  async function loadOptions(){
    const token=++optionsRevision,previous=source?.id||'pc';invalidate('正在讀取資料來源及目前啟用版本…');
    updateScope('loading');
    $('market-refresh').disabled=true;$('market-source').disabled=true;$('market-apply').disabled=true;$('market-reset').disabled=true;filterIds.forEach(id=>$(id).disabled=true);
    try{
      const response=await fetch('/api/market/options');const data=await response.json();if(token!==optionsRevision)return;
      if(!response.ok)throw new Error(data.error||'無法讀取來源');if(!Array.isArray(data.sources)||!data.sources.length)throw new Error('沒有可供分析的資料來源');
      sources=data.sources;$('market-source').replaceChildren();sources.forEach(item=>option($('market-source'),item.id,`${item.name}${item.available?'':'（暫不可用）'}`));
      configureSource(sources.some(item=>item.id===previous)?previous:sources[0].id);$('market-source').disabled=false;
      if(source.available)await analyze();else {const reason=source.description||'此來源暫時不可用，請選擇另一個資料集。';status(reason,true);pendingSections(reason,'unavailable');}
    }catch(error){if(token===optionsRevision){status(`無法載入分析：${error.message}。可展開「更改條件」，按「重新讀取版本」重試。`,true);updateScope('error');$('market-filter-panel').open=true;pendingSections('資料來源未能讀取，請重新讀取版本或選擇另一個資料集。','unavailable');}}
    finally{if(token===optionsRevision)$('market-refresh').disabled=false;}
  }
  function request(){return {source:source.id,version_id:source.version_id,group:$('market-group').value,tag:$('market-tag').value,compare_group:$('market-group').value?$('market-compare-group').value:'',year_from:$('market-year-from').value===''?null:Number($('market-year-from').value),year_to:$('market-year-to').value===''?null:Number($('market-year-to').value),top_n:Number($('market-top').value),rank_metric:$('market-rank').value};}
  async function analyze(){
    if(!source?.available)return;
    invalidate('正在計算目前樣本的圖表…');const token=revision,payload=request();controller=new AbortController();const signal=controller.signal;
    updateScope('loading');
    $('market-apply').disabled=true;$('market-results').setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/market',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal});
      const data=await response.json();if(token!==revision)return;if(!response.ok)throw new Error(data.error||'分析未完成');
      if(data.source?.id!==payload.source||data.source?.version_id!==payload.version_id)throw new Error('資料版本已改變，請重新讀取資料版本');
      analysisPayload=payload;render(data);result=data;$('market-export-json').disabled=false;$('market-export-csv').disabled=!(data.charts||[]).some(chart=>chartStatus(chart)!=='unavailable'&&(chart.rows?.length||chart.points?.length));
      updateScope('applied',data);
      status(data.empty?'分析完成：沒有符合條件的樣本。':`已更新分析。匯出檔包含所有分析頁的圖表數據。`,false,!data.empty);
    }catch(error){if(token===revision&&error.name!=='AbortError'){$('market-results').hidden=true;status(`分析未完成：${error.message}`,true);updateScope('error');pendingSections('這次分析未完成，請重試或調整篩選條件。','unavailable');}}
    finally{if(token===revision){controller=null;$('market-apply').disabled=!source?.available;$('market-results').setAttribute('aria-busy','false');}}
  }
  function table(data){
    const node=el('table'),head=el('thead'),headRow=el('tr'),body=el('tbody');
    data.columns.forEach(column=>{const th=el('th',column.label);th.scope='col';headRow.append(th);});head.append(headRow);node.append(head);
    data.rows.forEach(row=>{const tr=el('tr');data.columns.forEach(column=>{const value=row[column.key],td=el('td',Array.isArray(value)?value.join(', '):number(value));if(typeof value==='number')td.className='number';tr.append(td);});body.append(tr);});node.append(body);return node;
  }
  function recordStatus(message,error=false){$('market-records-status').textContent=message;$('market-records-status').dataset.error=String(error);}
  function openRecords(cohort='selected',tier=''){
    if(!result||!analysisPayload||!['selected','baseline'].includes(cohort))return;
    if(cohort==='baseline'&&!result.comparison)return;
    clearRecords();
    const sample=result.comparison?.[cohort];
    recordsState={analysis:JSON.parse(JSON.stringify(analysisPayload)),cohort,tier,
      n:sample?.n??result.provenance.filtered_rows,label:sample?.label||result.filters.group||'全部篩選作品'};
    $('market-records-q').value='';$('market-records-sort').value='title';$('market-records-size').value='20';
    $('market-records-panel').hidden=false;$('market-records-title').textContent=`查看作品：${recordsState.label}`;
    $('market-records-context').textContent=`${result.source.name} · 資料時間 ${result.source.snapshot||'未提供'} · ${tier?'所選數量分層':'全部數量分層'}`;
    $('market-records-panel').scrollIntoView({behavior:'smooth',block:'start'});$('market-records-panel').focus({preventScroll:true});
    loadRecords(1);
  }
  async function loadRecords(page=1){
    if(!recordsState||!result)return;
    clearRecords(false);const token=recordsRevision,analysisRevision=revision,state=recordsState;
    const payload={analysis:state.analysis,cohort:state.cohort,tier:state.tier,q:$('market-records-q').value.trim(),page,page_size:Number($('market-records-size').value),sort:$('market-records-sort').value};
    recordsController=new AbortController();$('market-records-panel').setAttribute('aria-busy','true');$('market-records-search-button').disabled=true;
    recordStatus('正在讀取這組作品…');
    try{
      const response=await fetch('/api/market/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:recordsController.signal});
      const data=await response.json();if(token!==recordsRevision||analysisRevision!==revision)return;
      if(!response.ok)throw new Error(data.error||'無法讀取作品明細');
      if(data.context?.source_id!==state.analysis.source||data.context?.version_id!==state.analysis.version_id||data.context?.cohort!==state.cohort||(data.context?.tier||'')!==state.tier)throw new Error('明細的資料版本或組別不一致，請重新分析');
      if(!Array.isArray(data.columns)||!Array.isArray(data.rows)||!Number.isInteger(data.total)||!Number.isInteger(data.page)||!Number.isInteger(data.pages))throw new Error('明細格式不完整');
      recordsResult=data;
      $('market-records-context').textContent=`${result.source.name} · 資料時間 ${result.source.snapshot||'未提供'} · ${data.context.cohort_label} · ${data.context.tier_label||'全部數量分層'}`;
      $('market-records-table').replaceChildren(table(data));$('market-records-table').hidden=!data.rows.length;
      recordStatus(`符合本次分層及搜尋：${number(data.total)} 筆；這組共有 ${number(state.n)} 筆。${data.rows.length?'':'沒有符合的作品，可清除搜尋或改選分層。'}`);
      $('market-records-pagination').hidden=data.pages<1;$('market-records-page').textContent=`第 ${data.page} / ${data.pages} 頁`;
      $('market-records-prev').disabled=data.page<=1;$('market-records-next').disabled=data.page>=data.pages;
    }catch(error){if(token===recordsRevision&&analysisRevision===revision&&error.name!=='AbortError')recordStatus(`無法讀取明細：${error.message}`,true);}
    finally{if(token===recordsRevision&&analysisRevision===revision){recordsController=null;$('market-records-panel').setAttribute('aria-busy','false');$('market-records-search-button').disabled=false;}}
  }
  function comparisonDetails(comparison,visible){
    const panel=$('market-comparison');panel.hidden=!comparison||!visible;if(!comparison||!visible)return;
    $('market-comparison-context').textContent=`上方概況只計所選組；此處另列對照組。兩組共有 ${number(comparison.overlap_count)} 款重疊作品。`;
    const host=$('market-comparison-cohorts');host.replaceChildren();
    const labels=viewData.source.id==='pc'?{volume_lower:'估計擁有者下限',volume_upper:'估計擁有者上限'}:
      viewData.source.id==='mobile'?{volume_lower:'最低安裝量'}:{volume_lower:'估計售出份數',revenue:'估計總營收（USD）'};
    for(const key of ['selected','baseline']){
      const sample=comparison[key],card=el('article',undefined,'market-cohort-card');card.dataset.cohort=key;
      const knownLabel=viewData.source.id==='revenue'?'已知估計營收':'已知數量分層';
      card.append(el('h4',`${key==='selected'?'所選組':'對照組'}：${sample.label}`),el('p',`樣本 ${number(sample.n)} 款 · ${knownLabel} ${number(sample.known_outcome_rows)} 款${sample.unknown_outcome_rows?` · 未知 ${number(sample.unknown_outcome_rows)} 款`:''}`));
      const list=el('dl');
      for(const [metric,label] of Object.entries(labels)){
        const value=sample.statistics?.[metric];if(!value)continue;
        const description=el('dd');description.append(el('strong',`中位數 ${number(value.median)}`),el('small',`中央 50%（Q1–Q3）：${number(value.q1)}–${number(value.q3)}；此數值有資料的遊戲：${number(value.n)} 款`));list.append(el('dt',label),description);
      }
      card.append(list);const button=el('button','查看這組作品','outline');button.type='button';button.dataset.recordsCohort=key;button.disabled=!sample.n;button.addEventListener('click',()=>openRecords(key));card.append(button);host.append(card);
    }
    $('market-comparison-notes').replaceChildren();
    const baseline=typeof comparison.baseline_definition==='string'?comparison.baseline_definition:JSON.stringify(comparison.baseline_definition);
    [baseline,...(comparison.notes||[])].filter(Boolean).forEach(note=>$('market-comparison-notes').append(el('li',note)));
  }
  function sectionCharts(data,sectionId){
    const charts=(data.charts||[]).filter(chart=>sectionOf(chart)===sectionId);
    if(sectionId==='distribution'){
      if(data.comparison?.chart)return [data.comparison.chart,...charts];
      const preferred=data.source.id==='revenue'?charts.find(chart=>chart.type==='histogram'):charts.find(chart=>chart.id==='outcome_tiers');
      if(preferred)return [preferred,...charts.filter(chart=>chart!==preferred)];
    }
    return charts;
  }
  function chartRowSelected(row){
    if(row.cohort){openRecords(row.cohort);return;}
    if(typeof row.filter?.tier==='string'){openRecords('selected',row.filter.tier);return;}
    const group=row.filter?.group;
    if(typeof group==='string'&&(source.groups||[]).includes(group)){
      $('market-group').value=group;configureComparison();activeSection='distribution';selectedCharts.delete('distribution');analyze();
    }
  }
  function clearCharts(){for(const node of $('market-charts').children)window.GameCharts.dispose?.(node);$('market-charts').replaceChildren();}
  function selectPoint(point,chart){
    const panel=$('market-point-detail');panel.replaceChildren(el('strong',point.label||point.id||'所選作品'));
    panel.append(el('span',`${chart.xLabel||'X'}：${number(point.x)} ${chart.xUnit||''} · ${chart.yLabel||'Y'}：${number(point.y)} ${chart.yUnit||chart.unit||''}`));
    if(point.id)panel.append(el('small',`ID ${point.id}`));
    const close=el('button','關閉','quiet-button');close.type='button';close.addEventListener('click',()=>panel.hidden=true);panel.append(close);panel.hidden=false;
  }
  function findingStatus(message,error=false){$('market-finding-status').textContent=message;$('market-finding-status').dataset.error=String(error);}
  function clearFinding(){
    findingRevision++;findingController?.abort();findingController=null;findingSnapshot=null;
    $('market-finding-capture').hidden=true;$('market-finding-form').hidden=true;
    $('market-finding-save').disabled=false;$('market-finding-open').disabled=false;
    $('market-finding-capture').setAttribute('aria-busy','false');findingStatus('');
  }
  function compactChart(chart){
    const {rows=[],points=[],outliers=[],...metadata}=chart;
    return {...metadata,rows:rows.slice(0,40).map(row=>{const {outliers:ignored,...values}=row;return values;}),
      row_count:rows.length,rows_saved:Math.min(rows.length,40),rows_truncated:rows.length>40,
      point_count:points.length,points_omitted:points.length>0,
      outlier_points_omitted:outliers.length>0||rows.some(row=>row.outliers?.length),
      evidence_scope:'aggregate_rows_up_to_40_without_scatter_or_outlier_points'};
  }
  function configureFinding(data,charts){
    clearFinding();charts=charts.filter(chart=>chartStatus(chart)!=='unavailable');if(data.empty||!charts.length)return;
    const {chart:comparisonChart,...comparison}=data.comparison||{};
    const {id,name,version_id,snapshot,data_kind,description,limitations}=data.source;
    findingSnapshot=JSON.parse(JSON.stringify({schema_version:'market_finding_v1',analysis_schema_version:data.schema_version,generated_at_utc:data.generated_at_utc,
      source:{id,name,version_id,snapshot,data_kind,description,limitations},filters:data.filters,
      summary:data.summary,comparison:data.comparison?comparison:null,charts:charts.map(compactChart),
      provenance:data.provenance,notes:data.notes||[]}));
    $('market-finding-capture').hidden=false;
    $('market-finding-context').textContent=`目前觀察：${charts.map(chart=>chart.title).join('、')} · ${data.source.name} · ${data.filters.group||'全部類型'}`;
    $('market-finding-title').value=`${data.source.name} · ${data.filters.group||'全部類型'} · ${charts.length===1?charts[0].title:'市場總覽'}`.slice(0,120);
    $('market-finding-note').value='';
  }
  function renderFindings(message=''){
    const saved=window.PlanningFlow.findings();
    $('market-findings-count').textContent=saved.error?'— / 5':`${saved.items.length} / 5`;
    $('market-findings-status').textContent=saved.error||message||(!saved.items.length?'尚未保存分析發現。檢視圖表後，可用「保存分析發現」加入這裡。':'');
    $('market-findings-status').dataset.error=String(!!saved.error);
    const list=$('market-findings-list');list.replaceChildren();
    for(const item of saved.items){
      const card=el('article',undefined,'market-finding-item');card.dataset.findingId=item.id;
      card.append(el('h3',item.title),el('p',`${item.source.name} · ${item.source.snapshot||'未提供日期'} · ${item.filters.group||'全部類型'}`,'fine'));
      card.append(el('p',item.note||'尚未填寫個人解讀。','market-finding-note'));
      const remove=el('button','移除','quiet-button');remove.type='button';remove.dataset.findingRemove=item.id;
      remove.setAttribute('aria-label',`移除分析發現：${item.title}`);
      remove.addEventListener('click',()=>{
        const outcome=window.PlanningFlow.removeFinding(item.id);renderFindings(outcome.ok?'已移除這項分析發現。':outcome.error||'未能移除，請重試。');
        if(!outcome.ok)$('market-findings-status').dataset.error='true';
      });
      card.append(remove);list.append(card);
    }
  }
  async function saveFinding(){
    if(!findingSnapshot||!result||!$('market-finding-form').reportValidity())return;
    const title=$('market-finding-title').value.trim(),note=$('market-finding-note').value.trim();
    if(!title){findingStatus('請填寫發現標題。',true);$('market-finding-title').focus();return;}
    const snapshot=findingSnapshot,token=++findingRevision,analysisRevision=revision;
    findingController?.abort();findingController=new AbortController();
    $('market-finding-save').disabled=true;$('market-finding-open').disabled=true;$('market-finding-capture').setAttribute('aria-busy','true');
    findingStatus('正在核對資料版本並保存…');
    try{
      const response=await fetch('/api/market/options',{signal:findingController.signal});
      const data=await response.json();if(token!==findingRevision||analysisRevision!==revision)return;
      if(!response.ok||!Array.isArray(data.sources))throw new Error(data.error||'無法核對資料版本');
      const current=data.sources.find(item=>item.id===snapshot.source.id);
      const canonical=value=>JSON.stringify(Object.keys(value||{}).sort().map(key=>[key,value[key]]));
      if(!current?.available||current.version_id!==snapshot.source.version_id||
          current.analysis_schema_version!==snapshot.analysis_schema_version||
          current.taxonomy_version!==snapshot.provenance?.label_taxonomy?.version||
          canonical(current.input_hashes)!==canonical(snapshot.provenance?.input_hashes)||
          snapshot.comparison&&current.comparison_method_version!==snapshot.comparison.method_version){
        invalidate('資料來源或啟用版本已改變，尚未保存這項發現。請按「重新讀取版本」後重新分析。');return;
      }
      const saved=window.PlanningFlow.addFinding({...snapshot,title,note});
      if(!saved.ok){findingStatus(saved.error||'未能保存分析發現，請重試。',true);renderFindings();return;}
      $('market-finding-form').hidden=true;findingStatus('已保存，可在「規劃摘要」連同其他觀察及預算一起檢視。');
      renderFindings('已加入新的分析發現。');
    }catch(error){if(token===findingRevision&&analysisRevision===revision&&error.name!=='AbortError')findingStatus(`尚未保存：${error.message}`,true);}
    finally{if(token===findingRevision&&analysisRevision===revision){findingController=null;$('market-finding-save').disabled=false;$('market-finding-open').disabled=false;$('market-finding-capture').setAttribute('aria-busy','false');}}
  }
  function renderSection(sectionId){
    const section=sections.find(item=>item.id===sectionId);if(!section)return;activeSection=sectionId;
    syncSection(sectionId);
    if(!viewData)return;
    const charts=sectionCharts(viewData,sectionId);
    for(const button of $('market-analysis-tabs').querySelectorAll('button')){const selected=button.dataset.section===sectionId;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;}
    $('market-analysis-panel').setAttribute('aria-labelledby','market-section-title');
    $('market-section-title').textContent=section.title;$('market-section-description').textContent=section.description;$('market-point-detail').hidden=true;
    const selector=$('market-chart-select');selector.replaceChildren();
    if(sectionId==='overview'&&charts.length>1)option(selector,'__overview__','總覽雙圖');
    charts.forEach(chart=>option(selector,chart.id,`${chart.title}${chartStatus(chart)==='available'?'':`（${readinessLabel(chartStatus(chart))}）`}`));
    let selected=selectedCharts.get(sectionId);if(![...selector.options].some(item=>item.value===selected))selected=selector.options[0]?.value||'';selector.value=selected;selectedCharts.set(sectionId,selected);
    $('market-chart-select-label').hidden=charts.length<2||(sectionId==='overview'&&charts.length===2);
    const shown=selected==='__overview__'?charts.slice(0,2):charts.filter(chart=>chart.id===selected);
    const readiness=sectionReadiness(viewData,section);readinessPanel.dataset.status=readiness.status;
    readinessPanel.replaceChildren(el('summary',`資料檢查：${readiness.usable} / ${readiness.total} 張圖可顯示${readiness.status==='available'?'':` · ${readinessLabel(readiness.status)}`}`),el('p',readiness.reason));
    readinessPanel.open=readiness.status==='unavailable';
    if(!charts.length)readinessPanel.append(el('p','你可以放寬篩選條件，或選擇含有所需數值的資料版本。'));
    configureFinding(viewData,shown);
    comparisonDetails(viewData.comparison,shown.some(chart=>chart.id===viewData.comparison?.chart?.id));
    clearCharts();$('market-charts').classList.toggle('single-chart',shown.length===1);
    for(const chart of shown){
      const card=el('article',undefined,'market-chart');card.dataset.chartId=chart.id;card.dataset.chartType=chart.type;card.classList.toggle('chart-wide',shown.length===1||['line','scatter','heatmap','boxplot','histogram'].includes(chart.type));$('market-charts').append(card);
      const sourceCaption=`${viewData.source.name}；資料時間 ${viewData.source.snapshot||'未提供'}；版本 ${viewData.source.version_id}`;
      window.GameCharts.render(card,{...chart,compactReadiness:true,...(sectionId==='overview'&&shown.length===2?{rowHeight:46,showLegend:true}:{}),source:chart.source||sourceCaption,filename:`gamescope-market-${viewData.source.id}-${String(chart.id||'chart').replace(/[^a-zA-Z0-9_-]/g,'_')}.svg`,onPointSelect:point=>selectPoint(point,chart),onSelectRow:chart.rows?.some(row=>row.filter?.group||row.filter?.tier||row.cohort)?chartRowSelected:undefined,onSelectSegment:chart.type==='stacked_bar'?({row,series})=>openRecords(row.cohort||'selected',series.key):undefined});
    }
    $('market-leaders-panel').hidden=sectionId!=='rankings'||!viewData.leaders?.rows?.length;
  }
  function renderTabs(data){
    $('market-analysis-tabs').replaceChildren();
    const availability=[];
    for(const section of sections){
      const readiness=sectionReadiness(data,section);availability.push(readiness);
      const button=el('button',section.label);button.type='button';button.id=`market-tab-${section.id}`;button.dataset.section=section.id;button.setAttribute('role','tab');button.setAttribute('aria-controls','market-analysis-panel');button.addEventListener('click',()=>{location.hash=section.id;renderSection(section.id);});$('market-analysis-tabs').append(button);
    }
    window.GameShell?.setMarketSections(availability);
    $('market-analysis-tabs').hidden=!!window.GameShell;$('market-analysis-panel').hidden=false;
    renderSection(activeSection);
  }
  function render(data){
    $('market-results').hidden=false;viewData=data;
    updateScope('applied',data);
    $('market-view-records').disabled=!!data.empty;
    $('market-summary').replaceChildren();(data.summary||[]).forEach(metric=>{const card=el('article');card.append(el('span',metric.label.replace(/owners/gi,'擁有者')),el('strong',number(metric.value)));if(metric.unit)card.append(el('small',metric.unit));$('market-summary').append(card);});
    $('market-metric-meaning').textContent=data.source.id==='pc'?'擁有者（owners）是來源估計的帳戶數區間，不是精確購買量；同一款遊戲可屬多個玩法，分組總和可能重複計入。':data.source.id==='mobile'?'最低安裝量是來源公布的安裝數下限，不是精確下載量；例如 1,000 表示至少達到這個數量。':'營收與售出份數是來源估計的累積值。這是經挑選的 Steam 樣本，不能代表所有新遊戲的預期收入。';
    $('market-empty').hidden=!data.empty;renderTabs(data);
    const leaders=data.leaders;$('market-leaders').replaceChildren();
    if(leaders?.rows?.length&&leaders?.columns?.length){$('market-leaders-title').textContent=leaders.title||'作品排名';$('market-leaders').append(table(leaders));}
    const notes=[...(data.notes||[]),...(data.source.limitations||[])];$('market-notes').replaceChildren();[...new Set(notes)].forEach(note=>$('market-notes').append(el('li',note)));
    $('market-source-links').replaceChildren();
    for(const entry of data.provenance?.source_urls||[]){try{const raw=typeof entry==='string'?entry:entry.url,url=new URL(raw);if(!['https:','http:'].includes(url.protocol))continue;const link=el('a',typeof entry==='string'?`${url.hostname}${url.pathname}`:entry.label||entry.title||entry.name||url.hostname);link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';const item=el('li');item.append(link);$('market-source-links').append(item);}catch{/* Invalid source URLs remain in the raw evidence only. */}}
    $('market-source-links').hidden=!$('market-source-links').childElementCount;
    $('market-provenance-json').textContent=JSON.stringify({schema_version:data.schema_version,generated_at_utc:data.generated_at_utc,source:data.source,filters:data.filters,provenance:data.provenance,comparison:data.comparison||null},null,2);
    $('market-results').hidden=false;
  }
  function download(body,type,filename){const url=URL.createObjectURL(new Blob([body],{type})),link=el('a');link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function csvCell(value){
    if(value===null||value===undefined)return '""';
    let text=String(value);if(typeof value!=='number'&&/^[\s]*[=+\-@\t\r\n]/.test(text))text="'"+text;
    return `"${text.replace(/"/g,'""')}"`;
  }
  $('market-export-json').addEventListener('click',()=>{if(result)download(JSON.stringify({...result,exported_at_utc:new Date().toISOString()},null,2),'application/json',`gamescope-market-${result.source.id}.json`);});
  $('market-export-csv').addEventListener('click',()=>{
    if(!result)return;
    const header=['record_type','schema_version','source','source_version','snapshot','filters_json','generated_at_utc','chart_id','chart_type','chart_title','unit','group','series','value','x','y','lower','upper','n','outlier_count','record_json','source_caption','limitations_json','provenance_json','cohort','cohort_n','known_outcome_rows','unknown_outcome_rows'],rows=[header];
    function append(type,chart,record,extra={}){rows.push([type,result.schema_version,result.source.name,result.source.version_id,result.source.snapshot,JSON.stringify(result.filters),result.generated_at_utc,chart?.id,chart?.type,chart?.title,chart?.unit,extra.label,extra.series,extra.value,extra.x,extra.y,extra.lower,extra.upper,extra.n,extra.outlier_count,JSON.stringify(record),chart?.source,type==='analysis_metadata'?JSON.stringify([...(result.notes||[]),...(result.source.limitations||[])]):extra.notes?JSON.stringify(extra.notes):'',extra.provenance?JSON.stringify(extra.provenance):type==='analysis_metadata'?JSON.stringify(result.provenance):'',extra.cohort,extra.cohort_n,extra.known_outcome_rows,extra.unknown_outcome_rows]);}
    append('analysis_metadata',null,{summary:result.summary,source:result.source,filters:result.filters,provenance:result.provenance});
    for(const chart of result.charts||[]){
      const {rows:chartRows,points,outliers,...metadata}=chart;append('chart_metadata',chart,metadata);
      if(chartStatus(chart)==='unavailable')continue;
      for(const row of chartRows||[]){
        const labels=chart.type==='boxplot'?['lower_whisker','q1','median','q3','upper_whisker']:(chart.series||[]).map(item=>item.label||item.key);
        for(let i=0;i<(row.values||[]).length;i++)append(chart.type==='histogram'?'histogram_bin':chart.type==='boxplot'?'box_summary':chart.type==='heatmap'?'heatmap_cell':'chart_value',chart,row,{label:row.label,series:labels[i]||`value_${i+1}`,value:row.values[i],lower:row.lower,upper:row.upper,n:row.n,outlier_count:row.outlier_count});
        if(!row.values?.length)append('chart_row',chart,row,{label:row.label,n:row.n});
        for(const point of row.outliers||[])append('box_outlier',chart,point,{label:row.label,value:typeof point==='number'?point:point.value??point.y});
      }
      for(const point of points||[])append('scatter_point',chart,point,{label:point.label,x:point.x,y:point.y});
      for(const point of outliers||[])append('chart_outlier',chart,point,{label:point.label,value:typeof point==='number'?point:point.value??point.y});
    }
    if(result.comparison){
      const comparison=result.comparison,chart=comparison.chart;
      const provenance={source_id:result.source.id,version_id:result.source.version_id,source_urls:result.provenance.source_urls,input_hashes:result.provenance.input_hashes,analysis_filters:result.filters,method_version:comparison.method_version,baseline_definition:comparison.baseline_definition,overlap_count:comparison.overlap_count};
      append('comparison_metadata',chart,comparison,{provenance,notes:comparison.notes});
      for(const cohort of ['selected','baseline']){
        const sample=comparison[cohort],context={label:sample.label,n:sample.n,cohort,cohort_n:sample.n,known_outcome_rows:sample.known_outcome_rows,unknown_outcome_rows:sample.unknown_outcome_rows,provenance:{...provenance,cohort,cohort_label:sample.label,cohort_n:sample.n},notes:comparison.notes};
        append('comparison_cohort',chart,sample,context);
        for(const [metric,statistics] of Object.entries(sample.statistics||{})){
          const metricChart={id:`comparison_${metric}`,type:'summary',title:`兩組 ${metric} 四分位數`,unit:metric==='revenue'?'USD':result.source.id==='mobile'?'最低安裝量':result.source.id==='revenue'?'估計售出份數':`估計擁有者${metric==='volume_upper'?'上限':'下限'}`,source:chart?.source};
          for(const statistic of ['q1','median','q3'])append('comparison_statistic',metricChart,{metric,statistic,value:statistics[statistic],valid_n:statistics.n},{...context,n:statistics.n,series:statistic,value:statistics[statistic]});
        }
        for(const tier of sample.tiers||[])append('comparison_tier',chart,tier,{...context,series:tier.id,value:tier.percent});
      }
    }
    download('\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8',`gamescope-market-${result.source.id}-charts.csv`);
  });
  $('market-chart-select').addEventListener('change',()=>{selectedCharts.set(activeSection,$('market-chart-select').value);renderSection(activeSection);});
  $('market-analysis-tabs').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;const tabs=[...$('market-analysis-tabs').querySelectorAll('button:not(:disabled)')],index=tabs.indexOf(document.activeElement);if(index<0)return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].focus();tabs[next].click();});
  $('market-form').addEventListener('submit',event=>{event.preventDefault();analyze();});
  filterIds.forEach(id=>$(id).addEventListener('input',()=>{if(id==='market-group'){configureComparison();selectedCharts.delete('distribution');activeSection=$('market-group').value?'distribution':activeSection;}if(id==='market-compare-group'){selectedCharts.delete('distribution');activeSection='distribution';}invalidate();}));
  $('market-source').addEventListener('change',()=>{invalidate();activeSection='overview';syncSection(activeSection);selectedCharts.clear();configureSource($('market-source').value);if(source?.available)analyze();else {const reason=source?.description||'此來源暫不可用，請選擇另一個資料集。';status(reason,true);pendingSections(reason,'unavailable');}});
  $('market-reset').addEventListener('click',()=>{invalidate();activeSection='overview';selectedCharts.clear();configureSource(source.id);analyze();});
  $('market-view-records').addEventListener('click',()=>openRecords());
  $('market-records-close').addEventListener('click',()=>{clearRecords();$('market-view-records').focus();});
  $('market-records-form').addEventListener('submit',event=>{event.preventDefault();loadRecords(1);});
  $('market-records-q').addEventListener('input',()=>{clearRecords(false);recordStatus('搜尋條件已更改，請按「搜尋」更新作品清單。');});
  ['market-records-sort','market-records-size'].forEach(id=>$(id).addEventListener('change',()=>loadRecords(1)));
  $('market-records-prev').addEventListener('click',()=>{if(recordsResult?.page>1)loadRecords(recordsResult.page-1);});
  $('market-records-next').addEventListener('click',()=>{if(recordsResult&&recordsResult.page<recordsResult.pages)loadRecords(recordsResult.page+1);});
  $('market-refresh').addEventListener('click',loadOptions);
  $('market-finding-open').addEventListener('click',()=>{if(findingSnapshot){$('market-finding-form').hidden=false;findingStatus('');$('market-finding-title').focus();}});
  $('market-finding-cancel').addEventListener('click',()=>{$('market-finding-form').hidden=true;findingStatus('');$('market-finding-open').focus();});
  $('market-finding-form').addEventListener('submit',event=>{event.preventDefault();saveFinding();});
  window.addEventListener('pageshow',event=>{if(event.persisted)loadOptions();});
  window.addEventListener('hashchange',()=>{const section=hashSection();if(!section)return;renderSection(section);});
  syncSection(activeSection);
  renderFindings();
  loadOptions();
})();
