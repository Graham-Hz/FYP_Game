'use strict';
const $ = id => document.getElementById(id);
const labels = {cash_cost:'現金支出',reported_budget:'來源所稱預算',planned_budget:'原定預算',economic_estimate:'經濟成本估值',funding_received:'獲得資金',funding_request:'申請資金',reported_cost:'來源所稱成本',development_duration:'開發期',team_size:'人數',logged_hours:'記錄工時',planned_effort:'計劃人月'};
const componentNames = {team_cash:'人力現金',overhead:'每月其他開支',outsourcing:'外包／素材',marketing:'行銷',other_one_off:'其他一次性',reference_fees:'選用工具／平台／設備費',contingency:'備用金'};
const stages = {released:'已發行',pitch_prototype:'提案／原型',ongoing:'持續開發'};
const fmt = n => Number(n).toLocaleString('en-US',{maximumFractionDigits:2});
const el = (tag,text,cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
let library = null, result = null, revision = 0, teamId = 0;
let restoringDraft = true, blockedSavedFees = false;
const draftFields = ['budget-currency','budget-months','monthly_overhead','outsourcing','marketing','other_one_off','contingency_percent','available_funds','net_unit_contribution'];
function captureDraft() {const fees=blockedSavedFees?{fee_selection:window.PlanningFlow.read()?.draft?.fee_selection}:feePlanner.selection();return {fields:Object.fromEntries(draftFields.map(id=>[id,$(id).value])),team:[...$('team-rows').children].map(r=>Object.fromEntries([...r.querySelectorAll('input')].map(i=>[i.dataset.field,i.value]))),...fees};}
function sourceLink(source) {const a=el('a',`${source.author} · ${source.title}`,'source-link');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function displayValue(o) {
  const sign={approx:'約 ',less_than:'< ',greater_than:'> ',reported:''}[o.qualifier];
  const unit=o.unit==='money' ? (o.currency || '原文 $，幣別未明') : {months:'月',people:'人',hours:'小時',person_months:'人月'}[o.unit];
  return `${sign}${fmt(o.value)} ${unit}`;
}
function table(headers,rows) {const t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>{const th=el('th',h);th.scope='col';tr.append(th);});head.append(tr);t.append(head);const body=el('tbody');rows.forEach(row=>{const r=el('tr');row.forEach(v=>{const td=el('td');td.append(v instanceof Node?v:document.createTextNode(String(v)));r.append(td);});body.append(r);});t.append(body);return t;}
function renderCases() {
  if(!library)return;
  const query=$('case-search').value.trim().toLowerCase(),stage=$('case-stage').value,platform=$('case-platform').value;
  const cases=library.cases.filter(c=>(!query||`${c.game} ${c.context} ${c.source.author}`.toLowerCase().includes(query))&&(!stage||c.stage_at_source===stage)&&(!platform||c.platform_scope.includes(platform)));
  $('case-list').replaceChildren();
  $('case-status').textContent=cases.length?`顯示 ${cases.length} / ${library.metadata.case_count} 個案例。展開作品查看數值定義。`:'沒有符合條件的案例；可清除搜尋或篩選。';
  for(const c of cases){
    const entry=el('details',undefined,'case-entry');
    entry.append(el('summary',`${c.game} · ${c.source.publication_date?.slice(0,4)||'發表年份未列'} · ${stages[c.stage_at_source]}`));
    entry.append(el('p',`${c.platform_scope} · ${c.context}`),sourceLink(c.source));
    entry.append(el('p',`發表：${c.source.publication_date||'來源未列日期'}；查閱：${c.source.accessed_date}。`,'fine'));
    const rows=c.observations.map(o=>{
      const val=el('span',displayValue(o));
      if(o.currency_basis==='article_context')val.append(el('small','幣別按文章上下文判讀，非該金額旁明示。'));
      const scope=el('span',o.scope);scope.append(el('small',o.period));
      const note=el('span',o.notes||'—');note.append(el('small',`原文位置：${o.locator} · ${o.observation_id}`));
      return [labels[o.metric],val,scope,note];
    });
    const scroll=el('div',undefined,'table-scroll');scroll.tabIndex=0;scroll.setAttribute('aria-label',`${c.game} 數值及來源表`);scroll.append(table(['項目','來源數值','涵蓋範圍／時期','解讀與來源位置'],rows));entry.append(scroll);$('case-list').append(entry);
  }
}
async function loadCases(){try{const response=await fetch('/api/planning/cases');const data=await response.json();if(!response.ok)throw new Error(data.error);library=data;$('case-count').textContent=`${data.metadata.case_count} 個案例 · ${data.metadata.observation_count} 筆紀錄`;$('case-downloads').hidden=false;renderCases();}catch(e){$('case-status').textContent=`案例未能載入：${e.message}。預算計算仍可獨立使用。`;}}
['case-search','case-stage','case-platform'].forEach(id=>$(id).addEventListener('input',renderCases));
function invalidate(message='輸入已改變，請重新計算。'){revision++;result=null;$('budget-results').hidden=true;$('budget-status').textContent=message;
  if(!restoringDraft)window.PlanningFlow.saveDraft(captureDraft());
}
function addTeam(data={}){
  if($('team-rows').children.length>=20)return;
  const n=++teamId,row=el('fieldset',undefined,'team-row');row.append(el('legend',`人員／職能組 ${n}`));const grid=el('div',undefined,'team-fields');
  const fields=[['label','人員／職能','text',null,null,null],['people','人數','number',1,50,1],['allocation','投入比例 (0–1)','number',0,1,0.01],['monthly_cash','每人每月現金成本（全職）','number',0,1000000000,0.01],['monthly_unpaid','額外未付勞動估值（全職／月）','number',0,1000000000,0.01]];
  fields.forEach(([key,title,type,min,max,step])=>{const l=el('label',title),input=el('input');input.type=type;input.dataset.field=key;input.required=true;if(type==='number'){input.min=min;input.max=max;input.step=step;}else input.maxLength=80;if(data[key]!==undefined)input.value=data[key];l.append(input);grid.append(l);});
  const remove=el('button','移除此組','outline');remove.type='button';remove.addEventListener('click',()=>{row.remove();invalidate();});row.append(grid,remove);$('team-rows').append(row);
}
function num(id,optional=false){const v=$(id).value;return optional&&v===''?null:Number(v);}
function payload(){return {currency:$('budget-currency').value,months:num('budget-months'),team:[...$('team-rows').children].map(r=>Object.fromEntries([...r.querySelectorAll('input')].map(i=>[i.dataset.field,i.type==='number'?Number(i.value):i.value.trim()]))),...Object.fromEntries(['monthly_overhead','outsourcing','marketing','other_one_off','contingency_percent'].map(k=>[k,num(k)])),available_funds:num('available_funds',true),net_unit_contribution:num('net_unit_contribution',true),...feePlanner.selection()};}
function renderBudget(data){
  const b=data.base,cur=data.currency,money=v=>`${cur} ${fmt(v)}`;
  // Reveal before measuring chart containers; SVG keeps readable labels at card width.
  $('budget-results').hidden=false;
  $('budget-context').textContent=`使用者假設 · ${b.months} 個月 · ${cur} · 所有結果由本次輸入計算。`;
  $('budget-metrics').replaceChildren();
  [['現金預算（含備用金）',b.cash_budget],['額外未付勞動估值',b.unpaid_labour_value],['含勞動估值的總投入',b.resource_budget]].forEach(([name,value])=>{const a=el('article');a.append(el('span',name),el('strong',money(value)));$('budget-metrics').append(a);});
  const parts=Object.entries(b.components).map(([k,v])=>[componentNames[k],v]);
  const chartSource=`來源：本次使用者輸入假設；計算方法 ${data.method_version}。${data.fee_reference?'選用費用按已保存來源及使用者確認的數量、資格、匯率計入；詳見同次預算 JSON。':'未選用費用參考。'}`;
  window.GameCharts.render('cost-chart',{title:'現金預算組成',description:`${b.months} 個月的各項現金投入，包含備用金；未付勞動估值另行計算。`,type:'bar',rows:parts.map(([label,value])=>({label,values:[value]})),series:[{label:'現金成本'}],unit:cur,source:chartSource,filename:'planning-cost-components.svg'});
  $('cost-table').replaceChildren(table(['現金項目',`金額 (${cur})`],parts.map(([k,v])=>[k,fmt(v)])));
  $('fee-result-panel').hidden=!data.fee_reference;
  if(data.fee_reference){
    const rows=b.fee_lines.map(line=>{
      const selected=data.fee_reference.selections.find(s=>s.fee_id===line.fee_id),r=selected.reference;
      const source=el('a',`${line.product} · ${line.plan}`);source.href=r.primary_source_url;source.target='_blank';source.rel='noopener noreferrer';
      return [source,`${fmt(line.quantity)} × ${r.amount} ${r.currency||''} × ${line.price_units} 個價格單位${line.covered_months?`（涵蓋 ${line.covered_months} 月）`:''}`,`${line.source_currency||'—'} ${fmt(line.source_total)}`,fmt(line.fx_rate),money(line.cost)];
    });
    $('fee-result-table').replaceChildren(table(['方案／來源','數量 × 單價 × 收費期','原幣金額','換算率','計劃金額'],rows));
  }
  window.GameCharts.render('delay-chart',{title:'工期延長的現金預算',description:'原定工期、延長 3 個月與延長 6 個月。每月人力及手動開支不變；訂閱按完整收費期續訂，備用金重新計算。',type:'bar',rows:data.delays.map(s=>({label:`${s.months} 個月`,values:[s.cash_budget]})),series:[{label:'現金預算',color:'#426cba'}],unit:cur,source:chartSource,filename:'planning-delay-budget.svg'});
  $('delay-table').replaceChildren(table(['開發期',`現金預算 (${cur})`,'較原定增加','資金差額'],data.delays.map(s=>[`${s.months} 個月`,fmt(s.cash_budget),fmt(s.cash_budget-b.cash_budget),s.funding_balance===null?'未提供資金':fmt(s.funding_balance)])));
  window.GameCharts.render('resource-chart',{title:'工期與總投入的情境比較',description:'每個點代表一個完整開發期情境；連線只輔助比較，並非逐月現金流或實際支出紀錄。',type:'line',rows:data.delays.map(s=>({label:`${s.months} 個月`,values:[s.cash_budget,s.resource_budget]})),series:[{label:'現金預算'},{label:'現金及未付勞動估值'}],unit:cur,source:chartSource,filename:'planning-duration-resources.svg'});
  window.GameCharts.render('break-even-chart',{title:'不同工期的回本銷售要求',description:data.break_even_status==='available'?`每份銷售淨貢獻假設為 ${cur} ${fmt(data.request.net_unit_contribution)}。份數是覆蓋成本的要求，不是預測銷量。`:'未提供正數的每份銷售淨貢獻，無法繪製回本要求；不會把未知要求當作零。',type:'bar',rows:data.delays.map(s=>({label:`${s.months} 個月`,values:[s.cash_break_even_units,s.resource_break_even_units]})),series:[{label:'覆蓋現金預算'},{label:'連同未付勞動估值'}],unit:'份',source:chartSource,filename:'planning-break-even-requirements.svg'});
  const req=$('requirements');req.replaceChildren();
  req.append(el('p',b.funding_balance===null?'可投入資金未提供，因此不判斷資金是否足夠。':b.funding_balance<0?`按輸入預算，資金不足 ${money(-b.funding_balance)}。`:`預留全部計劃現金成本後，資金餘額 ${money(b.funding_balance)}。`));
  const runway={funds_not_supplied:'未提供資金，無法計算可支持月數。',insufficient_upfront_funds:'現有資金不足以預留一次性支出、備用金及選用費用。',no_monthly_cash_outflow:'每月手動現金支出為零，無法以固定每月支出換算可支持月數。',constant_burn_assumption:`按固定支出假設，資金可支持約 ${fmt(b.runway_months)} 個月。`,reference_fees_reserved_upfront:`先預留本情境全部選用費用後，資金可支持約 ${fmt(b.runway_months)} 個月（最多顯示至本情境的 ${b.months} 個月）。`};req.append(el('p',runway[b.runway_status]));
  req.append(el('p',data.break_even_status==='available'?`覆蓋現金預算需要 ${fmt(b.cash_break_even_units)} 份銷售；連同未付勞動估值則需要 ${fmt(b.resource_break_even_units)} 份。`:'未提供正數的每份銷售淨貢獻，因此沒有回本份數結果。'));
  $('budget-results').hidden=false;
}
$('budget-form').addEventListener('input',()=>invalidate());
$('budget-currency').addEventListener('change',()=>{feePlanner.currencyChanged();invalidate('幣別已改變，手動數值未作匯率換算。請重新核對選用費用的換算率與資格確認。');});
$('add-team').addEventListener('click',()=>{addTeam();invalidate();});
$('load-example').addEventListener('click',()=>{
  blockedSavedFees=false;$('discard-saved-fees').hidden=true;$('calculate-budget').disabled=false;
  feePlanner.clear();
  $('budget-currency').value='HKD';$('budget-months').value=12;$('team-rows').replaceChildren();teamId=0;
  addTeam({label:'Founder',people:1,allocation:1,monthly_cash:0,monthly_unpaid:12000});addTeam({label:'Part-time developer',people:1,allocation:0.5,monthly_cash:16000,monthly_unpaid:0});
  Object.entries({monthly_overhead:2000,outsourcing:20000,marketing:15000,other_one_off:5000,contingency_percent:10,available_funds:200000,net_unit_contribution:40}).forEach(([k,v])=>$(k).value=v);
  invalidate('已載入人工假設示例並清除選用費用，不代表案例數據或市場報價。可修改後按計算。');
});
$('budget-form').addEventListener('reset',()=>{queueMicrotask(()=>{blockedSavedFees=false;$('discard-saved-fees').hidden=true;$('calculate-budget').disabled=false;feePlanner.clear();$('team-rows').replaceChildren();teamId=0;addTeam();invalidate('已清空。請輸入自己的計劃。');});});
$('budget-form').addEventListener('submit',async event=>{
  event.preventDefault();if(blockedSavedFees || restoringDraft)return;invalidate('正在計算…');const requestRevision=revision,context=window.PlanningFlow.read()?.context_id;$('calculate-budget').disabled=true;
  try{const response=await fetch('/api/planning/budget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});const data=await response.json();if(requestRevision!==revision)return;if(!response.ok)throw new Error(data.error);result=data;renderBudget(data);const saved=context&&window.PlanningFlow.saveBudget(data,context);$('budget-flow-summary').hidden=!saved;$('budget-status').textContent=context&&!saved?'計算完成，但未能保存至規劃；可先匯出個別預算，並查看上方儲存提示。':'計算完成。結果及假設可於下方查看和匯出。';}
  catch(e){if(requestRevision===revision)$('budget-status').textContent=`未完成計算：${e.message}`;}
  finally{$('calculate-budget').disabled=false;}
});
$('budget-export').addEventListener('click',()=>{if(!result)return;const blob=new Blob([JSON.stringify({...result,exported_at:new Date().toISOString()},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='game-planning-budget.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
const feePlanner=new window.FeePlanner(invalidate);
window.PlanningFlow.mount('budget');
$('discard-saved-fees').addEventListener('click',()=>{blockedSavedFees=false;feePlanner.clear();$('discard-saved-fees').hidden=true;$('calculate-budget').disabled=false;invalidate('已明確移除無法還原的舊費用。請自行補充所需開支或重新選用工具，再計算。');});
async function initialisePlanning() {
  const saved=window.PlanningFlow.read(),draft=saved?.draft;
  $('budget-form').inert=true;$('calculate-budget').disabled=true;$('load-example').disabled=true;
  if(draft){draftFields.forEach(id=>{if(draft.fields[id]!==undefined)$(id).value=draft.fields[id];});draft.team.forEach(addTeam);}
  else addTeam();
  if(saved)$('case-platform').value=saved.comparison.platform==='pc'?'PC':'Android';
  loadCases();await feePlanner.load();
  if(draft?.fee_selection && !feePlanner.restore(draft.fee_selection)) {
    blockedSavedFees=true;$('discard-saved-fees').hidden=false;
    window.PlanningFlow.mutate(s=>s.budget=null);
    $('budget-status').textContent='已保存的工具費用無法還原（來源版本不同或資料未能載入）。請先移除舊費用後重新選取；系統不會悄悄把它們當作零。';
  } else if(saved?.budget) {result=saved.budget;renderBudget(result);$('budget-status').textContent='已還原此規劃保存的預算及結果。修改任何輸入後需重新計算。';}
  else if(draft)$('budget-status').textContent='已還原此規劃的預算輸入。請核對後計算。';
  restoringDraft=false;$('budget-form').inert=false;$('load-example').disabled=false;$('calculate-budget').disabled=blockedSavedFees;
  $('budget-flow-summary').hidden=!saved;
}
initialisePlanning();
