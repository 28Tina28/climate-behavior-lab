// Tool functions
function toast(msg, type) {
  type = type || "info";
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast " + type + " show";
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 3000);
}

function formatTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Page load
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [batches, stats] = await Promise.all([
      fetch("/api/batches").then(r => r.json()),
      fetch("/api/analysis/stats").then(r => r.json()),
    ]);

    document.getElementById("stat-total").textContent = batches.length;
    document.getElementById("stat-climate").textContent = batches.reduce((s, b) => s + b.climate_records, 0);
    document.getElementById("stat-behavior").textContent = batches.reduce((s, b) => s + b.behavior_records, 0);
    document.getElementById("stat-wbgt").textContent = (stats.wbgt_avg ?? "-") + "°C";

    renderBatchTable(batches);
    renderOverviewCharts(batches, stats);
  } catch (e) {
    console.error(e);
    toast("Load failed", "error");
  }
});

function renderBatchTable(batches) {
  const tb = document.getElementById("batch-table-body");
  if (!batches.length) {
    tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-secondary);padding:32px;">暂无数据</td></tr>';
    return;
  }
  tb.innerHTML = batches.map(b =>
    `<tr><td>${b.date_label||"-"}</td><td>${b.time_period||"-"}</td><td>${b.climate_records}</td><td>${b.behavior_records}</td><td>${formatTime(b.upload_time)}</td><td><a href="/analysis?batch_ids=${b.id}" class="btn btn-outline" style="padding:2px 10px;font-size:12px;">分析</a></td><td><button onclick="deleteBatch(${b.id})" class="btn btn-danger" style="padding:2px 10px;font-size:12px;">删除</button></td></tr>`
  ).join("");
}

async function deleteBatch(id) {
  if (!confirm("确定删除批次 #" + id + " 吗？此操作不可撤销。")) return;
  try {
    const res = await fetch("/api/batches/" + id, { method: "DELETE" });
    const data = await res.json();
    if (data.success) {
      toast("批次 #" + id + " 已删除", "success");
      // Reload page to refresh
      location.reload();
    } else {
      toast("删除失败", "error");
    }
  } catch (e) {
    toast("删除失败: " + e.message, "error");
  }
}

function renderOverviewCharts(batches, stats) {
  const COLORS = ["#2563eb","#dc2626","#16a34a","#d97706","#7c3aed","#0891b2","#db2777","#ca8a04"];

  // WBGT overview
  const promises = batches.map(b => fetch(`/api/analysis/timeseries?batch_ids=${b.id}`).then(r => r.json()));
  Promise.all(promises).then(all => {
    try {
      const ctx = document.getElementById("chart-wbgt-overview").getContext("2d");
      const datasets = [];
      let ci = 0;
      for (const series of all) {
        for (const [label, data] of Object.entries(series)) {
          const pts = data.filter(d => d.wbgt != null).map(d => ({ x: d.timestamp, y: d.wbgt }));
          if (!pts.length) continue;
          const c = COLORS[ci % COLORS.length];
          datasets.push({ label: label + " WBGT", data: pts, borderColor: c, backgroundColor: c + "22", borderWidth: 2, pointRadius: 0, tension: 0.3, fill: false });
          ci++;
        }
      }
      new Chart(ctx, {
        type: "line", data: { datasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
          scales: {
            x: { type: "time", time: { tooltipFormat: "MM-dd HH:mm" }, title: { display: true, text: "Time" } },
            y: { title: { display: true, text: "WBGT (℃)" }, beginAtZero: false },
          },
        },
      });
    } catch(e) { console.error("WBGT overview chart error:", e); }
  }).catch(() => {});

  // Stress distribution
  try {
    const wd = stats.wbgt_distribution || {};
    new Chart(document.getElementById("chart-stress"), {
      type: "doughnut",
      data: { labels: ["Safe (<28)", "Caution (28-30)", "Danger (30-32)", "Extreme (>=32)"], datasets: [{ data: [wd.safe||0, wd.caution||0, wd.danger||0, wd.extreme||0], backgroundColor: ["#16a34a","#d97706","#dc2626","#7f1d1d"] }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } } },
    });
  } catch(e) { console.error("Stress chart error:", e); }

  // Behavior distribution
  fetch("/api/analysis/behavior-distribution").then(r => r.json()).then(data => {
    try {
      const agg = {};
      for (const v of Object.values(data)) {
        for (const [k, c] of Object.entries(v)) { agg[k] = (agg[k] || 0) + c; }
      }
      new Chart(document.getElementById("chart-behavior-overview"), {
        type: "doughnut",
        data: { labels: Object.keys(agg), datasets: [{ data: Object.values(agg), backgroundColor: ["#2563eb","#16a34a","#d97706","#7c3aed","#dc2626","#0891b2"] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } } },
      });
    } catch(e) { console.error("Behavior overview chart error:", e); }
  }).catch(() => {});
}
