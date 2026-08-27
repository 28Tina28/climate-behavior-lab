 window.renderCharts = function(stats, ts, bd, bx, sd, hm, status) {
   status.textContent += " renderSt";
   try {
     document.getElementById("astat-temp").textContent = (stats.temp_min || "-") + " ~ " + (stats.temp_max || "-");
     document.getElementById("astat-wbgt").textContent = (stats.wbgt_min || "-") + " ~ " + (stats.wbgt_max || "-");
     document.getElementById("astat-behavior").textContent = stats.total_behaviors || 0;
     var wd = stats.wbgt_distribution || {};
     var t = (wd.safe||0)+(wd.caution||0)+(wd.danger||0)+(wd.extreme||0);
     document.getElementById("astat-stress").textContent = t ? Math.round(((wd.danger||0)+(wd.extreme||0))/t*100)+"%" : "0%";
     status.textContent += " statsOK";
   } catch(e) { status.textContent += " StE:" + e.message; }
   status.textContent += " renderTS";
   try {
     var ctx = document.getElementById("chart-timeseries").getContext("2d");
     var datasets = [];
     var ci = 0;
     var colors = ["#2563eb","#dc2626","#16a34a","#d97706","#7c3aed","#0891b2","#db2777","#ca8a04"];
     for (var label in ts) {
       var records = ts[label];
       var temps = []; var wbgts = [];
       for (var j = 0; j < records.length; j++) {
         var r = records[j];
         if (r.temperature != null) temps.push({x: r.timestamp, y: r.temperature});
         if (r.wbgt != null) wbgts.push({x: r.timestamp, y: r.wbgt});
       }
       var c = colors[ci % 8];
       if (temps.length) datasets.push({label: label + " T", data: temps, borderColor: c, borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: false});
       if (wbgts.length) datasets.push({label: label + " WBGT", data: wbgts, borderColor: c, borderWidth: 2.5, pointRadius: 0, tension: 0.3, borderDash: [4,3], fill: false});
       ci++;
     }
     new Chart(ctx, {type: "line", data: {datasets: datasets}, options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {position: "bottom", labels: {font: {size: 10}}}}, scales: {x: {type: "time", time: {tooltipFormat: "MM-dd HH:mm"}, title: {display: true, text: "Time"}}, y: {title: {display: true, text: "T / WBGT (C)"}}}}});
     status.textContent += " TSchart";
   } catch(e) { status.textContent += " TSE:" + e.message; }
 };
