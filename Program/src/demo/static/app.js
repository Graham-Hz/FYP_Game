"use strict";
let platforms = {}, platform = "pc", displayed = null, requestId = 0;
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
  invalidate("選擇兩組條件，或直接比較全部訓練樣本。");
  const spec = platforms[platform];
  document.querySelectorAll("[data-platform]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.platform === platform)));
  $("#snapshot").textContent = `${spec.name} · 資料快照 ${spec.snapshot}`;
  $("#denominator").textContent = `${count(spec.train_count)} 筆訓練樣本`;
  $("#scope").textContent = spec.scope;
  $("#caveat").textContent = spec.caveat;
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
    card.append(node("p", labels.join(" · ") || "全部訓練樣本", "selected-filters"));
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
    const response = await fetch("/api/compare", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({platform, a: filters("a"), b: filters("b")})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "無法載入結果");
    if (current !== requestId) return;
    displayed = result;
    render(result);
  } catch (error) {
    if (current === requestId) $("#status").textContent = `比較失敗：${error.message}。請確認啟動視窗仍開啟。`;
  } finally {
    if (current === requestId) $("#compare").disabled = false;
  }
});
document.querySelectorAll("[data-platform]").forEach(button => button.addEventListener("click", () => {if (platforms[button.dataset.platform]) selectPlatform(button.dataset.platform);}));
document.querySelectorAll("[data-reset]").forEach(button => button.addEventListener("click", () => {document.querySelectorAll(`#filters-${button.dataset.reset} select`).forEach(select => select.value = ""); invalidate();}));
$("#export").addEventListener("click", () => {
  if (!displayed) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(displayed, null, 2)], {type: "application/json;charset=utf-8"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = `gamescope-${displayed.platform}-train-comparison.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
fetch("/api/options").then(response => {if (!response.ok) throw new Error("資料載入失敗"); return response.json();}).then(data => {platforms = data.platforms; selectPlatform("pc");}).catch(error => {$("#status").textContent = `無法啟動：${error.message}。請參閱 DEMO_GUIDE.md。`;});
