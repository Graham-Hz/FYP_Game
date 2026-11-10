'use strict';
const $ = id => document.getElementById(id);
const labels = {cash_cost:'現金支出',reported_budget:'來源所稱預算',planned_budget:'原定預算',economic_estimate:'經濟成本估值',funding_received:'獲得資金',funding_request:'申請資金',reported_cost:'來源所稱成本',development_duration:'開發期',team_size:'人數',logged_hours:'記錄工時',planned_effort:'計劃人月'};
const componentNames = {team_cash:'人力現金',overhead:'每月其他開支',outsourcing:'外包／素材',marketing:'行銷',other_one_off:'其他一次性',contingency:'備用金'};
const stages = {released:'已發行',pitch_prototype:'提案／原型',ongoing:'持續開發'};
const fmt = n => Number(n).toLocaleString('en-US',{maximumFractionDigits:2});
const el = (tag,text,cls) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
let library = null, result = null, revision = 0, teamId = 0;
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
function invalidate(message='輸入已改變，請重新計算。'){revision++;result=null;$('budget-results').hidden=true;$('budget-status').textContent=message;}
function addTeam(data={}){
  if($('team-rows').children.length>=20)return;
  const n=++teamId,row=el('fieldset',undefined,'team-row');row.append(el('legend',`人員／職能組 ${n}`));const grid=el('div',undefined,'team-fields');
  const fields=[['label','人員／職能','text',null,null,null],['people','人數','number',1,50,1],['allocation','投入比例 (0–1)','number',0,1,0.01],['monthly_cash','每人每月現金成本（全職）','number',0,1000000000,0.01],['monthly_unpaid','額外未付勞動估值（全職／月）','number',0,1000000000,0.01]];
  fields.forEach(([key,title,type,min,max,step])=>{const l=el('label',title),input=el('input');input.type=type;input.dataset.field=key;input.required=true;if(type==='number'){input.min=min;input.max=max;input.step=step;}else input.maxLength=80;if(data[key]!==undefined)input.value=data[key];l.append(input);grid.append(l);});
  const remove=el('button','移除此組','outline');remove.type='button';remove.addEventListener('click',()=>{row.remove();invalidate();});row.append(grid,remove);$('team-rows').append(row);
}
function num(id,optional=false){const v=$(id).value;return optional&&v===''?null:Number(v);}
function payload(){return {currency:$('budget-currency').value,months:num('budget-months'),team:[...$('team-rows').children].map(r=>Object.fromEntries([...r.querySelectorAll('input')].map(i=>[i.dataset.field,i.type==='number'?Number(i.value):i.value.trim()]))),...Object.fromEntries(['monthly_overhead','outsourcing','marketing','other_one_off','contingency_percent'].map(k=>[k,num(k)])),available_funds:num('available_funds',true),net_unit_contribution:num('net_unit_contribution',true)};}
function bars(target,items,delayed=false){const max=Math.max(...items.map(i=>i[1]),1);$(target).replaceChildren();items.forEach(([name,value])=>{const row=el('div',undefined,'chart-row'),label=el('div',undefined,'chart-label');label.append(el('span',name),el('strong',fmt(value)));const track=el('div',undefined,'chart-track'),fill=el('div',undefined,`chart-fill${delayed?' delay':''}`);fill.style.width=`${value/max*100}%`;track.append(fill);row.append(label,track);$(target).append(row);});}
function renderBudget(data){
  const b=data.base,cur=data.currency,money=v=>`${cur} ${fmt(v)}`;
  $('budget-context').textContent=`使用者假設 · ${b.months} 個月 · ${cur} · 所有結果由本次輸入計算。`;
  $('budget-metrics').replaceChildren();
  [['現金預算（含備用金）',b.cash_budget],['額外未付勞動估值',b.unpaid_labour_value],['含勞動估值的總投入',b.resource_budget]].forEach(([name,value])=>{const a=el('article');a.append(el('span',name),el('strong',money(value)));$('budget-metrics').append(a);});
  const parts=Object.entries(b.components).map(([k,v])=>[componentNames[k],v]);bars('cost-chart',parts);$('cost-table').replaceChildren(table(['現金項目',`金額 (${cur})`],parts.map(([k,v])=>[k,fmt(v)])));
  bars('delay-chart',data.delays.map(s=>[`${s.months} 個月`,s.cash_budget]),true);
  $('delay-table').replaceChildren(table(['開發期',`現金預算 (${cur})`,'較原定增加','資金差額'],data.delays.map(s=>[`${s.months} 個月`,fmt(s.cash_budget),fmt(s.cash_budget-b.cash_budget),s.funding_balance===null?'未提供資金':fmt(s.funding_balance)])));
  const req=$('requirements');req.replaceChildren();
  req.append(el('p',b.funding_balance===null?'可投入資金未提供，因此不判斷資金是否足夠。':b.funding_balance<0?`按輸入預算，資金不足 ${money(-b.funding_balance)}。`:`預留全部計劃現金成本後，資金餘額 ${money(b.funding_balance)}。`));
  const runway={funds_not_supplied:'未提供資金，無法計算可支持月數。',insufficient_upfront_funds:'現有資金不足以預留一次性支出及備用金。',no_monthly_cash_outflow:'每月現金支出為零，無法以固定每月支出換算可支持月數。',constant_burn_assumption:`按固定支出假設，資金可支持約 ${fmt(b.runway_months)} 個月。`};req.append(el('p',runway[b.runway_status]));
  req.append(el('p',data.break_even_status==='available'?`覆蓋現金預算需要 ${fmt(b.cash_break_even_units)} 份銷售；連同未付勞動估值則需要 ${fmt(b.resource_break_even_units)} 份。`:'未提供正數的每份銷售淨貢獻，因此沒有回本份數結果。'));
  $('budget-results').hidden=false;
}
$('budget-form').addEventListener('input',()=>invalidate());
$('budget-currency').addEventListener('change',()=>invalidate('幣別已改變，數值未作匯率換算。請核對所有輸入後重新計算。'));
$('add-team').addEventListener('click',()=>{addTeam();invalidate();});
$('load-example').addEventListener('click',()=>{
  $('budget-currency').value='HKD';$('budget-months').value=12;$('team-rows').replaceChildren();teamId=0;
  addTeam({label:'Founder',people:1,allocation:1,monthly_cash:0,monthly_unpaid:12000});addTeam({label:'Part-time developer',people:1,allocation:0.5,monthly_cash:16000,monthly_unpaid:0});
  Object.entries({monthly_overhead:2000,outsourcing:20000,marketing:15000,other_one_off:5000,contingency_percent:10,available_funds:200000,net_unit_contribution:40}).forEach(([k,v])=>$(k).value=v);
  invalidate('已載入人工假設示例，不代表案例數據或市場報價。可修改後按計算。');
});
$('budget-form').addEventListener('reset',()=>{queueMicrotask(()=>{$('team-rows').replaceChildren();teamId=0;addTeam();invalidate('已清空。請輸入自己的計劃。');});});
$('budget-form').addEventListener('submit',async event=>{
  event.preventDefault();invalidate('正在計算…');const requestRevision=revision;$('calculate-budget').disabled=true;
  try{const response=await fetch('/api/planning/budget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});const data=await response.json();if(requestRevision!==revision)return;if(!response.ok)throw new Error(data.error);result=data;renderBudget(data);$('budget-status').textContent='計算完成。結果及假設可於下方查看和匯出。';}
  catch(e){if(requestRevision===revision)$('budget-status').textContent=`未完成計算：${e.message}`;}
  finally{$('calculate-budget').disabled=false;}
});
$('budget-export').addEventListener('click',()=>{if(!result)return;const blob=new Blob([JSON.stringify({...result,exported_at:new Date().toISOString()},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='game-planning-budget.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
addTeam();loadCases();
