'use strict';
// One planning context per browser tab. Evidence remains separate from assumptions.
window.PlanningFlow = (() => {
  const KEY = 'gamescope.planning.v1', LIMIT = 1500000;
  let storageError = '', page = '';
  const clone = value => JSON.parse(JSON.stringify(value));
  const element = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  function read() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return null;
      if (raw.length > LIMIT) throw new Error('規劃記錄過大');
      const s = JSON.parse(raw);
      if (s.schema_version !== 1 || typeof s.context_id !== 'string' ||
          !['pc', 'mobile'].includes(s.comparison?.platform) || !['a', 'b'].includes(s.choice) ||
          !s.comparison.scenarios?.[s.choice] || !Array.isArray(s.comparison.scenarios[s.choice].tiers) ||
          typeof s.comparison.version_id !== 'string' || !Array.isArray(s.comparison.metadata?.fields) ||
          !s.comparison.scenarios.a?.filters || !s.comparison.scenarios.b?.filters ||
          (s.draft && (!s.draft.fields || !Array.isArray(s.draft.team))) ||
          (s.references && (!Array.isArray(s.references.evidence?.rows) || !Array.isArray(s.references.selected_ids))) ||
          (s.budget && (!s.budget.request || !s.budget.base || !Array.isArray(s.budget.delays)))) throw new Error('規劃格式不相容');
      return s;
    } catch (error) { storageError = `無法讀取暫存規劃：${error.message}。可在摘要頁清除後重建。`; return null; }
  }
  function write(state) {
    try {
      state.updated_at_utc = new Date().toISOString();
      const raw = JSON.stringify(state);
      if (raw.length > LIMIT) throw new Error('規劃記錄過大');
      sessionStorage.setItem(KEY, raw);
      storageError = ''; render(); return true;
    } catch (error) { storageError = `無法保存跨頁規劃：${error.message}。請允許此頁使用瀏覽器儲存後重試。`; render(); return false; }
  }
  function mutate(fn, context) {
    const state = read();
    if (!state || (context && state.context_id !== context)) return false;
    fn(state); return write(state);
  }
  function selectComparison(result, choice) {
    if (!['a', 'b'].includes(choice) || !result.scenarios?.[choice]?.total) return false;
    const previous = read(), samePlatform = previous?.comparison.platform === result.platform;
    if (samePlatform && previous.choice === choice && previous.comparison.version_id === result.version_id &&
        ['a','b'].every(k => JSON.stringify(previous.comparison.scenarios[k].filters) === JSON.stringify(result.scenarios[k].filters))) {
      previous.comparison = clone(result); return write(previous);
    }
    const draft = previous?.draft ? clone(previous.draft) : null;
    if (draft && !samePlatform) delete draft.fee_selection;
    return write({schema_version: 1, context_id: crypto.randomUUID(), name: previous?.name || '', notes: previous?.notes || '',
      comparison: clone(result), choice, references: null, reference_draft: null, reference_skip: null,
      draft, budget: null, context_note: draft ? '分析條件已更新；保留手動預算輸入，請核對並重新計算。跨平台時須重新選用工具費用。' : ''});
  }
  function describe(state) {
    if (!state) return '尚未建立規劃';
    const result = state.comparison, scenario = result.scenarios[state.choice];
    const labels = Object.entries(scenario.filters).map(([key, value]) => {
      const field = result.metadata.fields.find(f => f.key === key);
      return `${field?.label || key}：${field?.choices.find(c => c.value === value)?.label || value}`;
    });
    return `${result.metadata.name} · 條件 ${state.choice.toUpperCase()} · ${labels.join(' · ') || '全部合資格樣本'}`;
  }
  function referenceDraft(request) {
    return mutate(s => { if (s.comparison.platform !== 'pc') return;
      s.reference_draft = clone(request); s.references = null; s.reference_skip = null; });
  }
  function chooseReferences(result, ids) {
    return mutate(s => {
      if (s.comparison.platform !== 'pc') return;
      s.references = {evidence: clone(result), selected_ids: [...new Set(ids)].filter(id => result.rows.some(r => String(r.steam_id) === id)).slice(0, 5)};
      s.reference_draft = clone(result.request); s.reference_skip = null;
    });
  }
  function saveDraft(draft) { return mutate(s => {s.draft = clone(draft); s.budget = null;}); }
  function saveBudget(result, context) { return mutate(s => {s.budget = clone(result); s.context_note = '';}, context); }
  function clear() {
    try {sessionStorage.removeItem(KEY); storageError = ''; render(); return true;}
    catch (error) {storageError = `未能清除規劃：${error.message}`; render(); return false;}
  }
  function mount(currentPage) {
    page = currentPage;
    const host = element('section', undefined, 'workflow-panel'); host.id = 'workflow-panel';
    host.setAttribute('aria-label', '目前規劃及步驟');
    document.querySelector('.intro').after(host); render();
  }
  function render() {
    const host = document.getElementById('workflow-panel'); if (!host) return;
    const state = read(); host.replaceChildren();
    host.append(element('strong', state ? describe(state) : '從歷史比較建立你的規劃'));
    const nav = element('nav', undefined, 'workflow-steps'); nav.setAttribute('aria-label', '規劃流程');
    const steps = [['comparison', '/', '1 歷史市場比較'], ['references', '/revenue#reference-panel', '2 相近 Steam 遊戲'],
      ['budget', '/planning#budget-section', '3 成本預算'], ['summary', '/plan', '4 規劃摘要']];
    steps.forEach(([key, href, label]) => {
      if (key === 'references' && state?.comparison.platform === 'mobile') {nav.append(element('span', '2 Android 相近遊戲暫未提供', 'workflow-unavailable')); return;}
      const a = element('a', label); a.href = href; if (key === page) a.setAttribute('aria-current', 'step'); nav.append(a);
    });
    host.append(nav, element('p', state ? '這是你保存的規劃情境。各頁可來回查看；歷史資料、參考作品與個人預算仍分開解讀。' : '比較後選擇條件 A 或 B，即可帶到參考作品及預算。也可直接使用各分析頁。', 'fine'));
    if (state?.context_note) host.append(element('p', state.context_note, 'sample-warning'));
    host.append(element('p', '規劃暫存在此瀏覽器分頁；關閉前請匯出摘要。沒有自動同步至伺服器。', 'fine'));
    if (storageError) host.append(element('p', storageError, 'sample-warning'));
  }
  async function sourceChecks(state) {
    const issues = [], checked = [];
    const get = async path => {const response = await fetch(path); if (!response.ok) throw new Error('資料服務未能回應'); return response.json();};
    try {
      const data = await get('/api/options'), active = data.platforms[state.comparison.platform];
      if (active.version_id !== state.comparison.version_id) issues.push('主頁資料版本已切換，請重新比較並選擇規劃條件。');
      else checked.push('歷史比較版本一致');
    } catch (_) {issues.push('無法核對歷史比較版本，請確認程式仍在運行後重試。');}
    if (state.references) {
      try {
        const data = await get('/api/revenue/metadata');
        if (JSON.stringify(data.metadata) !== JSON.stringify(state.references.evidence.metadata)) issues.push('相近遊戲資料已更新，請重新搜尋及選取作品。');
        else checked.push('Steam 參考資料版本一致');
      } catch (_) {issues.push('無法核對相近遊戲資料，請恢復資料服務後重試。');}
    }
    if (state.budget?.fee_reference) {
      try {
        const data = await get('/api/planning/fees');
        if (data.metadata.revision !== state.budget.fee_reference.metadata.revision) issues.push('工具費用資料已更新，請重新選取及計算預算。');
        else checked.push('已保存的費用參考版本一致');
      } catch (_) {issues.push('無法核對預算所用的費用資料，請恢復資料服務後重試。');}
    }
    return {checked_at_utc: new Date().toISOString(), issues, checked};
  }
  function bundle(state, checks) {
    const missing = [];
    if (state.comparison.platform === 'pc' && !state.references?.selected_ids.length && !state.reference_skip) missing.push('Steam 參考作品或略過原因');
    if (!state.budget) missing.push('已計算的預算');
    const refs = state.references;
    return {schema_version: 'game_planning_summary_v1', exported_at_utc: new Date().toISOString(),
      context_id: state.context_id, name: state.name, decision_notes: state.notes,
      completion: {complete: missing.length === 0 && checks.issues.length === 0, missing}, source_checks: checks,
      selected_condition: state.choice, historical_comparison: clone(state.comparison),
      reference_status: state.comparison.platform === 'mobile' ? 'not_available_for_android' : refs?.selected_ids.length ? 'selected' : state.reference_skip ? 'skipped_with_reason' : 'not_selected',
      reference_skip_reason: state.reference_skip,
      comparable_games: refs ? {...clone(refs.evidence), rows: refs.evidence.rows.filter(r => refs.selected_ids.includes(String(r.steam_id))),
        selection_count: refs.selected_ids.length, note: 'Rows are the user-selected subset of the retrieved results; returned_count describes the original search.'} : null,
      budget: state.budget ? clone(state.budget) : null,
      interpretation: ['Historical associations are not forecasts or causal effects.', 'Steam references come from a selected high-revenue sample, independent of the comparison snapshot.',
        'Budget figures are user assumptions and saved fee references, not inferred game costs. Reference prices and revenues are not used as net contribution.',
        'Snapshot years and outcome definitions differ across platforms; no cross-platform performance ranking is made.']};
  }
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json;charset=utf-8'}));
    const a = element('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  window.addEventListener('pageshow', event => {if (event.persisted) location.reload();});
  return {read, mutate, selectComparison, describe, referenceDraft, chooseReferences, saveDraft, saveBudget,
    clear, mount, render, sourceChecks, bundle, download, element};
})();
