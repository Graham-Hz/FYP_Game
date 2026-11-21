'use strict';
(() => {
  const $ = selector => document.querySelector(selector);
  const make = (tag, text, cls) => {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const count = value => new Intl.NumberFormat('en').format(value ?? 0);
  const profileKey = platform => `gamescope.guided-import.profile.v1.${platform}`;
  const optionControls = {delimiter:'#format-delimiter',date_format:'#format-date',list_separator:'#format-list',boolean_format:'#format-boolean',number_format:'#format-number',id_policy:'#format-id'};
  const reasonLabels = {
    local_row_id_not_platform_identity:'使用本檔案內部行號，並非平台遊戲 ID',
    observation_uses_snapshot_proxy:'缺少觀察日期，使用你填寫的快照日期',
    release_after_observation_masked:'發售日期晚於觀察日期，未用於時間分析',
    missing_release_date:'缺少發售日期',missing_title:'缺少遊戲名稱',
    no_recognized_gameplay_genre:'沒有本項目可識別的玩法類型',missing_genres:'沒有遊戲類型',
    unknown_owners:'沒有可用的擁有者區間',unknown_installs:'沒有可用的安裝量下限',
    owner_interval_straddles_tiers:'擁有者區間跨越分層界線，可探索但不參與分層比較',
    unknown_game_category_masked:'未識別 Google Play 遊戲類別，未用於類別比較',
    free_price_conflict_masked:'免費標記與價格矛盾，免費狀態設為未知',
    usd_price_unavailable:'沒有已確認的美元價格，未用於 Android 價格圖',
    software_only_heuristic:'類型只包含軟件標籤',no_usable_analysis_fields:'沒有可用的分析欄位',
    unknown_developer:'缺少可用的開發者資料',nonpositive_or_missing_price:'價格為零或未提供',
    demo_playtest_title_heuristic:'名稱符合 Demo／Playtest 排除規則',
    outside_game_categories:'不屬於既定的 Google Play 遊戲類別',release_after_observation:'發售日期晚於觀察日期',
  };
  let token='', busy=false, revision=0, csvText='', inspection=null, previewId=null, validation=null;
  let versions=[], active={pc:'research_train_v1',mobile:'research_train_v1'};
  const platform = () => $('#guided-platform').value;
  const status = (text, state='') => {$('#guided-status').textContent=text;$('#guided-status').dataset.state=state;};
  function controls() {
    $('#source-fields').disabled=busy;
    $('#mapping-fields').disabled=busy;
    $('#version-fields').disabled=busy;
    $('#inspect-csv').disabled=busy||!token||!$('#guided-file').files.length;
    $('#preview-guided').disabled=busy||!inspection||!token;
    $('#save-guided').disabled=busy||!previewId;
    $('#download-validation').disabled=busy||!validation;
    $('#guided-version').disabled=busy||!token;
    $('#activate-guided').disabled=busy||!token||!$('#guided-version').value;
    $('#reuse-profile').disabled=busy||!inspection||!readProfile();
    $('#save-profile').disabled=busy||!inspection;
  }
  function setBusy(value) {busy=value;$('#guided-form').setAttribute('aria-busy',String(value));controls();}
  function invalidate({clearInspection=false, message=true}={}) {
    revision++;previewId=null;validation=null;$('#guided-preview').hidden=true;
    if(clearInspection){inspection=null;csvText='';$('#mapping-fields').hidden=true;$('#field-mapping').replaceChildren();}
    if(message)status('設定已變更，請重新驗證及預覽。');
    controls();
  }
  async function request(path, payload) {
    const settings=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-GameScope-Token':token},body:JSON.stringify(payload)};
    const response=await fetch(path,settings);
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'資料操作未完成。');
    return data;
  }
  function metadata() {
    return {platform:platform(),source_name:$('#guided-source').value.trim(),source_url:$('#guided-url').value.trim(),snapshot_date:$('#guided-date').value,
      outcome_definition:platform()==='pc'?'estimated_owner_interval':'minimum_installs_lower_bound',data_kind:$('#guided-kind').value,
      price_currency:platform()==='pc'?($('#guided-currency').value.trim().toLowerCase()==='unknown'?'unknown':$('#guided-currency').value.trim().toUpperCase()):'per_row'};
  }
  function mapping() {return Object.fromEntries([...document.querySelectorAll('[data-map-field]')].filter(e=>e.value).map(e=>[e.dataset.mapField,e.value]));}
  function options() {return {...Object.fromEntries(Object.entries(optionControls).map(([key,id])=>[key,$(id).value])),confirmed_semantics:$('#confirm-semantics').checked};}
  function readable(value) {return value===null||value===undefined?'—':typeof value==='object'?JSON.stringify(value):String(value);}
  function sample(container, rows, headers) {
    container.replaceChildren();
    if(!Array.isArray(rows)||!rows.length){container.append(make('p','沒有可顯示的資料範例。','fine'));return;}
    const names=headers||Object.keys(rows[0]);
    const table=make('table'),head=make('thead'),tr=make('tr'),body=make('tbody');
    names.forEach(name=>{const th=make('th',name);th.scope='col';tr.append(th);});head.append(tr);
    for(const row of rows.slice(0,5)){const line=make('tr');names.forEach((name,index)=>line.append(make('td',readable(Array.isArray(row)?row[index]:row[name]))));body.append(line);}
    table.append(head,body);container.append(table);
  }
  function showUnmapped() {
    if(!inspection)return;
    const used=new Set(Object.values(mapping()));
    const unused=inspection.headers.filter(h=>!used.has(h));
    $('#unmapped-columns').textContent=unused.length?`未用於分析的欄位：${unused.join('、')}。原始檔案仍會完整保存。`:'所有來源欄位均已對照。';
  }
  function showMapping(data) {
    const container=$('#field-mapping');container.replaceChildren();
    for(const field of data.fields){
      const label=make('label'),heading=make('span',field.label),code=make('code',field.id);
      heading.append(code);label.append(heading);
      const select=make('select');select.id=`map-${field.id}`;select.dataset.mapField=field.id;select.setAttribute('aria-label',field.label);
      select.add(new Option(field.id==='title'?'請選擇遊戲名稱欄位':'未提供／不使用',''));
      data.headers.forEach(header=>select.add(new Option(header,header)));
      if(data.suggestions[field.id]&&data.headers.includes(data.suggestions[field.id]))select.value=data.suggestions[field.id];
      if(field.id==='title')select.required=true;
      label.append(select,make('small',field.description||''));container.append(label);
    }
    $('#format-delimiter').value=data.delimiter;
    sample($('#raw-sample'),data.sample,data.headers);
    $('#mapping-fields').hidden=false;
    $('#confirm-semantics').checked=false;
    showUnmapped();profileMessage();updateMeaning();
  }
  function updateMeaning() {
    $('#guided-currency-label').hidden=platform()!=='pc';
    $('#metric-meaning').textContent=platform()==='pc'
      ?'Steam 數量欄位只接受「估計擁有者人數」的下限與上限，兩欄必須成對。不可用售出份數、評論數、下載次數或營收代替。價格是資料快照的觀察值。'
      :'Android 數量欄位只接受來源定義的「累積安裝量下限」。不可把不明含義的 Downloads、精確銷量或營收當成安裝下限。價格貨幣由每行 currency 指明；目前價格圖只使用 USD。';
  }
  function readProfile() {
    try{const item=JSON.parse(localStorage.getItem(profileKey(platform()))||'null');return item&&item.version===1&&item.platform===platform()&&item.mapping&&typeof item.mapping==='object'&&item.options&&typeof item.options==='object'?item:null;}catch{return null;}
  }
  function profileMessage() {
    const saved=readProfile();
    $('#profile-status').textContent=saved?'此瀏覽器已有這個平台的欄位對照；套用後仍需重新確認資料含義。':'可把這次對照保存在此瀏覽器，方便下次匯入同一來源格式。';
    controls();
  }
  function versionChoices(selected) {
    const select=$('#guided-version');select.replaceChildren(new Option('原有研究 train 資料','research_train_v1'));
    for(const v of versions.filter(v=>v.metadata.platform===platform())){
      const rows=v.exploration_rows===undefined?`${count(v.eligible_rows)} 筆比較樣本`:`${count(v.exploration_rows)} 筆探索／${count(v.eligible_rows)} 筆比較樣本`;
      select.add(new Option(`${v.metadata.source_name} · ${v.metadata.snapshot_date} · ${rows}${v.metadata.data_kind==='synthetic'?' · 人工示例':''} · ${v.version_id.slice(-6)}`,v.version_id));
    }
    select.value=selected||active[platform()];
    if(!select.value)select.value=active[platform()];
    const current=versions.find(v=>v.version_id===active[platform()]);
    $('#guided-active').textContent=`目前啟用：${current?`${current.metadata.source_name} · ${current.metadata.snapshot_date}`:'原有研究 train 資料'}。儲存版本不會自動切換。`;
    controls();
  }
  async function reloadVersions(selected) {const data=await request('/api/versions');versions=data.versions;active=data.active;versionChoices(selected);}
  function renderReadiness(items) {
    const container=$('#readiness-table');container.replaceChildren();
    if(!Array.isArray(items)||!items.length){container.append(make('p','此預覽未提供分析可用性明細。','fine'));return;}
    const table=make('table'),head=make('thead'),heading=make('tr'),body=make('tbody');
    ['分析','可用紀錄','欄位是否足夠'].forEach(text=>{const th=make('th',text);th.scope='col';heading.append(th);});head.append(heading);
    for(const item of items){const row=make('tr'),state=String(item.status||'unavailable');
      const ready=state==='available',limited=['limited','partial'].includes(state);
      const label=ready?'欄位齊備':limited?'部分紀錄齊備':'資料不足';
      row.append(make('td',item.label||item.id),make('td',`${count(item.usable_rows)} / ${count(item.total_rows)}`));
      const info=make('td');info.append(make('strong',label,ready?'import-ready':limited?'import-limited':'import-unavailable'),make('div',item.reason||''));row.append(info);body.append(row);
    }
    table.append(head,body);container.append(table);
  }
  function renderValidation(data) {
    validation=data.validation;previewId=data.preview_id;
    const s=validation,box=$('#preview-counts');box.replaceChildren();
    for(const [label,value] of [['原始紀錄',s.total_rows],['可用於市場探索',s.exploration_rows],['符合嚴格規劃比較',s.eligible_rows]]){const card=make('div',undefined,'import-count');card.append(make('span',label),make('strong',count(value)));box.append(card);}
    $('#preview-explanation').textContent='下表核對每種分析所需的欄位；實際圖表還會檢查樣本數及數值是否有足夠變化。缺少開發者或發售日期，不會單獨阻止其他可用分析。規劃比較另用較嚴格的資格，數量可能較少或為零。欄位齊備不代表資料具有市場代表性。';
    renderReadiness(s.analysis_readiness);
    const issues=$('#issue-list');issues.replaceChildren();
    for(const issue of (s.issues||[])){const field=inspection?.fields.find(f=>f.id===issue.field)?.label||issue.field;issues.append(make('li',`第 ${issue.row} 行 · ${field}：${issue.message}`));}
    for(const [reason,n] of Object.entries(s.warnings||{}))issues.append(make('li',`${reasonLabels[reason]||reason}：${count(n)} 筆`));
    for(const [reason,n] of Object.entries(s.comparison_exclusions||{}))issues.append(make('li',`規劃比較未納入：${reasonLabels[reason]||reason}（${count(n)} 筆）。`));
    if(Object.keys(s.comparison_exclusions||{}).length)issues.append(make('li','同一筆資料可以有多個未納入原因；以上次數不能直接相加。'));
    if(s.excluded_rows)issues.append(make('li',`${count(s.excluded_rows)} 筆未納入市場探索；完整原因保存在逐行紀錄。`));
    if(s.issues_truncated)issues.append(make('li','只顯示前部分錯誤；完整錯誤數請查看驗證報告。'));
    if(!issues.children.length)issues.append(make('li','沒有格式錯誤；來源真實性及代表性仍需由你核對。'));
    $('#preview-issues-title').textContent=`檢查提示與錯誤${s.error_count?`（${count(s.error_count)} 項錯誤）`:''}`;
    $('#preview-issues').open=!!s.error_count;
    sample($('#normalized-sample'),s.sample||[]);
    $('#guided-preview').hidden=false;
    status(s.can_import?'驗證通過。請查看可用分析，再儲存版本。':'未能儲存：請查看錯誤或補充可用資料，然後重新驗證。',s.can_import?'success':'error');
    controls();
  }
  $('#guided-form').addEventListener('input', event=>{
    if(event.target.id==='guided-file')return;
    invalidate();
    if(event.target.id!=='confirm-semantics')$('#confirm-semantics').checked=false;
  });
  $('#guided-form').addEventListener('change',event=>{
    if(event.target.id==='guided-file'||event.target.id==='guided-platform'){
      invalidate({clearInspection:true,message:false});$('#confirm-semantics').checked=false;
      updateMeaning();versionChoices();$('#activation-status').textContent='';
      status($('#guided-file').files.length?'已選擇檔案。請按「讀取欄位」。':'選擇平台及 CSV，然後讀取欄位。');
    }else{invalidate();if(event.target.id!=='confirm-semantics')$('#confirm-semantics').checked=false;showUnmapped();}
  });
  $('#inspect-csv').addEventListener('click',async()=>{
    if(busy)return;const file=$('#guided-file').files[0];if(!file)return;
    invalidate({clearInspection:true,message:false});const current=revision;setBusy(true);status('正在讀取欄位與資料範例…');
    try{
      if(!file.size||file.size>64*1024*1024)throw new Error('CSV 必須非空且不超過 64 MiB。');
      let text;try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());}catch{throw new Error('檔案不是有效 UTF-8。請以 UTF-8 CSV 格式另存。');}
      const data=await request('/api/import/inspect',{csv_text:text,platform:platform()});
      if(current!==revision)return;
      csvText=text;inspection=data;showMapping(data);
      status('欄位已讀取。請核對對照建議、資料格式與數字定義，再驗證。');
    }catch(error){if(current===revision)status(`未能讀取：${error.message}`,'error');}finally{setBusy(false);}
  });
  $('#guided-form').addEventListener('submit',async event=>{
    event.preventDefault();if(busy||!inspection)return;
    if(!$('#guided-form').reportValidity())return;
    invalidate({message:false});const current=revision;setBusy(true);status('正在驗證資料，計算各分析的可用紀錄…');
    try{const result=await request('/api/import/guided-preview',{csv_text:csvText,metadata:metadata(),mapping:mapping(),options:options()});if(current===revision)renderValidation(result);}
    catch(error){if(current===revision)status(`驗證未完成：${error.message}`,'error');}finally{setBusy(false);}
  });
  $('#save-profile').addEventListener('click',()=>{
    if(!inspection||busy)return;
    try{localStorage.setItem(profileKey(platform()),JSON.stringify({version:1,platform:platform(),mapping:mapping(),options:{...options(),confirmed_semantics:false}}));profileMessage();$('#profile-status').textContent='對照已保存在此瀏覽器；下次讀取檔案後可明確選擇套用。';}
    catch{$('#profile-status').textContent='此瀏覽器未能保存設定；本次仍可繼續匯入。';}
  });
  $('#reuse-profile').addEventListener('click',()=>{
    const saved=readProfile();if(!saved||!inspection||busy)return;
    const missing=Object.values(saved.mapping).filter(value=>typeof value!=='string'||!inspection.headers.includes(value));
    if(missing.length){$('#profile-status').textContent=`這份 CSV 缺少已保存的欄位：${missing.map(readable).join('、')}。未套用，請自行對照。`;return;}
    for(const [key,id] of Object.entries(optionControls))if(![...$(id).options].some(o=>o.value===saved.options[key])){$('#profile-status').textContent='已保存的格式設定不相容，請重新設定。';return;}
    invalidate();
    for(const select of document.querySelectorAll('[data-map-field]'))select.value=saved.mapping[select.dataset.mapField]||'';
    for(const [key,id] of Object.entries(optionControls))$(id).value=saved.options[key];
    $('#confirm-semantics').checked=false;showUnmapped();
    $('#profile-status').textContent='已套用欄位與格式設定。請重新核對資料含義，然後勾選確認。';
  });
  $('#save-guided').addEventListener('click',async()=>{
    if(busy||!previewId)return;setBusy(true);status('正在儲存已驗證版本…');
    try{const result=await request('/api/import/commit',{preview_id:previewId});previewId=null;await reloadVersions(result.version_id);status(result.already_exists?'相同資料與設定的版本已存在。已選取該版本，可在下方啟用。':'版本已儲存，尚未啟用。請在下方按「啟用所選版本」。','success');$('#version-heading').scrollIntoView({behavior:'smooth',block:'center'});}
    catch(error){status(`儲存未完成：${error.message}`,'error');}finally{setBusy(false);}
  });
  $('#activate-guided').addEventListener('click',async()=>{
    if(busy)return;setBusy(true);$('#activation-status').textContent='正在啟用所選版本…';
    try{const result=await request('/api/activate',{platform:platform(),version_id:$('#guided-version').value});active=result.active;await reloadVersions();$('#activation-status').textContent='已啟用。前往市場分析即可查看此版本的資料與可用圖表。';}
    catch(error){$('#activation-status').textContent=`啟用未完成：${error.message}`;}finally{setBusy(false);}
  });
  $('#download-validation').addEventListener('click',()=>{
    if(!validation)return;const url=URL.createObjectURL(new Blob([JSON.stringify(validation,null,2)],{type:'application/json'}));
    const link=make('a');link.href=url;link.download=`${platform()}_guided_import_validation.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('#guided-version').addEventListener('change',()=>{$('#activation-status').textContent='版本選擇已改變；按啟用才會切換資料。';controls();});
  async function initialize(){setBusy(true);try{const data=await request('/api/options');token=data.mutation_token;await reloadVersions();updateMeaning();status('選擇平台及 CSV，然後讀取欄位。');}catch(error){status(`無法連接資料服務：${error.message}。請重新啟動程式並重新整理頁面。`,'error');}finally{setBusy(false);}}
  initialize();
})();
