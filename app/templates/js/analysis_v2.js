var COLORS = ["#2563eb","#dc2626","#16a34a","#d97706","#7c3aed","#0891b2","#db2777","#ca8a04"];
var selectedBatches = [];
var charts = {};

function toggleBatch(id) {
  var el = document.querySelector(".chip[data-id=\"" + id + "\"]");
  var idx = selectedBatches.indexOf(id);
  if (idx >= 0) { selectedBatches.splice(idx, 1); el.classList.remove("active"); }
  else { selectedBatches.push(id); el.classList.add("active"); }
}
function selectAll() {
  document.querySelectorAll(".chip").forEach(function(x) { x.classList.add("active"); });
  selectedBatches = Array.from(document.querySelectorAll(".chip")).map(function(x) { return x.dataset.id; });
}
function clearAll() {
  document.querySelectorAll(".chip").forEach(function(x) { x.classList.remove("active"); });
  selectedBatches = [];
}
function destroyChart(k) { if (charts[k]) { charts[k].destroy(); delete charts[k]; } }

async function refreshAnalysis() {
  if (!selectedBatches.length) return;
  var dbg = document.getElementById("js-status");
  var ids = selectedBatches.join(",");
  dbg.textContent = "loading...";
  try {
    var data = {};
    data.stats = await (await fetch("/api/analysis/stats?batch_ids=" + ids)).json();
    data.timeseries = await (await fetch("/api/analysis/timeseries?batch_ids=" + ids)).json();
    data.behaviorByTemp = await (await fetch("/api/analysis/behavior-by-temp?batch_ids=" + ids)).json();
    data.boxplot = await (await fetch("/api/analysis/boxplot?batch_ids=" + ids)).json();
    data.shadeStacked = await (await fetch("/api/analysis/shade-stacked?batch_ids=" + ids)).json();
    data.shadeByAge = await (await fetch("/api/analysis/shade-by-age?batch_ids=" + ids)).json();
    dbg.textContent = "data loaded";
    renderStats(data.stats);
    renderTimeseries(data.timeseries);
    renderBoxplot(data.boxplot);
    renderShadeStacked(data.shadeStacked);
    renderBehaviorByTemp(data.behaviorByTemp);
    renderShadeByAge(data.shadeByAge);
    dbg.textContent = "done";
  } catch (e) { dbg.textContent = "Error: " + e.message; }
}

function renderStats(s) {
  document.getElementById("astat-temp").textContent = (s.temp_min || "-") + "~" + (s.temp_max || "-");
  document.getElementById("astat-wbgt").textContent = (s.wbgt_min || "-") + "~" + (s.wbgt_max || "-");
  document.getElementById("astat-behavior").textContent = s.total_behaviors || 0;
  var wd = s.wbgt_distribution || {};
  var tot = (wd.safe || 0) + (wd.caution || 0) + (wd.danger || 0) + (wd.extreme || 0);
  document.getElementById("astat-stress").textContent = tot ? Math.round(((wd.danger || 0) + (wd.extreme || 0)) / tot * 100) + "%" : "0%";
}

function renderTimeseries(t) {
  destroyChart("timeseries");
  var ctx = document.getElementById("chart-timeseries").getContext("2d");
  var dss = []; var ci = 0;
  for (var label in t) {
    var recs = t[label]; var temps = []; var wbgts = [];
    for (var j = 0; j < recs.length; j++) {
      var r = recs[j];
      if (r.temperature != null) temps.push({ x: r.timestamp, y: r.temperature });
      if (r.wbgt != null) wbgts.push({ x: r.timestamp, y: r.wbgt });
    }
    var c = COLORS[ci % 8];
    if (temps.length) dss.push({ label: label + " T", data: temps, borderColor: c, borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false });
    if (wbgts.length) dss.push({ label: label + " WBGT", data: wbgts, borderColor: c, borderWidth: 2.5, pointRadius: 0, tension: 0.3, borderDash: [4, 3], fill: false });
    ci++;
  }
  charts["timeseries"] = new Chart(ctx, {
    type: "line", data: { datasets: dss },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
      scales: { x: { type: "time", time: { tooltipFormat: "MM-dd HH:mm" }, title: { display: true, text: "Time" } }, y: { title: { display: true, text: "T / WBGT (\"\"C)" } } }
    }
  });
}

function renderBoxplot(bx) {
  destroyChart("temp-behavior");
  if (!bx || !bx.length) return;
  var ctx = document.getElementById("chart-temp-behavior").getContext("2d");
  charts["temp-behavior"] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: bx.map(function(d) { return d.behavior; }),
      datasets: [
        { label: "Min-Q1", data: bx.map(function(d) { return [d.min, d.q1]; }), backgroundColor: "rgba(100,116,139,0.3)", borderRadius: 0 },
        { label: "IQR", data: bx.map(function(d) { return [d.q1, d.q3]; }), backgroundColor: COLORS.slice(0, bx.length), borderRadius: 0 },
        { label: "Q3-Max", data: bx.map(function(d) { return [d.q3, d.max]; }), backgroundColor: "rgba(100,116,139,0.3)", borderRadius: 0 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
      scales: { x: { title: { display: true, text: "Behavior" } }, y: { title: { display: true, text: "Temp (\"\"C)" }, beginAtZero: false } }
    }
  });
}

function renderShadeStacked(sd) {
  destroyChart("shade");
  if (!sd || !sd.bins) return;
  var ctx = document.getElementById("chart-shade").getContext("2d");
  var envs = ["\u5168\u906e\u9634","\u5168\u906e\u835c","\u534a\u906e\u9634","\u534a\u906e\u835c","\u66dd\u6652"];
  var ec = ["#16a34a","#22c55e","#d97706","#f59e0b","#dc2626"];
  var dss = [];
  envs.forEach(function(env, i) {
    var vals = sd.bins.map(function(b) { return (sd.data[b] && sd.data[b][env]) ? sd.data[b][env] : 0; });
    if (vals.some(function(v) { return v > 0; })) dss.push({ label: env, data: vals, backgroundColor: ec[i % 5] });
  });
  charts["shade"] = new Chart(ctx, {
    type: "bar", data: { labels: sd.bins, datasets: dss },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
      scales: { x: { stacked: true, title: { display: true, text: "Temp (\"\"C)" } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "People" } } }
    }
  });
}

function renderBehaviorByTemp(bd) {
  destroyChart("behavior-temp");
  if (!bd || !bd.bins) return;
  var ctx = document.getElementById("chart-behavior-temp").getContext("2d");
  var cats = {};
  for (var bk in bd.data) { for (var c in bd.data[bk]) { cats[c] = true; } }
  var catList = Object.keys(cats);
  var colors = {};
  for (var i = 0; i < catList.length; i++) colors[catList[i]] = COLORS[i % 8];
  var dss = [];
  catList.forEach(function(cat) {
    var vals = bd.bins.map(function(b) { return (bd.data[b] && bd.data[b][cat]) ? bd.data[b][cat] : 0; });
    if (vals.some(function(v) { return v > 0; })) dss.push({ label: cat, data: vals, backgroundColor: colors[cat] });
  });
  charts["behavior-temp"] = new Chart(ctx, {
    type: "bar", data: { labels: bd.bins, datasets: dss },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
      scales: { x: { stacked: true, title: { display: true, text: "Temp (\"\"C)" } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "Count" } } }
    }
  });
}

function renderShadeByAge(sa) {
  destroyChart("shade-age");
  if (!sa || !sa.ages || !sa.ages.length) return;
  var ctx = document.getElementById("chart-shade-age").getContext("2d");
  var envs = {};
  for (var a in sa.data) { for (var e in sa.data[a]) { envs[e] = true; } }
  var envList = Object.keys(envs);
  var ec2 = ["#16a34a","#22c55e","#d97706","#f59e0b","#dc2626"];
  var dss = []; var ci = 0;
  envList.forEach(function(env) {
    var vals = sa.ages.map(function(a) { return (sa.data[a] && sa.data[a][env]) ? sa.data[a][env] : 0; });
    if (vals.some(function(v) { return v > 0; })) dss.push({ label: env, data: vals, backgroundColor: ec2[ci % 5] });
    ci++;
  });
  charts["shade-age"] = new Chart(ctx, {
    type: "bar", data: { labels: sa.ages, datasets: dss },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 10 } } } },
      scales: { x: { stacked: true, title: { display: true, text: "Age" } }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "Count" } } }
    }
  });
}

async function loadBatches() {
  var dbg = document.getElementById("js-status");
  try {
    var res = await fetch("/api/batches");
    var batches = await res.json();
    var container = document.getElementById("batch-filters");
    if (!batches.length) { container.innerHTML = "<p>暂无数据</p>"; return; }
    var params = new URLSearchParams(window.location.search);
    var pre = params.get("batch_ids");
    var h = "";
    for (var i = 0; i < batches.length; i++) {
      var b = batches[i]; var sid = String(b.id);
      var active = pre ? pre.split(",").indexOf(sid) >= 0 : true;
      if (active && selectedBatches.indexOf(sid) < 0) selectedBatches.push(sid);
      h += "<span class=\"chip " + (active ? "active" : "") + "\" data-id=\"" + sid + "\" onclick=\"toggleBatch(\'" + sid + "\')\">" + (b.date_label || "") + " " + (b.time_period || "") + " <span class=\"count\">#" + sid + "</span></span>";
    }
    container.innerHTML = h;
    dbg.textContent = "batches:" + batches.length;
    if (selectedBatches.length) await refreshAnalysis();
  } catch (e) { dbg.textContent = "err:" + e.message; }
}

document.addEventListener("DOMContentLoaded", loadBatches);