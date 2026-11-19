'use strict';
const flow = window.PlanningFlow, el = flow.element, $ = id => document.getElementById(id);
const number = n => Number(n).toLocaleString('en-US', {maximumFractionDigits: 2});
let state = null, checkId = 0;
flow.mount('summary');
function link(text, href) {const a = el('a', text); a.href = href; return a;}
function detail(target, label, value) {const d = el('details'); d.append(el('summary', label), el('pre', JSON.stringify(value, null, 2))); target.append(d);}
function render() {
  state = flow.read(); flow.render();
  $('plan-content').hidden = !state; $('plan-print').disabled = !state;
  if (!state) {$('plan-status').replaceChildren(el('span', '尚未有規劃。'), link('先比較歷史分布並選擇 A 或 B →', '/')); return;}
  $('plan-name').value = state.name || ''; $('plan-notes').value = state.notes || ''; renderNotes();
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
    const delays = el('ul'); b.delays.forEach(d => delays.append(el('li', `${d.months} 個月：現金預算 ${money(d.cash_budget)}${d.funding_balance === null ? '' : `；資金差額 ${money(d.funding_balance)}`}`)));
    budget.append(delays, el('p', b.base.cash_break_even_units === null ? '未提供正數每份淨貢獻，沒有回本份數結果。' : `每份淨貢獻由你假設：${money(b.request.net_unit_contribution)}。覆蓋現金預算需要 ${number(b.base.cash_break_even_units)} 份銷售；這是要求，不是銷量預測。`));
    detail(budget, '查看全部預算輸入、計算及費用來源', b);
  }
  budget.append(link('修改預算及選用費用 →', '/planning#budget-section'));
}
function renderNotes() {$('plan-title').textContent = state?.name || '目前規劃'; $('plan-note-display').textContent = state?.notes || '尚未填寫決定或待驗證事項。';}
async function validate() {
  const id = ++checkId; $('plan-export').disabled = true; render(); if (!state) return;
  $('plan-status').textContent = '正在核對此規劃使用的資料版本…';
  const checks = await flow.sourceChecks(state); if (id !== checkId) return;
  $('plan-checks').replaceChildren(); [...checks.checked, ...checks.issues].forEach(text => $('plan-checks').append(el('li', text)));
  $('plan-checks').className = checks.issues.length ? 'plan-issues' : '';
  const bundle = flow.bundle(state, checks);
  $('plan-completion').textContent = bundle.completion.missing.length ? `仍未完成：${bundle.completion.missing.join('、')}。匯出時會標記為未完成。` : '各步驟已有記錄；這表示流程已填妥，不表示計劃已證明可行。';
  $('plan-status').textContent = checks.issues.length ? '部分來源版本未通過核對，請按提示更新後再匯出。' : '本機來源版本核對完成。可繼續修改或匯出目前規劃。';
  $('plan-export').disabled = checks.issues.length > 0;
}
['plan-name', 'plan-notes'].forEach(id => $(id).addEventListener('input', () => {
  flow.mutate(s => {s.name = $('plan-name').value.trim(); s.notes = $('plan-notes').value.trim();}); state = flow.read(); renderNotes();
}));
$('plan-refresh').addEventListener('click', validate);
$('plan-print').addEventListener('click', () => window.print());
$('plan-clear').addEventListener('click', () => {if (confirm('清除此分頁的規劃條件、參考作品及預算？請先匯出需要保留的內容。') && flow.clear()) validate();});
$('plan-export').addEventListener('click', async () => {
  $('plan-export').disabled = true; const current = flow.read(); if (!current) return;
  const checks = await flow.sourceChecks(current);
  const latest = flow.read();
  if (!latest || latest.context_id !== current.context_id || latest.updated_at_utc !== current.updated_at_utc) {await validate(); $('plan-status').textContent = '規劃已改變，請核對後重新匯出。'; return;}
  if (checks.issues.length) {await validate(); return;}
  flow.download(flow.bundle(current, checks), 'gamescope-planning-summary.json'); $('plan-export').disabled = false;
});
validate();
