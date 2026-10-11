"use strict";
let platforms = {}, platform = "pc", displayed = null, requestId = 0;
let mutationToken = "", versions = [], previewId = null, validation = null, managing = false;
const $ = (selector) => document.querySelector(selector);
const count = (n) => new Intl.NumberFormat("en").format(n);
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function invalidate(message = "條件已更新，請按比較以查看結果。") {
  requestId += 1;
  displayed = null;
  $("#results").hidden = true;
  $("#status").textContent = message;
  $("#compare").disabled = false;
}
function selectPlatform(value) {
  platform = value;
  invalidate("選擇兩組條件，或直接比較此版本的全部合資格樣本。");
  const spec = platforms[platform];
  document.querySelectorAll("[data-platform]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.platform === platform)));
  $("#snapshot").textContent = `${spec.name} · ${spec.source_name} · ${spec.snapshot}${spec.data_kind === "synthetic" ? "（人工示例）" : ""}`;
  $("#denominator").textContent = `${count(spec.row_count)} 筆${spec.sample_label}`;
  $("#scope").textContent = spec.scope;
  $("#caveat").textContent = spec.caveat;
  $("#import-platform-name").textContent = spec.name;
  $("#template-link").href = `/api/template?platform=${platform}`;
  $("#template-link").download = `${platform}_template_v1.csv`;
  $("#currency-label").hidden = platform !== "pc";
  $("#import-outcome").textContent = platform === "pc" ? "Outcome：估算 owners 上下界。不可填入收入、評論數或同時在線人數。" : "Outcome：Minimum Installs 下界。不可填入評分、收入或其他下載量定義。";
  clearPreview();
  refreshVersionChoices();
  for (const scenario of ["a", "b"]) {
    const container = $(`#filters-${scenario}`);
    container.replaceChildren();
    for (const field of spec.fields) {
      const label = node("label", field.label);
      const select = document.createElement("select");
      select.id = `${scenario}-${field.key}`;
      select.dataset.key = field.key;
      select.add(new Option("全部", ""));
      field.choices.forEach(choice => select.add(new Option(choice.label, choice.value)));
      select.addEventListener("change", () => invalidate());
      label.append(select);
      container.append(label);
    }
  }
}
function filters(scenario) {
  return Object.fromEntries([...document.querySelectorAll(`#filters-${scenario} select`)].map(select => [select.dataset.key, select.value]));
}
function render(result) {
  $("#outcome").textContent = result.metadata.outcome;
  const container = $("#result-cards");
  container.replaceChildren();
  for (const key of ["a", "b"]) {
    const scenario = result.scenarios[key];
    const card = node("article", undefined, "result-card");
    card.append(node("h3", `條件 ${key.toUpperCase()}`));
    const labels = Object.entries(scenario.filters).map(([fieldKey, value]) => {
      const field = result.metadata.fields.find(f => f.key === fieldKey);
      return `${field.label}：${field.choices.find(c => c.value === value).label}`;
    });
    card.append(node("p", labels.join(" · ") || `此版本全部${result.metadata.sample_label}`, "selected-filters"));
    const metric = node("p", count(scenario.total), "metric");
    metric.append(node("span", " 筆符合條件"));
    card.append(metric);
    if (scenario.status !== "available") card.append(node("p", scenario.status === "no_matches" ? "沒有符合條件的資料；未計算比例。可放寬篩選條件。" : "小樣本：分布容易受少數紀錄影響，請審慎解讀。", "sample-warning"));
    for (const tier of scenario.tiers) {
      const row = node("div", undefined, "tier");
      const heading = node("div", undefined, "tier-heading");
      heading.append(node("span", tier.label), node("strong", tier.percent === null ? "—" : `${tier.percent.toFixed(1)}%`));
      const bar = node("div", undefined, "bar");
      const fill = node("span", undefined, `fill ${key}`);
      fill.style.width = `${tier.percent ?? 0}%`;
      bar.append(fill);
      row.append(heading, bar, node("small", `${count(tier.count)} 筆`));
      card.append(row);
    }
    container.append(card);
  }
  $("#overlap").textContent = `兩組共有 ${count(result.overlap_count)} 筆重疊紀錄；本頁並非隨機對照實驗。百分比可能因四捨五入不合計為 100%。`;
  $("#results").hidden = false;
  $("#status").textContent = "比較完成。以下比例只描述已符合條件的歷史樣本。";
}
$("#compare-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const current = ++requestId;
  displayed = null;
  $("#results").hidden = true;
  $("#compare").disabled = true;
  $("#status").textContent = "正在比較…";
  try {
    const response = await fetch("/api/compare", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({platform, version_id: platforms[platform].version_id, a: filters("a"), b: filters("b")})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "無法載入結果");
    if (current !== requestId) return;
    displayed = result;
    render(result);
  } catch (error) {
    if (current === requestId) $("#status").textContent = `比較失敗：${error.message}。請確認啟動視窗仍開啟。`;
  } finally {
    if (current === requestId) $("#compare").disabled = managing;
  }
});
document.querySelectorAll("[data-platform]").forEach(button => button.addEventListener("click", () => {if (platforms[button.dataset.platform]) selectPlatform(button.dataset.platform);}));
document.querySelectorAll("[data-reset]").forEach(button => button.addEventListener("click", () => {document.querySelectorAll(`#filters-${button.dataset.reset} select`).forEach(select => select.value = ""); invalidate();}));
$("#export").addEventListener("click", () => {
  if (!displayed) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(displayed, null, 2)], {type: "application/json;charset=utf-8"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = `gamescope-${displayed.platform}-${displayed.version_id}-comparison.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
function clearPreview() {
  previewId = null; validation = null;
  $("#import-preview").hidden = true;
  $("#save-import").disabled = true;
  $("#import-status").textContent = "";
}
function refreshVersionChoices() {
  const select = $("#version-select");
  select.replaceChildren(new Option("原有研究 train 資料", "research_train_v1"));
  for (const v of versions.filter(v => v.metadata.platform === platform)) {
    select.add(new Option(`${v.metadata.source_name} · ${v.metadata.snapshot_date} · ${count(v.eligible_rows)} 筆${v.metadata.data_kind === "synthetic" ? " · 人工示例" : ""} · ${v.version_id.slice(-6)}`, v.version_id));
  }
  select.value = platforms[platform].version_id;
  select.disabled = managing;
  $("#activate-version").disabled = managing;
}
async function reloadVersions() {
  const response = await fetch("/api/versions");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "無法讀取版本");
  versions = data.versions;
  refreshVersionChoices();
}
function setManaging(value) {
  managing = value;
  document.querySelectorAll("#import-form input, #import-form select, #preview-import, #version-select, #activate-version, [data-platform]").forEach(e => e.disabled = value);
  $("#save-import").disabled = value || !previewId;
  $("#compare").disabled = value;
}
async function mutate(path, payload) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", "X-GameScope-Token": mutationToken}, body: JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "資料操作失敗");
  return data;
}
document.querySelectorAll("#import-form input, #import-form select").forEach(e => e.addEventListener("change", clearPreview));
$("#import-form").addEventListener("submit", async event => {
  event.preventDefault();
  clearPreview(); setManaging(true);
  $("#import-status").textContent = "正在讀取並驗證 CSV…";
  try {
    const file = $("#csv-file").files[0];
    if (!file || file.size > 64 * 1024 * 1024) throw new Error("請選擇不超過 64 MiB 的 CSV");
    const text = new TextDecoder("utf-8", {fatal: true, ignoreBOM: true}).decode(await file.arrayBuffer());
    const metadata = {platform, source_name: $("#source-name").value, source_url: $("#source-url").value,
      snapshot_date: $("#snapshot-date").value, data_kind: $("#data-kind").value,
      price_currency: platform === "pc" ? $("#price-currency").value : "per_row",
      outcome_definition: platform === "pc" ? "estimated_owner_interval" : "minimum_installs_lower_bound"};
    const data = await mutate("/api/import/preview", {metadata, csv_text: text});
    validation = data.validation; previewId = data.preview_id;
    const v = validation;
    $("#validation-summary").textContent = `共 ${count(v.total_rows)} 筆；合資格 ${count(v.eligible_rows)}；排除 ${count(v.excluded_rows)}；無效 ${count(v.invalid_rows)}。`;
    const details = $("#validation-details"); details.replaceChildren();
    for (const issue of v.issues) details.append(node("li", `紀錄 ${issue.row} · ${issue.field}：${issue.message}`));
    const names = {missing_title: "缺少名稱", missing_release_date: "缺少發佈日期", release_after_observation: "發佈日期晚於觀察日期", observation_uses_snapshot_proxy: "缺少逐列觀察日期，使用快照截至日期", missing_genres: "缺少遊戲類型", software_only_heuristic: "僅有軟件類型", unknown_developer: "開發者資料不明", nonpositive_or_missing_price: "Steam 價格非正數或缺失", demo_playtest_title_heuristic: "名稱符合 demo/playtest 排除規則", unknown_owners: "擁有者區間未知", owner_interval_straddles_tiers: "擁有者區間跨越分級", outside_game_categories: "不在 16 個遊戲類別內", unknown_installs: "安裝量下界未知", free_price_conflict_masked: "免費狀態與價格矛盾，改為未知", usd_price_unavailable: "USD 價格不可用", unknown_free: "免費狀態未知", unknown_ad_supported: "廣告狀態未知", unknown_in_app_purchases: "內購狀態未知"};
    for (const [group, label] of [[v.exclusions, "排除"], [v.warnings, "提示"]]) for (const [reason, n] of Object.entries(group)) details.append(node("li", `${label}：${names[reason] || reason}，${count(n)} 筆（原因可重疊）。`));
    if (v.issues_truncated) details.append(node("li", "只展示前 100 項格式錯誤；各欄位總數見下載報告。"));
    $("#import-preview").hidden = false;
    $("#import-status").textContent = v.can_import ? "驗證通過。請檢查來源、排除及提示後儲存；目前使用的資料未改動。" : "不能儲存：請修正錯誤，並確保至少一筆合資格資料。";
  } catch (error) { $("#import-status").textContent = `驗證未完成：${error.message}`; }
  finally { setManaging(false); }
});
$("#save-import").addEventListener("click", async () => {
  if (!previewId) return;
  setManaging(true);
  try {
    const data = await mutate("/api/import/commit", {preview_id: previewId});
    previewId = null;
    await reloadVersions();
    $("#version-select").value = data.version_id;
    $("#import-status").textContent = data.already_exists ? "相同來源及設定的版本已存在，沒有重複儲存。可在上方啟用。" : "版本已儲存，尚未啟用。請在上方按「啟用所選版本」。";
  } catch (error) { $("#import-status").textContent = `儲存未完成：${error.message}`; }
  finally { setManaging(false); }
});
$("#activate-version").addEventListener("click", async () => {
  invalidate("正在切換資料版本…"); setManaging(true);
  try {
    const data = await mutate("/api/activate", {platform, version_id: $("#version-select").value});
    platforms = data.platforms; selectPlatform(platform);
    $("#version-status").textContent = "版本已啟用，已清除舊篩選及比較結果。";
  } catch (error) { $("#version-status").textContent = `切換未完成：${error.message}`; }
  finally { setManaging(false); }
});
$("#export-validation").addEventListener("click", () => {
  if (!validation) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(validation, null, 2)], {type: "application/json;charset=utf-8"}));
  const a = document.createElement("a"); a.href = url; a.download = `validation-${platform}.json`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
fetch("/api/options").then(response => {if (!response.ok) throw new Error("資料載入失敗"); return response.json();}).then(async data => {platforms = data.platforms; mutationToken = data.mutation_token; selectPlatform("pc"); await reloadVersions();}).catch(error => {$("#status").textContent = `無法啟動：${error.message}。請參閱 DEMO_GUIDE.md。`;});
