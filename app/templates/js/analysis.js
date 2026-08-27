let selectedBatches = [];
const charts = {};
const COLORS = ["#2563eb","#dc2626","#16a34a","#d97706","#7c3aed","#0891b2","#db2777","#ca8a04","#059669","#6366f1"];

function destroyChart(key) { if (charts[key]) { charts[key].destroy(); delete charts[key]; } }
function toast(msg, type) {
  type = type || "info";
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast " + type + " show";
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 3000);
}

async function loadBatchFilters() {
  const res = await fetch("/api/batches");
  const batches = await res.json();
  const container = document.getElementById("batch-filters");
  const params = new URLSearchParams(window.location.search);
  const preselected = params.get("batch_ids");
  if (!batches.length) { container.innerHTML = "<p>No data</p>"; return; }
  container.innerHTML = batches.map(b => {
    const sid = String(b.id);
    const active = preselected ? preselected.split(",").includes(sid) : true;
    if (active && !selectedBatches.includes(sid)) selectedBatches.push(sid);
    return `<span class="chip ${active?"active":""}" data-id="${sid}" onclick="toggleBatch('${sid}')">${b.date_label||""} ${b.time_period||""} <span class="count">#${sid}</span></span>`;
  }).join("");
  if (selectedBatches.length) refreshAnalysis();
}

window.toggleBatch = function(id) {
  const chip = document.querySelector(`.chip[data-id="${id}"]`);
  const idx = selectedBatches.indexOf(id);
  if (idx >= 0) { selectedBatches.splice(idx, 1); chip.classList.remove("active"); }
  else { selectedBatches.push(id); chip.classList.add("active"); }
};
window.selectAll = function() {
  document.querySelectorAll(".chip").forEach(c => c.classList.add("active"));
  selectedBatches = Array.from(document.querySelectorAll(".chip")).map(c => c.dataset.id);
};
window.clearAll = function() {
  document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
  selectedBatches = [];
};

window.refreshAnalysis = async function() {
  if (!selectedBatches.length) { toast("Select at least one batch", "info"); return; }
  const ids = selectedBatches.join(",");
  document.getElementById("page-subtitle").textContent = "Analyzing " + selectedBatches.length + " batch(es)";
  
  async function fetchJSON(url) { try { const r = await fetch(url); return await r.json(); } catch(e) { console.warn("fetch failed:", url); return null; } }
  
  const [stats, tsData, behDist, boxData, shadeData, heatData] = await Promise.all([
    fetchJSON("/api/analysis/stats?batch_ids=" + ids),
    fetchJSON("/api/analysis/timeseries?batch_ids=" + ids),
    fetchJSON("/api/analysis/behavior-distribution?batch_ids=" + ids),
    fetchJSON("/api/analysis/boxplot?batch_ids=" + ids),
    fetchJSON("/api/analysis/shade-stacked?batch_ids=" + ids),
    fetchJSON("/api/analysis/matrix-heatmap?batch_ids=" + ids),
  ]);
  
  if (stats) renderStats(stats);
  if (tsData && Object.keys(tsData).length) { renderTimeseries(tsData); renderChartWbgtCompare(tsData); }
  if (boxData && boxData.length) renderBoxplot(boxData);
  if (shadeData && shadeData.bins) renderShadeStacked(shadeData);
  if (behDist && Object.keys(behDist).length) renderBehaviorDistribution(behDist);
  if (heatData && heatData.cells) renderMatrixHeatmap(heatData);
};

function renderStats(s) {
  document.getElementById("astat-temp").textContent = (s.temp_min??"-") + " ~ " + (s.temp_max??"-");
  document.getElementById("astat-wbgt").textContent = (s.wbgt_min??"-") + " ~ " + (s.wbgt_max??"-");
  document.getElementById("astat-behavior").textContent = s.total_behaviors ?? 0;
  const wd = s.wbgt_distribution || {};
  const t = (wd.safe||0)+(wd.caution||0)+(wd.danger||0)+(wd.extreme||0);
  document.getElementById("astat-stress").textContent = t ? Math.round(((wd.danger||0)+(wd.extreme||0))/t*100)+"%" : "0%";
}

// Chart 1: Time series (unchanged)
function renderTimeseries(data) {
  destroyChart("timeseries");
  try {
    const ctx = document.getElementById("chart-timeseries").getContext("2d");
    const datasets = [];
    let ci = 0;
    for (const [label, records] of Object.entries(data)) {
      const temps = records.filter(r => r.temperature != null).map(r => ({ x: r.timestamp, y: r.temperature }));
      const wbgt = records.filter(r => r.wbgt != null).map(r => ({ x: r.timestamp, y: r.wbgt }));
      if (!temps.length && !wbgt.length) { ci++; continue; }
      const c = COLORS[ci % COLORS.length];
      if (temps.length) datasets.push({ label: label + " T", data: temps, borderColor: c, borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false });
      if (wbgt.length) datasets.push({ label: label + " WBGT", data: wbgt, borderColor: c, borderWidth: 2.5, pointRadius: 0, tension: 0.3, borderDash: [4,3], fill: false });
      ci++;
    }
    charts["timeseries"] = new Chart(ctx, {
      type: "line", data: { datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
        scales: { x: { type: "time", time: { tooltipFormat: "MM-dd HH:mm" }, title: { display: true, text: "Time" } }, y: { title: { display: true, text: "T / WBGT (C)" } } },
      },
    });
  } catch(e) { console.error("Timeseries error:", e); }
}

// Chart 2: Box plot (custom floating bar implementation)
function renderBoxplot(data) {
  destroyChart("temp-behavior");
  try {
    const ctx = document.getElementById("chart-temp-behavior").getContext("2d");
    if (!data.length) { ctx.canvas.parentElement.innerHTML = "<div class="empty-state"><p>No data</p></div>"; return; }
    
    const labels = data.map(d => d.behavior);
    
    // Use floating bar approach: IQR as bar, whiskers as error bars
    // Dataset 0: IQR (floating bar from Q1 to Q3)
    // Dataset 1: Min-Q1 whisker 
    // Dataset 2: Q3-Max whisker
    // Dataset 3: Median as scatter
    
    const iqrData = data.map(d => ({ x: d.behavior, y: [d.q1, d.q3] }));
    const whiskerLow = data.map(d => ({ x: d.behavior, y: [d.min, d.q1] }));
    const whiskerHigh = data.map(d => ({ x: d.behavior, y: [d.q3, d.max] }));
    const medianData = data.map(d => ({ x: d.behavior, y: d.median }));
    
    charts["temp-behavior"] = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "Min-Q1", data: data.map(d => [d.min, d.q1]), backgroundColor: "rgba(100,116,139,0.3)", borderColor: "rgba(100,116,139,0.6)", borderWidth: 1, borderRadius: 0 },
          { label: "IQR (Q1-Q3)", data: data.map(d => [d.q1, d.q3]), backgroundColor: COLORS.slice(0, data.length), borderColor: COLORS.slice(0, data.length), borderWidth: 1, borderRadius: 0 },
          { label: "Q3-Max", data: data.map(d => [d.q3, d.max]), backgroundColor: "rgba(100,116,139,0.3)", borderColor: "rgba(100,116,139,0.6)", borderWidth: 1, borderRadius: 0 },
          { label: "Median", data: data.map(d => d.median), type: "scatter", backgroundColor: "#fff", borderColor: "#1e293b", borderWidth: 2, pointRadius: 5, pointStyle: "rectRot" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } }, tooltip: { callbacks: { label: ctx => ctx.dataset.label + ": " + ctx.raw } } },
        scales: { x: { title: { display: true, text: "Behavior" } }, y: { title: { display: true, text: "Temperature (C)" }, beginAtZero: false } },
      },
    });
  } catch(e) { console.error("Boxplot error:", e); }
}

// Chart 3: Shade stacked bar
function renderShadeStacked(data) {
  destroyChart("shade");
  try {
    const ctx = document.getElementById("chart-shade").getContext("2d");
    if (!data || !data.bins) { ctx.canvas.parentElement.innerHTML = "<div class="empty-state"><p>No data</p></div>"; return; }
    
    const categories = ["全遮阴", "全遮荫", "半遮阴", "半遮荫", "曝晒"];
    const colors = ["#16a34a", "#22c55e", "#d97706", "#f59e0b", "#dc2626"];
    const datasets = [];
    categories.forEach((cat, i) => {
      const vals = data.bins.map(b => (data.data[b] && data.data[b][cat]) ? data.data[b][cat] : 0);
      if (vals.some(v => v > 0)) {
        datasets.push({ label: cat, data: vals, backgroundColor: colors[i % colors.length] });
      }
    });
    
    charts["shade"] = new Chart(ctx, {
      type: "bar", data: { labels: data.bins, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
        scales: { x: { stacked: true, title: { display: true, text: "Temperature Range (C)" } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "People Count" } } },
      },
    });
  } catch(e) { console.error("Shade stacked error:", e); }
}

// Chart 4: Behavior distribution stacked
function renderBehaviorDistribution(data) {
  destroyChart("behavior");
  try {
    const ctx = document.getElementById("chart-behavior").getContext("2d");
    const labels = [...new Set(Object.values(data).flatMap(v => Object.keys(v)))];
    if (!labels.length) { ctx.canvas.parentElement.innerHTML = "<div class="empty-state"><p>No data</p></div>"; return; }
    const datasets = [];
    let ci = 0;
    for (const [batch, counts] of Object.entries(data)) {
      datasets.push({ label: batch, data: labels.map(l => counts[l]||0), backgroundColor: COLORS[ci % COLORS.length] });
      ci++;
    }
    charts["behavior"] = new Chart(ctx, {
      type: "bar", data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
        scales: { x: { stacked: true, title: { display: true, text: "Behavior" } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "Count" } } },
      },
    });
  } catch(e) { console.error("Behavior chart error:", e); }
}

// Chart 5: WBGT compare bars
function renderChartWbgtCompare(tsData) {
  destroyChart("wbgt-compare");
  try {
    const ctx = document.getElementById("chart-wbgt-compare").getContext("2d");
    const labels = Object.keys(tsData);
    if (!labels.length) return;
    const means = labels.map(l => {
      const vals = (tsData[l]||[]).filter(r => r.wbgt != null).map(r => r.wbgt);
      return vals.length ? vals.reduce((a,b) => a+b, 0)/vals.length : 0;
    });
    charts["wbgt-compare"] = new Chart(ctx, {
      type: "bar", data: { labels, datasets: [{ label: "Avg WBGT", data: means, backgroundColor: COLORS.slice(0, labels.length) }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, title: { display: true, text: "WBGT (C)" } } } },
    });
  } catch(e) { console.error("WBGT compare error:", e); }
}

// Chart 6: Matrix heatmap (HTML table)
function renderMatrixHeatmap(data) {
  const container = document.getElementById("chart-heatmap-table");
  if (!data || !data.cells || !data.cells.length) {
    container.innerHTML = "<div class="empty-state"><p>No chair data</p></div>"; return;
  }
  
  const chairs = [...new Set(data.cells.map(c => c.x))].sort((a,b) => a-b);
  const times = [...new Set(data.cells.map(c => c.y))].sort();
  
  // Build lookup: chair_x_time -> cell
  const lookup = {};
  data.cells.forEach(c => { lookup[c.x + "_" + c.y] = c; });
  
  function wbgtColor(v) {
    if (v === null || v === undefined) return "#f1f5f9";
    if (v < 28) return `hsl(142, 76%, ${Math.max(30, 60 - v*1.5)}%)`;
    if (v < 30) return `hsl(45, 93%, 55%)`;
    if (v < 32) return `hsl(0, 84%, ${60 - (v-30)*15}%)`;
    return "hsl(0, 90%, 35%)";
  }
  
  let table = "<table style="font-size:11px;border-collapse:collapse;width:100%;"><tr><th style="position:sticky;left:0;background:#f8fafc;z-index:1;">Chair \\ Time</th>";
  times.forEach(t => { table += `<th style="padding:4px 2px;min-width:60px;text-align:center;border:1px solid #e2e8f0;background:#f8fafc;">${t}</th>`; });
  table += "</tr>";
  
  chairs.forEach(c => {
    table += `<tr><td style="padding:4px 8px;border:1px solid #e2e8f0;font-weight:500;position:sticky;left:0;background:#f8fafc;">#${c}</td>`;
    times.forEach(t => {
      const cell = lookup[c + "_" + t];
      if (cell) {
        const color = wbgtColor(cell.v);
        const vText = cell.v !== null ? cell.v + "C" : "-";
        table += `<td style="padding:4px;text-align:center;border:1px solid #cbd5e1;background:${color};color:${cell.v >= 30 ? 'white' : '#1e293b'};font-size:10px;" title="${cell.behav}">${vText}</td>`;
      } else {
        table += `<td style="padding:4px;text-align:center;border:1px solid #e2e8f0;background:#f8fafc;color:#cbd5e1;">-</td>`;
      }
    });
    table += "</tr>";
  });
  table += "</table><p style="font-size:11px;color:#64748b;margin-top:8px;">Color: green=safe, yellow=caution, red=danger. Hover for details.</p>";
  
  container.innerHTML = table;
}

document.addEventListener("DOMContentLoaded", loadBatchFilters);
