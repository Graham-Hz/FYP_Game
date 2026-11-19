"use strict";
const $ = s => document.querySelector(s);
const count = n => new Intl.NumberFormat("en").format(n);
const money = n => n === null ? "—" : new Intl.NumberFormat("en", {style: "currency", currency: "USD", maximumFractionDigits: 0}).format(n);
const pct = n => n === null ? "—" : `${(n * 100).toFixed(1)}%`;
let result = null, generation = 0, page = 0, optionsReady = false;
let referenceResult = null, referenceGeneration = 0;
const pageSize = 25;
function node(tag, text, className) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (className) e.className = className; return e; }
function invalidate() { generation++; result = null; $("#r-results").hidden = true; $("#r-status").textContent = "條件已改變，請按「更新分析」。"; $("#r-apply").disabled = false; }
function table(target, headers, rows) {
 const t = node("table"), head = node("thead"), tr = node("tr"), body = node("tbody");
 headers.forEach(h => {const th = node("th", h); th.scope = "col"; tr.append(th);}); head.append(tr); t.append(head, body);
 rows.forEach(row => {const line = node("tr"); row.forEach(value => {const td = node("td"); if (value instanceof Node) td.append(value); else td.textContent = value; line.append(td);}); body.append(line);});
 $(target).replaceChildren(t); if (!rows.length) $(target).append(node("p", "沒有符合條件的資料。", "fine"));
}
function bar(target, label, fraction, detail) {
 const row = node("div", undefined, "tier"), heading = node("div", undefined, "tier-heading"), track = node("div", undefined, "bar"), fill = node("span", undefined, "fill");
 heading.append(node("span", label), node("strong", detail)); fill.style.width = `${Math.max(0, Math.min(100, (fraction || 0) * 100))}%`; track.append(fill); row.append(heading, track); $(target).append(row);
}
function groupTable(target, groups) {
 table(target, ["組別", "遊戲數", "營收中位數 (USD)", "25%–75% 分位 (USD)"], groups.map(g => [g.label, `${count(g.count)}${g.small_sample ? "（小樣本）" : ""}`, money(g.median_revenue), `${money(g.q25)} – ${money(g.q75)}`]));
}
function gameTable() {
 if (!result) return;
 const rows = [...result.rows], sort = $("#r-sort").value;
 rows.sort(sort === "name" ? (a,b) => a.name.localeCompare(b.name) : sort === "price" ? (a,b) => a.price-b.price || b.revenue-a.revenue : (a,b) => b.revenue-a.revenue);
 const pages = Math.max(1, Math.ceil(rows.length/pageSize)); page = Math.min(page, pages-1);
 table("#r-games", ["遊戲", "來源發售日期", "觀察價格 (USD)", "估算營收 (USD)", "來源分類", "來源玩法／其他標籤"], rows.slice(page*pageSize,(page+1)*pageSize).map(r => {
  const link = node("a", r.name); link.href = `https://store.steampowered.com/app/${r.steam_id}/`; link.target = "_blank"; link.rel = "noopener";
  return [link, r.release_date, r.price.toFixed(2), money(r.revenue), r.publisher_class, r.genres.join(", ") || "未配對／缺少來源標籤"];
 }));
 $("#r-page").textContent = `${page+1} / ${pages} 頁 · ${count(rows.length)} 款`; $("#r-prev").disabled = page === 0; $("#r-next").disabled = page >= pages-1;
}
function render(data) {
 const s = data.summary; $("#r-metrics").replaceChildren();
 for (const [label,value] of [["樣本遊戲數",count(s.count)],["估算營收中位數",money(s.median_revenue)],["樣本估算營收總和",money(s.total_revenue)],["前 10% 遊戲的收入佔比",pct(s.top_decile_share)]]) {
  const card = node("article"); card.append(node("h3", label), node("p", value, "revenue-value")); $("#r-metrics").append(card);
 }
 const f = data.filters, mode = {positive:"正價格",zero:"零價格",all:"全部價格組別"}[f.mode];
 $("#r-context").textContent = `${mode} · ${f.genre || "全部來源玩法／其他標籤"} · ${f.publisher || "全部來源分類"}${f.q ? ` · 名稱：${f.q}` : ""}；${count(s.genre_matched_count)} / ${count(s.count)} 款有可用來源標籤。收入快照標示：2024-09-09；標籤快照：2025-03。`;
 $("#r-warning").hidden = s.count >= 30; $("#r-warning").textContent = s.count ? "少於 30 筆：中位數及分位數可能不穩定；超過此門檻亦不代表樣本具有代表性。" : "沒有符合條件的遊戲；沒有計算收入比例或中位數。";
 $("#r-distribution").replaceChildren(); data.distribution.forEach(d => bar("#r-distribution", d.label, s.count ? d.count/s.count : null, `${count(d.count)} 款 · ${pct(s.count ? d.count/s.count : null)}`));
 $("#r-concentration").replaceChildren(); bar("#r-concentration", `收入最高的 ${count(s.top_decile_count)} 款`, s.top_decile_share, pct(s.top_decile_share)); bar("#r-concentration", "其餘遊戲", s.top_decile_share === null ? null : 1-s.top_decile_share, pct(s.top_decile_share === null ? null : 1-s.top_decile_share));
 $("#r-concentration-note").textContent = "前 10% 遊戲數向上取整。佔比的分母是目前篩選樣本的估算收入總和，不是整個 Steam 市場。";
 groupTable("#r-price-table", data.by_price); groupTable("#r-genre-table", [...data.by_genre].sort((a,b) => b.median_revenue-a.median_revenue));
 page = 0; gameTable(); $("#r-results").hidden = false;
}
async function load() {
 const current = ++generation; result = null; $("#r-results").hidden = true; $("#r-apply").disabled = true; $("#r-status").textContent = "正在分析…";
 const params = new URLSearchParams({mode:$("#r-mode").value, genre:$("#r-genre").value, publisher:$("#r-publisher").value, q:$("#r-search").value.trim()});
 try {
  const response = await fetch(`/api/revenue?${params}`), data = await response.json(); if (!response.ok) throw new Error(data.error || "無法載入資料"); if (current !== generation) return;
  if (!optionsReady) {
   for (const group of data.options.genre_groups) {
    const optgroup = document.createElement('optgroup'); optgroup.label = group.label;
    group.values.forEach(value => optgroup.append(new Option(value, value)));
    $('#r-genre').append(optgroup);
   }
   data.options.publishers.forEach(value => $('#r-publisher').add(new Option(value, value)));
   data.options.reference_genres.forEach(genre => {const label=node("label"), input=node("input"); input.type="checkbox"; input.value=genre; input.checked=genre==="Action"; input.addEventListener("change",invalidateReferences); label.append(input,document.createTextNode(genre)); $("#ref-genres").append(label);});
   $("#ref-submit").disabled=false; $("#ref-status").textContent="選擇條件後，按「尋找參考作品」。"; optionsReady=true;
   restoreReferenceContext(data.metadata, data.options.reference_method_version);
  }
  result = data; render(data); $("#r-status").textContent = "分析完成。所有數字只描述目前篩選的歷史樣本。";
 } catch(error) {if (current === generation) {$("#r-status").textContent = `載入失敗：${error.message}`; if(!optionsReady) $("#ref-status").textContent="參考資料未能載入；請查看下方資料錯誤。";}}
 finally {if (current === generation) $("#r-apply").disabled=false;}
}
$("#revenue-form").addEventListener("submit",e=>{e.preventDefault();load();});
["#r-mode","#r-genre","#r-publisher"].forEach(id=>$(id).addEventListener("change",invalidate)); $("#r-search").addEventListener("input",invalidate);
$("#r-reset").addEventListener("click",()=>{$("#revenue-form").reset();load();});
$("#r-sort").addEventListener("change",()=>{page=0;gameTable();}); $("#r-prev").addEventListener("click",()=>{page--;gameTable();}); $("#r-next").addEventListener("click",()=>{page++;gameTable();});
$("#r-export").addEventListener("click",()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:"application/json"}));const a=node("a");a.href=url;a.download="gamescope-steam-revenue.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
function invalidateReferences() {
 referenceGeneration++; referenceResult=null; $("#ref-results").hidden=true;
 $("#ref-submit").disabled=!optionsReady; $("#ref-factor").disabled=$("#ref-price").value!=="" && Number($("#ref-price").value)===0;
 $("#ref-status").textContent="構想已改變，請重新尋找參考作品。";
 if (window.PlanningFlow.read()?.comparison.platform === 'pc') {
  window.PlanningFlow.referenceDraft(referenceInputs()); updateReferenceSelection();
 }
}
function renderReferences(data) {
 const r=data.request, coverage=data.coverage, range=data.price_range;
 const rangeLabel=range.minimum===null ? "不限制觀察價格" : range.maximum===0 ? "只比較零價格作品" : `候選觀察價格約 US$${range.minimum.toFixed(2)}–${range.maximum.toFixed(2)}`;
 $("#ref-context").textContent=`${r.genres.join(" + ")} · 預計售價 US$${r.price.toFixed(2)} · ${rangeLabel}。${count(coverage.same_price_cohort_rows)} 款有可用玩法類型且屬同一價格組別；${count(data.candidate_count)} 款符合類型與價格條件，顯示 ${count(data.returned_count)} 款。`;
 $("#ref-warning").textContent=data.status==="no_matches" ? "沒有符合條件的作品；可調整類型或價格範圍。系統沒有以不相關作品補足數量。" : `${data.status==="fewer_than_requested" ? "符合條件的作品少於要求數量。" : ""}參考作品來自高營收選樣；不能代表一般遊戲的收入或成功機率。`;
 const planning = window.PlanningFlow.read(), selectable = planning?.comparison.platform === 'pc';
 const selected = planning?.references?.selected_ids || [];
 table("#ref-table",["作品", "共同玩法類型", "類型重合率", "觀察價格 (USD)", "售價差距 (USD)", "歷史估算營收 (USD)", ...(selectable ? ['加入規劃'] : [])], data.rows.map(r=>{
  const link=node("a",r.name);link.href=`https://store.steampowered.com/app/${r.steam_id}/`;link.target="_blank";link.rel="noopener";
  const row = [link,r.match.shared_genres.join(", "),`${pct(r.match.genre_similarity)} (${r.match.shared_count}/${r.match.union_count})`,r.price.toFixed(2),r.match.price_difference_usd.toFixed(2),money(r.revenue)];
  if (selectable) {
   const label = node('label', '保存'), input = node('input'); input.type = 'checkbox'; input.dataset.planGame = String(r.steam_id); input.checked = selected.includes(String(r.steam_id)); input.setAttribute('aria-label', `加入規劃：${r.name}`);
   input.addEventListener('change', () => {
    const ids = [...document.querySelectorAll('[data-plan-game]:checked')].map(e => e.dataset.planGame);
    if (ids.length > 5) {input.checked = false; $('#ref-selection-status').textContent = '最多選取五款；請先取消其他作品。'; return;}
    if (!window.PlanningFlow.chooseReferences(data, ids)) input.checked = !input.checked;
    updateReferenceSelection();
   }); label.prepend(input); row.push(label);
  }
  return row;
 }));
 $("#ref-results").hidden=false; $("#ref-status").textContent="已依玩法類型及觀察價格選出參考作品。";
 updateReferenceSelection();
}
$("#reference-form").addEventListener("submit",async event=>{
 event.preventDefault(); const current=++referenceGeneration; referenceResult=null; $("#ref-results").hidden=true;
 const genres=[...document.querySelectorAll("#ref-genres input:checked")].map(input=>input.value);
 if(!genres.length){$("#ref-status").textContent="請至少選擇一個玩法類型。";return;}
 const payload={genres,price:Number($("#ref-price").value),limit:Number($("#ref-limit").value),price_factor:$("#ref-factor").value ? Number($("#ref-factor").value) : null};
 if (window.PlanningFlow.read()?.comparison.platform === 'pc') window.PlanningFlow.referenceDraft(payload);
 $("#ref-submit").disabled=true;$("#ref-status").textContent="正在尋找參考作品…";
 try {
  const response=await fetch("/api/references",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const data=await response.json();if(!response.ok)throw new Error(data.error || "無法載入參考作品");if(current!==referenceGeneration)return;
  referenceResult=data;renderReferences(data);
 }catch(error){if(current===referenceGeneration)$("#ref-status").textContent=`尋找失敗：${error.message}`;}
 finally{if(current===referenceGeneration)$("#ref-submit").disabled=false;}
});
["#ref-price","#ref-factor","#ref-limit"].forEach(id=>$(id).addEventListener("input",invalidateReferences));
$("#ref-export").addEventListener("click",()=>{if(!referenceResult)return;const url=URL.createObjectURL(new Blob([JSON.stringify(referenceResult,null,2)],{type:"application/json"}));const a=node("a");a.href=url;a.download="gamescope-reference-games.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
function referenceInputs() {
 return {genres: [...document.querySelectorAll('#ref-genres input:checked')].map(e => e.value), price: $('#ref-price').value,
  limit: Number($('#ref-limit').value), price_factor: $('#ref-factor').value ? Number($('#ref-factor').value) : null};
}
function updateReferenceSelection() {
 const s = window.PlanningFlow.read(), active = s?.comparison.platform === 'pc';
 $('#ref-flow-actions').hidden = !active;
 if (active) $('#ref-selection-status').textContent = `已保存 ${s.references?.selected_ids.length || 0} / 5 款。選取後可繼續預算；更改搜尋條件會清除舊選取。`;
}
function restoreReferenceContext(metadata, methodVersion) {
 let s = window.PlanningFlow.read(); updateReferenceSelection(); if (!s) return;
 $('#reference-panel').open = true;
 if (s.comparison.platform !== 'pc') {$('#ref-flow-note').textContent = '目前規劃是 Android。此處可獨立探索 Steam，但不會把 Steam 作品加入 Android 規劃。請直接繼續成本預算。'; return;}
 let staleNote = '', staleReferences = false;
 if (s.references && (JSON.stringify(s.references.evidence.metadata) !== JSON.stringify(metadata) ||
     s.references.evidence.method?.version !== methodVersion)) {
  staleReferences = true;
  const cleared = window.PlanningFlow.referenceDraft(s.reference_draft || s.references.evidence.request);
  s = window.PlanningFlow.read(); updateReferenceSelection();
  staleNote = cleared ? '資料或配對方法已更新，舊參考選擇已清除，請重新搜尋及選取作品；手動預算保留。' :
    '資料或配對方法已更新，舊參考選擇已失效；瀏覽器未能清除保存記錄，請恢復儲存功能後重新搜尋及選取。';
  if (!cleared) $('#ref-selection-status').textContent = '舊選擇已失效，不能作為目前的參考證據。';
 }
 const genre = s.comparison.scenarios[s.choice].filters.genre;
 const allowed = [...document.querySelectorAll('#ref-genres input')].map(e => e.value);
 const draft = s.reference_draft || {genres: allowed.includes(genre) ? [genre] : [], price: '', limit: 10, price_factor: 2};
 document.querySelectorAll('#ref-genres input').forEach(e => e.checked = draft.genres.includes(e.value));
 $('#ref-price').value = draft.price; $('#ref-limit').value = draft.limit; $('#ref-factor').value = draft.price_factor ?? '';
 $('#ref-factor').disabled = draft.price !== '' && Number(draft.price) === 0;
 $('#ref-skip-reason').value = s.reference_skip || '';
 $('#ref-flow-note').textContent = `已帶入 ${genre && allowed.includes(genre) ? `遊戲類型 ${genre}` : '規劃情境；請選擇可配對的玩法類型'}。其他比較條件不作自動配對；預計售價請自行填寫。參考作品來自獨立的 Steam 樣本，不隨主頁 CSV 版本切換。`;
 if (draft.genres.some(value => !allowed.includes(value))) staleNote += '舊草稿包含不支援的玩法類型；請按目前選項重新選擇，來源標籤不會自動變成玩法類型。';
 if (staleNote) $('#ref-status').textContent = staleNote;
 if (s.references && !staleReferences) {referenceResult = s.references.evidence; renderReferences(referenceResult);}
}
$('#ref-skip').addEventListener('click', () => {
 const reason = $('#ref-skip-reason').value.trim();
 if (!reason) {$('#ref-selection-status').textContent = '請簡述略過原因，例如沒有合適作品或樣本覆蓋不足。'; return;}
 if (window.PlanningFlow.mutate(s => {s.reference_skip = reason; s.references = null;})) location.href = '/planning#budget-section';
});
window.PlanningFlow.mount('references');
load();
