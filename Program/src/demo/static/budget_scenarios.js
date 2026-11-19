/* Saved budget alternatives reuse server calculations; no cost model is fitted here. */
window.BudgetScenarios = (() => {
  'use strict';
  const METHODS = new Set(['budget_scenario_v1', 'budget_scenario_v2']);
  const COMPONENTS = {team_cash:'人力現金',overhead:'每月其他開支',outsourcing:'外包／素材',marketing:'行銷',other_one_off:'其他一次性',reference_fees:'選用工具／平台／設備費',contingency:'備用金'};
  const INPUTS = {currency:'幣別',months:'開發期（月）',monthly_overhead:'每月其他現金支出',outsourcing:'一次性外包／素材',marketing:'一次性行銷',other_one_off:'其他一次性支出',contingency_percent:'備用金 (%)',available_funds:'可投入資金',net_unit_contribution:'每份銷售淨貢獻'};
  const TEAM = {label:'人員／職能',people:'人數',allocation:'投入比例',monthly_cash:'每人每月現金成本',monthly_unpaid:'每人每月額外未付勞動估值'};
  const FEE = {quantity:'數量',fx_rate:'換算率',target_currency:'計劃幣別',eligibility_confirmed:'資格確認',billing_assumption:'付款假設'};
  const clone = value => JSON.parse(JSON.stringify(value));
  const el = (tag,text,cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
  const fmt = value => Number.isFinite(value)?value.toLocaleString('en-US',{maximumFractionDigits:2}):'未提供';
  const signed = value => Number.isFinite(value)?`${value>0?'+':''}${fmt(value)}`:'未計算';
  const present = value => value===null||value===undefined?'未提供':typeof value==='boolean'?(value?'已確認':'未確認'):typeof value==='number'?fmt(value):String(value);
  let config=null, feeMetadata=null;

  function flatInputs(snapshot) {
    const request=snapshot.budget.request, values={};
    for(const [key,label] of Object.entries(INPUTS))values[key]={label,value:request[key]??null};
    (request.team||[]).forEach((row,index)=>{for(const [key,label] of Object.entries(TEAM))values[`team.${index}.${key}`]={label:`人員組 ${index+1} · ${label}`,value:row[key]??null};});
    const selected=snapshot.budget.fee_reference?.selections||[];
    for(const item of request.fee_selection?.items||[]){
      const reference=selected.find(entry=>entry.fee_id===item.fee_id)?.reference;
      const name=reference?`${reference.product} · ${reference.plan}`:item.fee_id;
      values[`fee.${item.fee_id}.selected`]={label:`參考費用 · ${name}`,value:'已選用'};
      for(const [key,label] of Object.entries(FEE))values[`fee.${item.fee_id}.${key}`]={label:`${name} · ${label}`,value:item[key]??null};
    }
    return values;
  }
  function difference(key,label,unit,a,b) {return {key,label,unit,a:a??null,b:b??null,delta:Number.isFinite(a)&&Number.isFinite(b)?Math.round((b-a)*100)/100:null};}
  function compare(slots, {feeMetadata=null,currentContextId=null}={}) {
    slots=slots||{};
    const issues=[],missing=[],context_notes=[];
    for(const key of ['a','b']){
      const saved=slots[key];
      if(!saved){missing.push(key.toUpperCase());continue;}
      const budget=saved.budget;
      if(!budget?.request||!budget.base||!Array.isArray(budget.delays)||!budget.currency){issues.push(`方案 ${key.toUpperCase()} 的預算格式不完整，請重新計算及保存。`);continue;}
      if(!METHODS.has(budget.method_version))issues.push(`方案 ${key.toUpperCase()} 的計算方法不受目前版本支援，請重新計算及保存。`);
      if(budget.fee_reference && (!feeMetadata || budget.fee_reference.metadata?.revision!==feeMetadata.revision))issues.push(`方案 ${key.toUpperCase()} 的費用來源版本未能通過核對，請重新選用費用、計算及保存。`);
      if(currentContextId&&saved.context_id&&saved.context_id!==currentContextId)context_notes.push(`方案 ${key.toUpperCase()} 來自另一個規劃情境；此處只比較資源假設，不會取代目前規劃的預算。`);
    }
    const a=slots.a?.budget,b=slots.b?.budget;
    if(a?.currency&&b?.currency&&a.currency!==b.currency)issues.push(`兩個方案幣別不同（${a.currency}／${b.currency}），不能直接相減或繪在同一金額軸上。請使用同一幣別重新計算。`);
    const result={schema_version:'budget_alternative_comparison_v1',ready:!missing.length&&!issues.length,issues,missing,currency:a?.currency===b?.currency?a?.currency:null,metrics:[],components:[],delays:[],inputs:[],context_notes};
    if(!a?.request||!b?.request)return result;
    const av=flatInputs(slots.a),bv=flatInputs(slots.b);
    for(const key of new Set([...Object.keys(av),...Object.keys(bv)]))if(JSON.stringify(av[key]?.value??null)!==JSON.stringify(bv[key]?.value??null))result.inputs.push({key,label:av[key]?.label||bv[key].label,a:av[key]?.value??null,b:bv[key]?.value??null});
    if(!result.ready)return result;
    for(const [key,label,unit] of [['months','原定工期','月'],['cash_budget','現金預算',a.currency],['unpaid_labour_value','額外未付勞動估值',a.currency],['resource_budget','含勞動估值總投入',a.currency],['funding_balance','資金餘額／不足',a.currency],['cash_break_even_units','覆蓋現金成本的銷售要求','份'],['resource_break_even_units','含勞動估值的銷售要求','份']])result.metrics.push(difference(key,label,unit,a.base[key],b.base[key]));
    for(const key of Object.keys(COMPONENTS))result.components.push(difference(key,COMPONENTS[key],a.currency,a.base.components[key]??0,b.base.components[key]??0));
    for(const offset of [0,3,6]){
      const ar=a.delays.find(row=>row.months===a.base.months+offset),br=b.delays.find(row=>row.months===b.base.months+offset);
      result.delays.push({...difference(String(offset),offset?`延長 ${offset} 個月`:'原定工期',a.currency,ar?.cash_budget,br?.cash_budget),a_months:ar?.months??null,b_months:br?.months??null});
    }
    return result;
  }
  function table(headers,rows,caption) {
    const scroll=el('div',undefined,'scenario-table-scroll');scroll.tabIndex=0;scroll.setAttribute('aria-label',caption);
    const t=el('table'),head=el('thead'),tr=el('tr');for(const label of headers){const th=el('th',label);th.scope='col';tr.append(th);}head.append(tr);t.append(head);
    const body=el('tbody');for(const row of rows){const tr=el('tr');row.forEach((value,index)=>{const td=el(index?'td':'th',value);if(!index)td.scope='row';tr.append(td);});body.append(tr);}t.append(body);scroll.append(t);const wrapper=el('div');wrapper.append(el('p','窄螢幕可左右捲動比較表。','scenario-table-hint'),scroll);return wrapper;
  }
  function dispose(host){host.querySelectorAll('.scenario-chart').forEach(node=>window.GameCharts?.dispose(node));}
  function renderInto(host,slots,options={}) {
    if(typeof host==='string')host=document.getElementById(host);
    const comparison=compare(slots,options);if(!host)return comparison;
    dispose(host);host.replaceChildren();host.classList.add('budget-scenarios-view');
    const cards=el('div',undefined,'saved-scenario-cards');
    for(const key of ['a','b']){
      const saved=slots?.[key],card=el('article',undefined,'saved-scenario-card');card.dataset.scenario=key;
      card.append(el('h3',`${key.toUpperCase()} · ${saved?.name||'尚未保存'}`));
      if(saved?.budget?.base){
        const b=saved.budget;
        card.append(el('strong',`${b.currency} ${fmt(b.base.cash_budget)}`,'saved-scenario-amount'),el('p',`${b.base.months} 個月 · 現金預算（含備用金）`));
        const scope=saved.platform==='pc'?'Steam 規劃':saved.platform==='mobile'?'Android 規劃':'獨立預算';
        const time=new Date(saved.saved_at_utc);card.append(el('p',`${scope} · 保存於 ${Number.isNaN(time.getTime())?saved.saved_at_utc:time.toLocaleString('zh-HK')}`,'fine'));
        const d=el('details');d.append(el('summary','查看這個方案的假設及來源'),el('p',`計算方法：${b.method_version}；費用來源版本：${b.fee_reference?.metadata?.revision||'未選用參考費用'}`),el('pre',JSON.stringify({request:b.request,fee_reference:b.fee_reference,assumptions:b.assumptions},null,2)));card.append(d);
      }else card.append(el('p','計算目前輸入後，可把結果保存為此方案。'));
      cards.append(card);
    }
    host.append(cards);
    if(comparison.missing.length)host.append(el('p',`保存方案 ${comparison.missing.map(key=>key.toUpperCase()).join('、')} 後，便可比較兩個方案。`,'fine'));
    for(const issue of comparison.issues)host.append(el('p',issue,'sample-warning'));
    for(const note of comparison.context_notes)host.append(el('p',note,'fine'));
    if(comparison.ready){
      host.append(el('h3','兩個方案相差多少？'),el('p','差額一律為 B 減 A。這是不同假設的資源要求，不會自動判定哪個方案較好。','fine'));
      host.append(table(['項目','方案 A','方案 B','差額 B − A'],comparison.metrics.map(row=>[`${row.label} (${row.unit})`,fmt(row.a),fmt(row.b),signed(row.delta)]),'兩個成本方案的輸出比較'));
      const source=`來源：兩個已保存的使用者預算；A ${slots.a.name}，${slots.a.budget.method_version}，${slots.a.saved_at_utc}；B ${slots.b.name}，${slots.b.budget.method_version}，${slots.b.saved_at_utc}。完整假設、費用與來源保留於方案 JSON。`;
      const charts=el('div',undefined,'scenario-comparison-charts');host.append(charts);
      for(const [kind,title,description,rows] of [
        ['components','成本組成比較','每項均採用已保存的計算結果；未付勞動估值另列。',comparison.components.map(row=>({label:row.label,values:[row.a,row.b]}))],
        ['delays','延期下的現金要求','按各自原定工期延長相同月數；兩個方案的實際總工期可能不同，並非同一日曆時間序列。',comparison.delays.map(row=>({label:`${row.label}\nA ${row.a_months} 月／B ${row.b_months} 月`,values:[row.a,row.b]}))]
      ]){
        const chart=el('div',undefined,'scenario-chart');chart.dataset.scenarioChart=kind;charts.append(chart);
        window.GameCharts?.render(chart,{title,description,type:'bar',rows,series:[{label:'方案 A',color:'#176b54'},{label:'方案 B',color:'#426cba'}],unit:comparison.currency,source,filename:`planning-alternatives-${kind}.svg`});
      }
      host.append(el('p','回本份數採用各方案自行輸入的每份淨貢獻；未提供時保留為未知，不當作零。它是成本覆蓋要求，不是銷售預測。','fine'));
    }
    if(slots?.a&&slots?.b){
      const differences=el('details');differences.open=true;differences.className='scenario-input-differences';differences.append(el('summary',`哪些輸入不同？（${comparison.inputs.length} 項）`));
      if(comparison.inputs.length)differences.append(table(['輸入假設','方案 A','方案 B'],comparison.inputs.map(row=>[row.label,present(row.a),present(row.b)]),'成本方案的輸入差異'));
      else differences.append(el('p','兩個方案的輸入假設相同。'));
      differences.append(el('p','人員組按輸入順序對照；費用按來源方案識別。變更多項假設時，總差額不能單獨歸因於其中一項。','fine'));host.append(differences);
    }
    return comparison;
  }
  function read(){return window.PlanningFlow.budgetScenarios();}
  function message(text,error=false){const node=document.getElementById('budget-scenarios-status');node.textContent=text;node.dataset.error=String(error);}
  function refreshCurrent(){
    if(!config)return;
    const current=config.getCurrent(),saved=read();
    for(const key of ['a','b']){
      const button=document.getElementById(`scenario-save-${key}`);button.disabled=!current||!!saved.error;
      button.textContent=`${saved.slots[key]?'更新':'保存為'}方案 ${key.toUpperCase()}`;
      document.getElementById(`scenario-remove-${key}`).disabled=!saved.slots[key];
    }
    document.getElementById('scenario-current').textContent=current?`目前已計算：${current.base.months} 個月 · ${current.currency} ${fmt(current.base.cash_budget)} 現金預算。可保存為 A 或 B。`:'先完成計算，才可保存目前輸入；已保存的方案不會隨表單修改而改變。';
    const comparison=renderInto('budget-scenarios-view',saved.slots,{feeMetadata,currentContextId:window.PlanningFlow.read()?.context_id||null});
    document.getElementById('scenario-export').disabled=!comparison.ready||!!saved.error;
    document.getElementById('scenario-recheck').hidden=!Object.values(saved.slots).some(item=>item?.budget?.fee_reference);
    if(saved.error)message(saved.error,true);
  }
  function save(key){
    const budget=config.getCurrent();if(!budget)return;
    const existing=read().slots[key];
    if(existing&&!confirm(`更新方案 ${key.toUpperCase()} 會取代「${existing.name}」已保存的假設及結果。繼續？`))return;
    const name=document.getElementById(`scenario-name-${key}`).value.trim()||`方案 ${key.toUpperCase()}`;
    const ok=window.PlanningFlow.saveBudgetScenario(key,name,budget,config.getDraft());
    if(ok){refreshCurrent();message(`已保存方案 ${key.toUpperCase()}「${name}」。之後修改表單不會改動此記錄。`);}
    else message(window.PlanningFlow.storageMessage()||'方案未能保存，請檢查瀏覽器儲存。',true);
  }
  async function exportComparison(){
    const initial=read(),raw=JSON.stringify(initial.slots),button=document.getElementById('scenario-export');button.disabled=true;
    try{
      if(Object.values(initial.slots).some(saved=>saved?.budget?.fee_reference)){
        feeMetadata=null;
        const response=await fetch('/api/planning/fees');if(!response.ok)throw new Error('未能核對費用來源');
        feeMetadata=(await response.json()).metadata;
      }
      const latest=read();if(raw!==JSON.stringify(latest.slots))throw new Error('方案已更改，請核對後再次匯出');
      const comparison=compare(latest.slots,{feeMetadata,currentContextId:window.PlanningFlow.read()?.context_id||null});
      if(latest.error||!comparison.ready)throw new Error(latest.error||comparison.issues.join(' ')||'請先保存兩個方案');
      window.PlanningFlow.download({schema_version:'game_budget_alternatives_v1',exported_at_utc:new Date().toISOString(),data_kind:'saved_user_assumptions',slots:clone(latest.slots),comparison,interpretation:['B minus A compares requirements under user assumptions, not forecasts or causal effects.','Saved fee sources, commitments and user exchange rates are retained; no live vendor price or currency conversion is inferred.','Alternative snapshots do not automatically replace the active planning budget.']},'gamescope-budget-alternatives.json');
      message('兩個方案、輸入差異、計算結果及來源已一同匯出。');
    }catch(error){message(`未能匯出：${error.message}`,true);}
    finally{refreshCurrent();}
  }
  async function recheckSources(){
    const button=document.getElementById('scenario-recheck');button.disabled=true;feeMetadata=null;
    try{
      const response=await fetch('/api/planning/fees');if(!response.ok)throw new Error('費用來源服務未能回應');
      feeMetadata=(await response.json()).metadata;
      const comparison=compare(read().slots,{feeMetadata});
      message(comparison.issues.length?comparison.issues.join(' '):'已重新核對本機保存的費用來源版本。',!!comparison.issues.length);
    }catch(error){message(`未能核對：${error.message}。恢復資料服務後可重試。`,true);}
    finally{button.disabled=false;refreshCurrent();}
  }
  function init(options){
    config=options;
    const saved=read();
    for(const key of ['a','b']){
      document.getElementById(`scenario-name-${key}`).value=saved.slots[key]?.name||'';
      document.getElementById(`scenario-save-${key}`).addEventListener('click',()=>save(key));
      document.getElementById(`scenario-remove-${key}`).addEventListener('click',()=>{
        if(window.PlanningFlow.removeBudgetScenario(key)){document.getElementById(`scenario-name-${key}`).value='';refreshCurrent();message(`已移除方案 ${key.toUpperCase()}。目前輸入沒有改變。`);}
        else message(window.PlanningFlow.storageMessage()||'未能移除方案。',true);
      });
    }
    document.getElementById('scenario-export').addEventListener('click',exportComparison);
    document.getElementById('scenario-recheck').addEventListener('click',recheckSources);refreshCurrent();
  }
  return {compare,renderInto,init,refreshCurrent,invalidateCurrent:refreshCurrent,setFeeMetadata(value){feeMetadata=value;refreshCurrent();}};
})();
