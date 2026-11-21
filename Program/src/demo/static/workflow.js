'use strict';
// One planning context per browser tab. Evidence remains separate from assumptions.
window.PlanningFlow = (() => {
  const KEY = 'gamescope.planning.v1', LIMIT = 1500000;
  const WORKSPACE_KEY = 'gamescope.planning.workspace.v1';
  let storageError = '', workspaceError = '', page = '';
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
    const workspace=readWorkspace();
    return write({schema_version: 1, context_id: crypto.randomUUID(), name: (previous?previous.name:workspace.name)||'', notes: (previous?previous.notes:workspace.notes)||'',
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
  const emptyWorkspace = () => ({schema_version:1, name:'', notes:'', findings:[], budget_scenarios:{a:null,b:null}, updated_at_utc:null});
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const canonical = value => JSON.stringify(value, (_, v) => object(v) ? Object.fromEntries(Object.keys(v).sort().map(k => [k,v[k]])) : v);
  function validFinding(f) {
    return object(f) && f.schema_version === 'market_finding_v1' && f.analysis_schema_version === 'market_analysis_v2' &&
      typeof f.title === 'string' && f.title.trim().length > 0 && f.title.length <= 120 &&
      typeof f.note === 'string' && f.note.length <= 1200 &&
      ['pc','mobile','revenue'].includes(f.source?.id) && typeof f.source.version_id === 'string' &&
      object(f.filters) && Array.isArray(f.summary) && object(f.provenance?.input_hashes) &&
      typeof f.provenance?.label_taxonomy?.version === 'string' && Array.isArray(f.charts) && f.charts.length <= 2 &&
      f.charts.every(c => typeof c.id === 'string' && (!c.rows || (Array.isArray(c.rows) && c.rows.length <= 40)) && !c.points && !c.outliers && (c.rows||[]).every(r=>!r.outliers)) &&
      (!f.comparison || (Number.isInteger(f.comparison.selected?.n) && Number.isInteger(f.comparison.baseline?.n))) &&
      JSON.stringify(f).length <= 150000;
  }
  function validBudget(b) {
    return object(b) && typeof b.currency === 'string' && b.request?.currency === b.currency &&
      typeof b.method_version === 'string' && Array.isArray(b.request?.team) && Array.isArray(b.delays) && b.delays.length === 3 &&
      [b.base,...b.delays].every(s=>object(s) && Number.isInteger(s.months) && Number.isFinite(s.cash_budget) && Number.isFinite(s.resource_budget) && object(s.components));
  }
  function readWorkspace() {
    try {
      const raw = sessionStorage.getItem(WORKSPACE_KEY); if (!raw) return {...emptyWorkspace(),error:''};
      if (raw.length > LIMIT) throw new Error('資料超出儲存上限');
      const s = JSON.parse(raw);
      if (s.schema_version !== 1 || typeof s.name !== 'string' || typeof s.notes !== 'string' ||
          !Array.isArray(s.findings) || s.findings.length > 5 || !s.findings.every(f=>typeof f.id === 'string' && validFinding(f)) ||
          !object(s.budget_scenarios) || !['a','b'].every(k=>s.budget_scenarios[k] === null ||
            (typeof s.budget_scenarios[k]?.name === 'string' && validBudget(s.budget_scenarios[k]?.budget) &&
             object(s.budget_scenarios[k]?.draft?.fields) && Array.isArray(s.budget_scenarios[k]?.draft?.team)))) throw new Error('格式不相容');
      return {...s,error:''};
    } catch(error) {workspaceError = `無法讀取分析依據／預算方案：${error.message}。請先匯出可用資料或明確清除後重建。`;return {...emptyWorkspace(),error:workspaceError};}
  }
  function writeWorkspace(s) {
    try {
      const next=clone(s);delete next.error;next.updated_at_utc=new Date().toISOString();
      const raw=JSON.stringify(next);if(raw.length>LIMIT)throw new Error('儲存空間上限；請移除不需要的依據後重試');
      sessionStorage.setItem(WORKSPACE_KEY,raw);workspaceError='';render();
      window.dispatchEvent(new CustomEvent('planning-workspace-change'));return true;
    } catch(error) {workspaceError=`無法保存分析依據／預算方案：${error.message}。原有記錄未被替換。`;render();return false;}
  }
  function findings() {const s=readWorkspace();return {items:s.findings,error:s.error};}
  function addFinding(payload) {
    const s=readWorkspace();if(s.error)return {ok:false,error:s.error,code:'storage'};
    if(!validFinding(payload))return {ok:false,error:'分析依據格式不完整或過大；請重新分析並選擇較精簡的圖表。',code:'invalid'};
    const key=f=>canonical([f.source.id,f.source.version_id,f.filters,f.charts.map(c=>c.id).sort()]);
    if(s.findings.some(f=>key(f)===key(payload)))return {ok:false,error:'已有相同來源、條件及圖表的依據；如需更新，請先移除原記錄。',code:'duplicate'};
    if(s.findings.length>=5)return {ok:false,error:'最多保存 5 份分析依據；請先移除不需要的記錄。',code:'limit'};
    const id=crypto.randomUUID();s.findings.push({...clone(payload),id,saved_at_utc:new Date().toISOString()});
    return writeWorkspace(s)?{ok:true,id,error:''}:{ok:false,error:workspaceError,code:'storage'};
  }
  function removeFinding(id) {const s=readWorkspace();if(s.error)return {ok:false,error:s.error};s.findings=s.findings.filter(f=>f.id!==id);return writeWorkspace(s)?{ok:true,error:''}:{ok:false,error:workspaceError};}
  function budgetScenarios() {const s=readWorkspace();return {schema_version:1,slots:s.budget_scenarios,error:s.error};}
  function saveBudgetScenario(slot,name,budget,draft) {
    const s=readWorkspace();if(s.error)return false;
    if(!['a','b'].includes(slot)||typeof name!=='string'||!name.trim()||name.trim().length>80||!validBudget(budget)||
       !['budget_scenario_v1','budget_scenario_v2'].includes(budget.method_version)||!object(draft?.fields)||!Array.isArray(draft?.team)) {workspaceError='請先完成有效預算計算，並填寫 1–80 字的方案名稱。';return false;}
    const context=read();s.budget_scenarios[slot]={name:name.trim(),saved_at_utc:new Date().toISOString(),budget:clone(budget),draft:clone(draft),
      context_id:context?.context_id||null,platform:context?.comparison.platform||null,context_label:context?describe(context):'獨立預算假設，未指定歷史比較條件'};
    return writeWorkspace(s);
  }
  function removeBudgetScenario(slot) {const s=readWorkspace();if(s.error||!['a','b'].includes(slot))return false;s.budget_scenarios[slot]=null;return writeWorkspace(s);}
  function saveWorkspaceMeta(name,notes) {const s=readWorkspace();if(s.error)return false;s.name=String(name).slice(0,120);s.notes=String(notes).slice(0,2000);return writeWorkspace(s);}
  function storageMessage() {return workspaceError||storageError;}
  function clear() {
    try {sessionStorage.removeItem(KEY);sessionStorage.removeItem(WORKSPACE_KEY); storageError = '';workspaceError=''; render(); return true;}
    catch (error) {storageError = `未能清除規劃：${error.message}`; render(); return false;}
  }
  function mount(currentPage) {
    page = currentPage;
    const host = element('section', undefined, 'workflow-panel'); host.id = 'workflow-panel';
    host.setAttribute('aria-label', '目前規劃及步驟');
    document.querySelector('.intro').after(host); render();
  }
  function render() {
    const state = read(), workspace=readWorkspace(); window.GameShell?.updatePlanning(state);
    const host = document.getElementById('workflow-panel'); if (!host) return;
    host.replaceChildren();
    const savedCount=workspace.findings.length,scenarioCount=['a','b'].filter(k=>workspace.budget_scenarios[k]).length;
    host.append(element('strong', state ? describe(state) : savedCount||scenarioCount?`已保存 ${savedCount} 份分析依據、${scenarioCount} 個預算方案`:'從分析依據到開發規劃'));
    host.append(element('p', state ? '這是你保存的規劃情境。用左側步驟來回查看；歷史資料、參考作品與個人預算仍分開解讀。' : '可先保存市場分析發現或成本方案；要建立完整規劃，請從 Step 1 選擇條件 A 或 B。', 'fine'));
    if (state?.context_note) host.append(element('p', state.context_note, 'sample-warning'));
    const storage = element('details'); storage.append(element('summary', '規劃的保存方式'), element('p', '規劃暫存在此瀏覽器分頁；關閉前請匯出摘要。沒有自動同步至伺服器。', 'fine')); host.append(storage);
    if (storageError||workspaceError) host.append(element('p', storageError||workspaceError, 'sample-warning'));
  }
  async function legacySourceChecks(state,get) {
    const issues = [], checked = [];
    try {
      const data = await get('/api/options'), active = data.platforms[state.comparison.platform];
      if (active.version_id !== state.comparison.version_id) issues.push('主頁資料版本已切換，請重新比較並選擇規劃條件。');
      else if (['a', 'b'].some(scenario => Object.entries(state.comparison.scenarios[scenario].filters).some(([key, value]) =>
        value !== '' && !active.fields.some(field => field.key === key && field.choices.some(choice => choice.value === value))))) {
        issues.push('已保存比較含不支援的舊類型／標籤條件，請重新選擇玩法類型及其他來源標籤後比較。');
      } else checked.push('歷史比較版本及篩選條件一致');
    } catch (_) {issues.push('無法核對歷史比較版本，請確認程式仍在運行後重試。');}
    if (state.references) {
      try {
        const data = await get('/api/revenue/metadata');
        if (JSON.stringify(data.metadata) !== JSON.stringify(state.references.evidence.metadata)) issues.push('相近遊戲資料已更新，請重新搜尋及選取作品。');
        else if (data.options.reference_method_version !== state.references.evidence.method?.version) issues.push('相近遊戲配對方法已更新，請重新搜尋及選取作品。');
        else checked.push('Steam 參考資料及配對方法版本一致');
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
  async function workspaceChecks(workspace=readWorkspace(),get) {
    if(!get)get=async path=>{const response=await fetch(path);if(!response.ok)throw new Error('資料服務未能回應');return response.json();};
    const issues=[],checked=[],item_checks=[];let feeMetadata=null;
    if(workspace.error)issues.push(workspace.error);
    if(workspace.findings.length) {
      try {
        const data=await get('/api/market/options');
        for(const finding of workspace.findings) {
          const source=data.sources.find(s=>s.id===finding.source.id);let issue='';
          if(!source?.available)issue='資料來源暫時不可用';
          else if(source.version_id!==finding.source.version_id||canonical(source.input_hashes)!==canonical(finding.provenance.input_hashes))issue='資料版本或來源檔案已改變';
          else if(source.analysis_schema_version!==finding.analysis_schema_version||source.taxonomy_version!==finding.provenance.label_taxonomy.version||
                  (finding.comparison&&source.comparison_method_version!==finding.comparison.method_version))issue='分析或分類方法已更新';
          const message=issue?`分析依據「${finding.title}」：${issue}，請重新分析保存或移除舊依據。`:`分析依據「${finding.title}」來源及方法一致`;
          (issue?issues:checked).push(message);item_checks.push({id:finding.id,current:!issue,message});
        }
      } catch(_) {issues.push('無法核對市場分析依據的來源，請確認程式運行後重試。');}
    }
    const slots=workspace.budget_scenarios;
    for(const key of ['a','b'])if(slots[key]&&!['budget_scenario_v1','budget_scenario_v2'].includes(slots[key].budget.method_version))issues.push(`預算 ${key.toUpperCase()} 的計算方法已不受支援，請重新計算保存。`);
    if(['a','b'].some(k=>slots[k]?.budget.fee_reference)) {
      try {
        feeMetadata=(await get('/api/planning/fees')).metadata;
        for(const key of ['a','b'])if(slots[key]?.budget.fee_reference) {
          if(feeMetadata.revision!==slots[key].budget.fee_reference.metadata.revision)issues.push(`預算 ${key.toUpperCase()} 的費用參考已更新，請重新選取並計算，或移除該方案。`);
          else checked.push(`預算 ${key.toUpperCase()} 的費用來源版本一致`);
        }
      }catch(_){issues.push('無法核對已保存預算方案的費用參考；請恢復資料服務後重試。');}
    }
    if(slots.a&&slots.b&&slots.a.budget.currency!==slots.b.budget.currency)issues.push('預算 A／B 幣別不同，不能計算差額或匯出合併比較；請以相同幣別重新計算，或移除其中一個方案。');
    return {issues,checked,item_checks,feeMetadata,checked_at_utc:new Date().toISOString()};
  }
  async function sourceChecks(state,workspace=readWorkspace()) {
    const requests=new Map(),get=path=>{if(!requests.has(path))requests.set(path,fetch(path).then(r=>{if(!r.ok)throw new Error('資料服務未能回應');return r.json();}));return requests.get(path);};
    const [legacy,extra]=await Promise.all([state?legacySourceChecks(state,get):Promise.resolve({issues:[],checked:[]}),workspaceChecks(workspace,get)]);
    return {...extra,issues:[...legacy.issues,...extra.issues],checked:[...legacy.checked,...extra.checked]};
  }
  function bundle(state, checks, workspace=readWorkspace()) {
    const workspaceContent=workspace.findings.length||workspace.budget_scenarios.a||workspace.budget_scenarios.b;
    const extra={market_findings:clone(workspace.findings),budget_scenarios:clone(workspace.budget_scenarios),
      budget_scenario_comparison:window.BudgetScenarios?.compare(workspace.budget_scenarios,{feeMetadata:checks.feeMetadata,currentContextId:state?.context_id||null})||null,
      workspace_note:'Saved findings are source-labelled background evidence. Budget A/B are independent user assumptions, not automatically the chosen plan or predictions.'};
    if(!state)return {schema_version:'game_planning_summary_v2',exported_at_utc:new Date().toISOString(),name:workspace.name,decision_notes:workspace.notes,
      completion:{complete:false,missing:['歷史比較條件','已選規劃的預算']},source_checks:checks,context_id:null,selected_condition:null,historical_comparison:null,
      reference_status:'not_selected',comparable_games:null,budget:null,...extra};
    const missing = [];
    if (state.comparison.platform === 'pc' && !state.references?.selected_ids.length && !state.reference_skip) missing.push('Steam 參考作品或略過原因');
    if (!state.budget) missing.push('已計算的預算');
    const refs = state.references;
    return {schema_version: workspaceContent?'game_planning_summary_v2':'game_planning_summary_v1', exported_at_utc: new Date().toISOString(),
      context_id: state.context_id, name: state.name, decision_notes: state.notes,
      completion: {complete: missing.length === 0 && checks.issues.length === 0, missing}, source_checks: checks,
      selected_condition: state.choice, historical_comparison: clone(state.comparison),
      reference_status: state.comparison.platform === 'mobile' ? 'not_available_for_android' : refs?.selected_ids.length ? 'selected' : state.reference_skip ? 'skipped_with_reason' : 'not_selected',
      reference_skip_reason: state.reference_skip,
      comparable_games: refs ? {...clone(refs.evidence), rows: refs.evidence.rows.filter(r => refs.selected_ids.includes(String(r.steam_id))),
        selection_count: refs.selected_ids.length, note: 'Rows are the user-selected subset of the retrieved results; returned_count describes the original search.'} : null,
      budget: state.budget ? clone(state.budget) : null,...extra,
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
    clear, mount, render, sourceChecks, bundle, download, element,readWorkspace,findings,addFinding,removeFinding,budgetScenarios,saveBudgetScenario,removeBudgetScenario,saveWorkspaceMeta,workspaceChecks,storageMessage};
})();
