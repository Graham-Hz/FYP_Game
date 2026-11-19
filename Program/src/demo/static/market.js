'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, className) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(className)node.className=className;return node;};
  const number = value => typeof value==='number' ? value.toLocaleString('en-US',{maximumFractionDigits:2}) : value===null||value===undefined ? '—' : String(value);
  let sources=[], source=null, result=null, revision=0, controller=null, optionsRevision=0, viewData=null, activeSection='overview';
  const selectedCharts=new Map();
  const filterIds=['market-group','market-tag','market-year-from','market-year-to','market-rank','market-top'];
  const sections=[
    {id:'overview',label:'市場總覽',title:'市場的供給與規模',description:'並排比較各玩法的作品數與累積數量。點選有互動提示的類型，可直接篩選該組。'},
    {id:'distribution',label:'數值分布',title:'多數遊戲落在哪個範圍？',description:'從分布、四分位數及分層比例，觀察典型作品和極端值。'},
    {id:'relationships',label:'變數關聯',title:'價格、玩法與表現有甚麼關聯？',description:'探索已觀察的變數關係；關聯不代表調整價格或玩法會造成表現改變。'},
    {id:'cohorts',label:'發售批次',title:'不同發售批次的差異',description:'每個點代表不同年份或月份發售的遊戲。這不是同一遊戲逐月銷量，也不是銷售發生時間。'},
    {id:'rankings',label:'作品排名',title:'查看樣本中的作品',description:'按所選指標排序及查看明細；估算區間重疊時，先後次序並不確定。'},
  ];
  function sectionOf(chart){
    if(sections.some(section=>section.id===chart.section))return chart.section;
    if(chart.id==='top_games')return 'rankings';
    if(chart.id?.startsWith('release_'))return 'cohorts';
    if(['group_count','group_volume_total','group_revenue_total'].includes(chart.id))return 'overview';
    if(['scatter','heatmap'].includes(chart.type)||chart.id?.startsWith('business_')||chart.id?.startsWith('price_'))return 'relationships';
    return 'distribution';
  }

  function status(message,error=false){$('market-status').textContent=message;$('market-status').dataset.error=String(error);}
  function invalidate(message='條件已更改，請按「套用條件」重新分析。'){
    revision++;if(controller)controller.abort();controller=null;result=null;viewData=null;$('market-results').hidden=true;
    $('market-export-json').disabled=true;$('market-export-csv').disabled=true;$('market-apply').disabled=!source?.available;
    $('market-results').setAttribute('aria-busy','false');if(message)status(message);
  }
  function option(select,value,label){const node=el('option',label);node.value=value;select.append(node);}
  function configureSource(id){
    source=sources.find(item=>item.id===id)||null;
    if(!source){status('沒有可供分析的資料來源。',true);return;}
    $('market-source').value=source.id;
    $('market-source-heading').textContent=source.name;
    $('market-source-snapshot').textContent=`資料時間：${source.snapshot||'未提供'} · ${source.available?'可供分析':'暫時未能讀取'}`;
    $('market-data-kind').hidden=source.data_kind!=='synthetic';
    $('market-source-description').textContent=[source.description,...(!source.available?source.limitations||[]:[])].filter(Boolean).join(' ');
    document.querySelector('.market-source-detail').open=!source.available;
    $('market-version').textContent=`資料版本：${source.version_id||'未提供'}。Steam／Android 的研究或匯入版本由「歷史分布比較」頁管理；營收樣本獨立保存。`;
    $('market-group-label').textContent=source.group_label||'玩法類型';
    $('market-group').replaceChildren();option($('market-group'),'','全部類型');(source.groups||[]).forEach(group=>option($('market-group'),group,group));
    $('market-tag').replaceChildren();option($('market-tag'),'','不限標籤');
    for(const bucket of source.tag_groups||[]){const group=el('optgroup');group.label=bucket.label;for(const value of bucket.values||[])option(group,value,value);$('market-tag').append(group);}
    $('market-tag-label').hidden=!(source.tag_groups||[]).some(bucket=>bucket.values?.length);
    $('market-rank').replaceChildren();(source.rank_metrics||[]).forEach(metric=>option($('market-rank'),metric.id,metric.label));
    ['market-year-from','market-year-to'].forEach(id=>{const node=$(id);node.value='';node.removeAttribute('min');node.removeAttribute('max');if(Number.isInteger(source.year_min))node.min=source.year_min;if(Number.isInteger(source.year_max))node.max=source.year_max;});
    $('market-top').value='10';
    filterIds.forEach(id=>$(id).disabled=!source.available);
    const years=Number.isInteger(source.year_min)&&Number.isInteger(source.year_max);
    $('market-year-from').disabled=!source.available||!years;$('market-year-to').disabled=!source.available||!years;
    $('market-filter-help').textContent=source.id==='mobile'?'按 Google Play 的遊戲類別分析。':'玩法類型與內容／發行標籤分開篩選；所選條件須同時符合。';
    $('market-apply').disabled=!source.available;$('market-reset').disabled=!source.available;
  }
  async function loadOptions(){
    const token=++optionsRevision,previous=source?.id||'pc';invalidate('正在讀取資料來源及目前啟用版本…');
    $('market-refresh').disabled=true;$('market-source').disabled=true;$('market-apply').disabled=true;$('market-reset').disabled=true;filterIds.forEach(id=>$(id).disabled=true);
    try{
      const response=await fetch('/api/market/options');const data=await response.json();if(token!==optionsRevision)return;
      if(!response.ok)throw new Error(data.error||'無法讀取來源');if(!Array.isArray(data.sources)||!data.sources.length)throw new Error('沒有可供分析的資料來源');
      sources=data.sources;$('market-source').replaceChildren();sources.forEach(item=>option($('market-source'),item.id,`${item.name}${item.available?'':'（暫不可用）'}`));
      configureSource(sources.some(item=>item.id===previous)?previous:sources[0].id);$('market-source').disabled=false;
      if(source.available)await analyze();else status(source.description||'此來源暫時不可用，請選擇另一個資料集。',true);
    }catch(error){if(token===optionsRevision)status(`無法載入分析：${error.message}。可按「重新讀取資料版本」重試。`,true);}
    finally{if(token===optionsRevision)$('market-refresh').disabled=false;}
  }
  function request(){return {source:source.id,version_id:source.version_id,group:$('market-group').value,tag:$('market-tag').value,year_from:$('market-year-from').value===''?null:Number($('market-year-from').value),year_to:$('market-year-to').value===''?null:Number($('market-year-to').value),top_n:Number($('market-top').value),rank_metric:$('market-rank').value};}
  async function analyze(){
    if(!source?.available)return;
    invalidate('正在計算目前樣本的圖表…');const token=revision,payload=request();controller=new AbortController();const signal=controller.signal;
    $('market-apply').disabled=true;$('market-results').setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/market',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal});
      const data=await response.json();if(token!==revision)return;if(!response.ok)throw new Error(data.error||'分析未完成');
      if(data.source?.id!==payload.source||data.source?.version_id!==payload.version_id)throw new Error('資料版本已改變，請重新讀取資料版本');
      render(data);result=data;$('market-export-json').disabled=false;$('market-export-csv').disabled=!(data.charts||[]).some(chart=>chart.rows?.length||chart.points?.length);
      status(data.empty?'分析完成：沒有符合條件的樣本。':`已更新分析。可切換分析方向；匯出檔包含所有圖表。`);
    }catch(error){if(token===revision&&error.name!=='AbortError'){$('market-results').hidden=true;status(`分析未完成：${error.message}`,true);}}
    finally{if(token===revision){controller=null;$('market-apply').disabled=!source?.available;$('market-results').setAttribute('aria-busy','false');}}
  }
  function table(data){
    const node=el('table'),head=el('thead'),headRow=el('tr'),body=el('tbody');
    data.columns.forEach(column=>{const th=el('th',column.label);th.scope='col';headRow.append(th);});head.append(headRow);node.append(head);
    data.rows.forEach(row=>{const tr=el('tr');data.columns.forEach(column=>{const value=row[column.key],td=el('td',Array.isArray(value)?value.join(', '):number(value));if(typeof value==='number')td.className='number';tr.append(td);});body.append(tr);});node.append(body);return node;
  }
  function clearCharts(){for(const node of $('market-charts').children)window.GameCharts.dispose?.(node);$('market-charts').replaceChildren();}
  function selectPoint(point,chart){
    const panel=$('market-point-detail');panel.replaceChildren(el('strong',point.label||point.id||'所選作品'));
    panel.append(el('span',`${chart.xLabel||'X'}：${number(point.x)} ${chart.xUnit||''} · ${chart.yLabel||'Y'}：${number(point.y)} ${chart.yUnit||chart.unit||''}`));
    if(point.id)panel.append(el('small',`ID ${point.id}`));
    const close=el('button','關閉','quiet-button');close.type='button';close.addEventListener('click',()=>panel.hidden=true);panel.append(close);panel.hidden=false;
  }
  function renderSection(sectionId){
    if(!viewData)return;
    const section=sections.find(item=>item.id===sectionId);if(!section)return;activeSection=sectionId;
    const charts=(viewData.charts||[]).filter(chart=>sectionOf(chart)===sectionId);
    for(const button of $('market-analysis-tabs').querySelectorAll('button')){const selected=button.dataset.section===sectionId;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;}
    $('market-analysis-panel').setAttribute('aria-labelledby',`market-tab-${sectionId}`);
    $('market-section-title').textContent=section.title;$('market-section-description').textContent=section.description;$('market-point-detail').hidden=true;
    const selector=$('market-chart-select');selector.replaceChildren();
    if(sectionId==='overview'&&charts.length>1)option(selector,'__overview__','總覽雙圖');
    charts.forEach(chart=>option(selector,chart.id,chart.title));
    let selected=selectedCharts.get(sectionId);if(![...selector.options].some(item=>item.value===selected))selected=selector.options[0]?.value||'';selector.value=selected;selectedCharts.set(sectionId,selected);
    $('market-chart-select-label').hidden=charts.length<2||(sectionId==='overview'&&charts.length===2);
    const shown=selected==='__overview__'?charts.slice(0,2):charts.filter(chart=>chart.id===selected);
    clearCharts();$('market-charts').classList.toggle('single-chart',shown.length===1);
    for(const chart of shown){
      const card=el('article',undefined,'market-chart');card.dataset.chartId=chart.id;card.dataset.chartType=chart.type;card.classList.toggle('chart-wide',shown.length===1||['line','scatter','heatmap','boxplot','histogram'].includes(chart.type));$('market-charts').append(card);
      const sourceCaption=`${viewData.source.name}；資料時間 ${viewData.source.snapshot||'未提供'}；版本 ${viewData.source.version_id}`;
      window.GameCharts.render(card,{...chart,...(sectionId==='overview'&&shown.length===2?{rowHeight:46,showLegend:true}:{}),source:chart.source||sourceCaption,filename:`gamescope-market-${viewData.source.id}-${String(chart.id||'chart').replace(/[^a-zA-Z0-9_-]/g,'_')}.svg`,onPointSelect:point=>selectPoint(point,chart),onSelectRow:chart.rows?.some(row=>row.filter?.group)?row=>{const group=row.filter?.group;if(typeof group==='string'&&(source.groups||[]).includes(group)){$('market-group').value=group;analyze();}}:undefined});
    }
    $('market-leaders-panel').hidden=sectionId!=='rankings'||!viewData.leaders?.rows?.length;
  }
  function renderTabs(data){
    $('market-analysis-tabs').replaceChildren();
    const available=[];
    for(const section of sections){
      const enabled=(data.charts||[]).some(chart=>sectionOf(chart)===section.id)||(section.id==='rankings'&&data.leaders?.rows?.length);
      const button=el('button',section.label);button.type='button';button.id=`market-tab-${section.id}`;button.dataset.section=section.id;button.setAttribute('role','tab');button.setAttribute('aria-controls','market-analysis-panel');button.disabled=!enabled;button.addEventListener('click',()=>renderSection(section.id));$('market-analysis-tabs').append(button);if(enabled)available.push(section.id);
    }
    $('market-analysis-tabs').hidden=!available.length;$('market-analysis-panel').hidden=!available.length;
    if(available.length)renderSection(available.includes(activeSection)?activeSection:available[0]);else clearCharts();
  }
  function render(data){
    $('market-results').hidden=false;viewData=data;
    const filter=data.filters||{},parts=[data.source.name,`類型：${filter.group||'全部'}`];
    if(filter.tag)parts.push(`標籤：${filter.tag}`);
    if(filter.year_from!==null&&filter.year_from!==undefined||filter.year_to!==null&&filter.year_to!==undefined)parts.push(`發售年份：${filter.year_from??'不限'}–${filter.year_to??'不限'}`);
    $('market-result-context').textContent=parts.join(' · ');
    $('market-summary').replaceChildren();(data.summary||[]).forEach(metric=>{const card=el('article');card.append(el('span',metric.label),el('strong',number(metric.value)));if(metric.unit)card.append(el('small',metric.unit));$('market-summary').append(card);});
    $('market-empty').hidden=!data.empty;renderTabs(data);
    const leaders=data.leaders;$('market-leaders').replaceChildren();
    if(leaders?.rows?.length&&leaders?.columns?.length){$('market-leaders-title').textContent=leaders.title||'作品排名';$('market-leaders').append(table(leaders));}
    const notes=[...(data.notes||[]),...(data.source.limitations||[])];$('market-notes').replaceChildren();[...new Set(notes)].forEach(note=>$('market-notes').append(el('li',note)));
    $('market-source-links').replaceChildren();
    for(const entry of data.provenance?.source_urls||[]){try{const raw=typeof entry==='string'?entry:entry.url,url=new URL(raw);if(!['https:','http:'].includes(url.protocol))continue;const link=el('a',typeof entry==='string'?`${url.hostname}${url.pathname}`:entry.label||entry.title||entry.name||url.hostname);link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';const item=el('li');item.append(link);$('market-source-links').append(item);}catch{/* Invalid source URLs remain in the raw evidence only. */}}
    $('market-source-links').hidden=!$('market-source-links').childElementCount;
    $('market-provenance-json').textContent=JSON.stringify({schema_version:data.schema_version,generated_at_utc:data.generated_at_utc,source:data.source,filters:data.filters,provenance:data.provenance},null,2);
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
    const header=['record_type','schema_version','source','source_version','snapshot','filters_json','generated_at_utc','chart_id','chart_type','chart_title','unit','group','series','value','x','y','lower','upper','n','outlier_count','record_json','source_caption','limitations_json','provenance_json'],rows=[header];
    function append(type,chart,record,extra={}){rows.push([type,result.schema_version,result.source.name,result.source.version_id,result.source.snapshot,JSON.stringify(result.filters),result.generated_at_utc,chart?.id,chart?.type,chart?.title,chart?.unit,extra.label,extra.series,extra.value,extra.x,extra.y,extra.lower,extra.upper,extra.n,extra.outlier_count,JSON.stringify(record),chart?.source,type==='analysis_metadata'?JSON.stringify([...(result.notes||[]),...(result.source.limitations||[])]):'',type==='analysis_metadata'?JSON.stringify(result.provenance):'']);}
    append('analysis_metadata',null,{summary:result.summary,source:result.source,filters:result.filters,provenance:result.provenance});
    for(const chart of result.charts||[]){
      const {rows:chartRows,points,outliers,...metadata}=chart;append('chart_metadata',chart,metadata);
      for(const row of chartRows||[]){
        const labels=chart.type==='boxplot'?['lower_whisker','q1','median','q3','upper_whisker']:(chart.series||[]).map(item=>item.label||item.key);
        for(let i=0;i<(row.values||[]).length;i++)append(chart.type==='histogram'?'histogram_bin':chart.type==='boxplot'?'box_summary':chart.type==='heatmap'?'heatmap_cell':'chart_value',chart,row,{label:row.label,series:labels[i]||`value_${i+1}`,value:row.values[i],lower:row.lower,upper:row.upper,n:row.n,outlier_count:row.outlier_count});
        if(!row.values?.length)append('chart_row',chart,row,{label:row.label,n:row.n});
        for(const point of row.outliers||[])append('box_outlier',chart,point,{label:row.label,value:typeof point==='number'?point:point.value??point.y});
      }
      for(const point of points||[])append('scatter_point',chart,point,{label:point.label,x:point.x,y:point.y});
      for(const point of outliers||[])append('chart_outlier',chart,point,{label:point.label,value:typeof point==='number'?point:point.value??point.y});
    }
    download('\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8',`gamescope-market-${result.source.id}-charts.csv`);
  });
  $('market-chart-select').addEventListener('change',()=>{selectedCharts.set(activeSection,$('market-chart-select').value);renderSection(activeSection);});
  $('market-analysis-tabs').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;const tabs=[...$('market-analysis-tabs').querySelectorAll('button:not(:disabled)')],index=tabs.indexOf(document.activeElement);if(index<0)return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].focus();tabs[next].click();});
  $('market-form').addEventListener('submit',event=>{event.preventDefault();analyze();});
  filterIds.forEach(id=>$(id).addEventListener('input',()=>invalidate()));
  $('market-source').addEventListener('change',()=>{invalidate();activeSection='overview';selectedCharts.clear();configureSource($('market-source').value);if(source?.available)analyze();else status(source?.description||'此來源暫不可用，請選擇另一個資料集。',true);});
  $('market-reset').addEventListener('click',()=>{invalidate();configureSource(source.id);analyze();});
  $('market-refresh').addEventListener('click',loadOptions);
  window.addEventListener('pageshow',event=>{if(event.persisted)loadOptions();});
  loadOptions();
})();
