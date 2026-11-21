'use strict';
const flow = window.PlanningFlow, el = flow.element, $ = id => document.getElementById(id);
const number = n => Number(n).toLocaleString('en-US', {maximumFractionDigits: 2});
let state = null, workspace = null, checkId = 0;
flow.mount('summary');
function link(text, href) {const a = el('a', text); a.href = href; return a;}
function detail(target, label, value) {const d = el('details'); d.append(el('summary', label), el('pre', JSON.stringify(value, null, 2))); target.append(d);}
function render() {
  state = flow.read();workspace=flow.readWorkspace(); flow.render();
  const hasContent=!!(state||workspace.findings.length||workspace.budget_scenarios.a||workspace.budget_scenarios.b);
  $('plan-content').hidden = !hasContent; $('plan-print').disabled = !hasContent;
  if (!hasContent) {$('plan-status').replaceChildren(el('span', workspace.error||'尚未有規劃。'), link('探索市場並保存依據', '/market')); return;}
  $('plan-name').value = (state?state.name:workspace.name) || ''; $('plan-notes').value = (state?state.notes:workspace.notes) || ''; renderNotes();
  renderFindings();
  $('plan-legacy-empty').hidden=!!state;
  ['plan-market','plan-references','plan-budget'].forEach(id=>$(id).hidden=!state);
  $('plan-scenarios').replaceChildren(el('p','正在核對保存的預算方案…'));
  if(!state)return;
  const result = state.comparison, selected = result.scenarios[state.choice], market = $('plan-market');
  market.replaceChildren(el('h2', '1 歷史比較與選擇'), el('p', flow.describe(state)),
    el('p', `${result.metadata.source_name} · ${result.metadata.snapshot} · ${result.metadata.sample_label} · 版本 ${result.version_id}`),
    el('p', `所選條件有 ${number(selected.total)} 筆；A、B 共有 ${number(result.overlap_count)} 筆重疊。這不是隨機對照實驗。`));
  if (selected.status !== 'available') market.append(el('p', '所選樣本少於介面提示門檻，請審慎解讀；較大樣本亦不保證代表性。', 'sample-warning'));
  const tiers = el('ul'); selected.tiers.forEach(t => tiers.append(el('li', `${t.label}：${number(t.count)} 筆（${t.percent === null ? '未計算比例' : t.percent.toFixed(1) + '%'}）`)));
  market.append(tiers, el('p', result.metadata.caveat, 'fine'), link('修改比較條件 →', '/'));
  detail(market, '查看 A／B 比較與來源紀錄', result);
  const references = $('plan-references'); references.replaceChildren(el('h2', '2 相近遊戲參考'));
  if (result.platform === 'mobile') references.append(el('p', '目前未提供 Android 相近遊戲搜尋。本規劃使用 Android 歷史比較，直接連到成本預算；不會套用 Steam 作品。'));
  else {
    const saved = state.references, rows = saved?.evidence.rows.filter(r => saved.selected_ids.includes(String(r.steam_id))) || [];
    if (rows.length) {
      const request = saved.evidence.request;
      references.append(el('p', `你的參考條件：${request.genres.join(' + ')}；預計售價 USD ${number(request.price)}。共選取 ${rows.length} 款。`));
      const list = el('ul', undefined, 'plan-games'); rows.forEach(r => {
        const item = el('li'), a = link(r.name, `https://store.steampowered.com/app/${r.steam_id}/`); a.target = '_blank'; a.rel = 'noopener noreferrer';
        item.append(a, el('p', `共同類型：${r.match.shared_genres.join(', ')}；類型重合 ${(r.match.genre_similarity * 100).toFixed(1)}%；觀察價格 USD ${number(r.price)}；歷史估算營收 USD ${number(r.revenue)}。`)); list.append(item);
      }); references.append(list);
      detail(references, '查看參考作品的來源與配對條件', saved.evidence.metadata);
    } else references.append(el('p', state.reference_skip ? `已記錄略過原因：${state.reference_skip}` : '尚未選取參考作品。可先查看候選清單，再選擇最多五款作參考。'));
    references.append(el('p', 'Steam 參考來自獨立的高營收選樣；營收快照為 2024 年，類型資料為 2025 年。它不是主頁比較樣本，也不是一般新遊戲收入的基準。', 'sample-warning'), link('查看／修改參考作品 →', '/revenue#reference-panel'));
  }
  const budget = $('plan-budget'); budget.replaceChildren(el('h2', '3 個人預算與延期情境'));
  if (!state.budget) budget.append(el('p', state.draft ? '已保存預算輸入，但尚未有對應的有效計算結果。請核對後重新計算。' : '尚未輸入及計算預算。'));
  else {
    const b = state.budget, money = n => `${b.currency} ${number(n)}`, metrics = el('div', undefined, 'plan-metrics');
    [['原定現金預算', b.base.cash_budget], ['額外未付勞動估值', b.base.unpaid_labour_value], ['含勞動估值總投入', b.base.resource_budget]].forEach(([label, value]) => {const m = el('div'); m.append(el('span', label), el('strong', money(value))); metrics.append(m);});
    budget.append(el('p', `${b.base.months} 個月 · 使用者假設 · 已含現金備用金`), metrics);
    const matching = window.BudgetScenarios.matchingSlots(b, workspace.budget_scenarios);
    budget.append(el('p', matching.length
      ? `目前預算的輸入及計算來源與已保存方案 ${matching.map(slot => slot.toUpperCase()).join('／')} 相同。這是你最近一次計算的預算，並非系統推薦。`
      : '目前預算是你最近一次計算的結果，輸入或計算來源與已保存 A／B 不完全相同。可到成本預算載入所需方案，核對並重新計算。', 'plan-budget-current'));
    const delays = el('ul'); b.delays.forEach(d => delays.append(el('li', `${d.months} 個月：現金預算 ${money(d.cash_budget)}${d.funding_balance === null ? '' : `；資金差額 ${money(d.funding_balance)}`}`)));
    budget.append(delays, el('p', b.base.cash_break_even_units === null ? '未提供正數每份淨貢獻，沒有回本份數結果。' : `每份淨貢獻由你假設：${money(b.request.net_unit_contribution)}。覆蓋現金預算需要 ${number(b.base.cash_break_even_units)} 份銷售；這是要求，不是銷量預測。`));
    detail(budget, '查看全部預算輸入、計算及費用來源', b);
  }
  budget.append(link('修改預算及選用費用 →', '/planning#budget-section'));
}
function renderNotes() {$('plan-title').textContent = (state?state.name:workspace?.name) || '目前規劃'; $('plan-note-display').textContent = (state?state.notes:workspace?.notes) || '尚未填寫決定或待驗證事項。';}
function renderFindings() {
  const host=$('plan-findings');host.querySelectorAll('[data-saved-chart]').forEach(node=>window.GameCharts.dispose(node));
  host.replaceChildren(el('h2','市場分析依據'),el('p','各來源的背景證據分開保存；下方筆記是你的解讀，不會自動變成銷量預測或成本假設。','fine'));
  if(!workspace.findings.length){host.append(el('p','尚未保存市場分析依據。'),link('探索市場並加入依據','/market'));return;}
  for(const finding of workspace.findings) {
    const card=el('article',undefined,'plan-finding');card.dataset.findingId=finding.id;
    card.append(el('h3',finding.title),el('p',`${finding.source.name} · ${finding.source.snapshot||'資料日期未提供'} · 版本 ${finding.source.version_id}`,'fine'));
    card.append(el('p','正在核對此依據的來源…','plan-finding-check fine'));
    if(finding.source.data_kind==='synthetic')card.append(el('strong','人工示例，並非真實市場','sample-warning'));
    const filters=finding.filters;card.append(el('p',`類型：${filters.group||'全部'}；標籤：${filters.tag||'不限'}；發售年：${filters.year_from??'不限'}–${filters.year_to??'不限'}。`));
    const list=el('ul');finding.summary.forEach(item=>list.append(el('li',`${item.label}：${item.value===null?'未提供':number(item.value)} ${item.unit||''}`)));card.append(list);
    if(finding.comparison){const c=finding.comparison;card.append(el('p',`所選 ${c.selected.label}：n=${number(c.selected.n)}；對照 ${c.baseline.label}：n=${number(c.baseline.n)}；重疊 ${number(c.overlap_count)}。`));}
    card.append(el('p',`你的解讀／規劃用途：${finding.note||'尚未填寫。請補充這份分析如何影響你的規劃。'}`,'plan-finding-note'));
    const charts=el('details');charts.append(el('summary','查看保存的圖表與數值'));const chartHost=el('div');charts.append(chartHost);let drawn=false;
    charts.addEventListener('toggle',()=>{if(!charts.open||drawn)return;drawn=true;for(const chart of finding.charts){
      if(chart.type==='scatter'){chartHost.append(el('p',`${chart.title}：保存完整配對統計及圖表描述；散點個別記錄未複製至規劃。`));detail(chartHost,'查看散點分析摘要',chart);continue;}
      const plot=el('div');plot.dataset.savedChart='true';chartHost.append(plot);window.GameCharts.render(plot,{...chart,description:[chart.description?.replace('點選分段可查看記錄。',''),'這是保存時的圖表摘要；完整互動及作品明細可返回市場分析查看。',chart.rows_truncated?`只保存原圖前 ${chart.rows_saved} / ${chart.row_count} 項；完整資料請返回市場分析。`:'',chart.outlier_points_omitted?'個別離群點未複製至此摘要圖。':''].filter(Boolean).join(' ')});
    }});card.append(charts);
    detail(card,'查看完整來源、條件及保存數值',finding);
    const remove=el('button','移除此依據','outline');remove.type='button';remove.dataset.removeFinding=finding.id;remove.addEventListener('click',()=>{const removed=flow.removeFinding(finding.id);if(removed.ok)validate();else $('plan-status').textContent=removed.error;});card.append(remove);host.append(card);
  }
  host.append(link('繼續探索及保存分析','/market'));
}
async function validate() {
  const id = ++checkId; $('plan-export').disabled = true; render(); if ($('plan-content').hidden) return;
  const checkedState=state,checkedWorkspace=workspace;
  $('plan-status').textContent = '正在核對此規劃使用的資料版本…';
  const checks = await flow.sourceChecks(checkedState,checkedWorkspace); if (id !== checkId) return;
  $('plan-findings').querySelectorAll('.plan-finding').forEach(card=>{const status=(checks.item_checks||[]).find(item=>item.id===card.dataset.findingId),node=card.querySelector('.plan-finding-check');node.textContent=status?.message||'此依據未能通過來源核對，請查看下方提示。';node.classList.toggle('sample-warning',!status?.current);});
  window.BudgetScenarios.renderInto($('plan-scenarios'),checkedWorkspace.budget_scenarios,{feeMetadata:checks.feeMetadata,currentContextId:checkedState?.context_id||null});
  $('plan-checks').replaceChildren(); [...checks.checked, ...checks.issues].forEach(text => $('plan-checks').append(el('li', text)));
  $('plan-checks').className = checks.issues.length ? 'plan-issues' : '';
  const bundle = flow.bundle(checkedState, checks,checkedWorkspace);
  $('plan-completion').textContent = bundle.completion.missing.length ? `仍未完成：${bundle.completion.missing.join('、')}。匯出時會標記為未完成。` : '各步驟已有記錄；這表示流程已填妥，不表示計劃已證明可行。';
  $('plan-status').textContent = checks.issues.length ? '部分來源版本未通過核對，請按提示更新後再匯出。' : '本機來源版本核對完成。可繼續修改或匯出目前規劃。';
  $('plan-export').disabled = checks.issues.length > 0;
}
['plan-name', 'plan-notes'].forEach(id => $(id).addEventListener('input', () => {
  const name=$('plan-name').value.trim(),notes=$('plan-notes').value.trim();
  const saved=state?flow.mutate(s => {s.name=name;s.notes=notes;}):flow.saveWorkspaceMeta(name,notes);
  if(!saved){$('plan-status').textContent=flow.storageMessage();$('plan-export').disabled=true;return;}
  state = flow.read();workspace=flow.readWorkspace(); renderNotes();
}));
$('plan-refresh').addEventListener('click', validate);
$('plan-print').addEventListener('click', () => window.print());
$('plan-clear').addEventListener('click', () => {if (confirm('清除此分頁的規劃、分析依據及預算 A／B？請先匯出需要保留的內容。') && flow.clear()) validate();});
$('plan-export').addEventListener('click', async () => {
  $('plan-export').disabled = true; const current = flow.read(),currentWorkspace=flow.readWorkspace();
  if(!current&&!currentWorkspace.findings.length&&!currentWorkspace.budget_scenarios.a&&!currentWorkspace.budget_scenarios.b)return;
  const checks = await flow.sourceChecks(current,currentWorkspace);
  if (JSON.stringify(flow.read())!==JSON.stringify(current)||JSON.stringify(flow.readWorkspace())!==JSON.stringify(currentWorkspace)) {await validate(); $('plan-status').textContent = '規劃已改變，請核對後重新匯出。'; return;}
  if (checks.issues.length) {await validate(); return;}
  flow.download(flow.bundle(current, checks,currentWorkspace), 'gamescope-planning-summary.json'); $('plan-export').disabled = false;
});
validate();
