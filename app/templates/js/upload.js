let climateFile = null, observationFile = null;

["climate-input", "observation-input"].forEach(id => {
  document.getElementById(id).addEventListener("change", e => {
    const f = e.target.files[0];
    if (!f) return;
    if (id === "climate-input") {
      climateFile = f;
      document.getElementById("climate-name").textContent = f.name;
      document.getElementById("climate-zone").classList.add("has-file");
    } else {
      observationFile = f;
      document.getElementById("observation-name").textContent = f.name;
      document.getElementById("observation-zone").classList.add("has-file");
    }
    checkReady();
  });
});

["climate-zone", "observation-zone"].forEach(id => {
  const zone = document.getElementById(id);
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault(); zone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (id === "climate-zone" && file.name.endsWith(".csv")) {
      climateFile = file;
      document.getElementById("climate-name").textContent = file.name;
      zone.classList.add("has-file");
    } else if (id === "observation-zone" && file.name.endsWith(".xlsx")) {
      observationFile = file;
      document.getElementById("observation-name").textContent = file.name;
      zone.classList.add("has-file");
    }
    checkReady();
  });
});

function checkReady() {
  document.getElementById("upload-btn").disabled = !(climateFile && observationFile);
}

async function startUpload() {
  if (!climateFile || !observationFile) return;
  const btn = document.getElementById("upload-btn");
  const progress = document.getElementById("progress");
  const fill = document.getElementById("progress-fill");
  const resultBox = document.getElementById("result-box");

  btn.disabled = true;
  progress.classList.add("active");
  resultBox.className = "result-box";
  fill.style.width = "30%";
  document.getElementById("progress-text").textContent = "Uploading...";

  const form = new FormData();
  form.append("climate_file", climateFile);
  form.append("observation_file", observationFile);

  try {
    fill.style.width = "60%";
    document.getElementById("progress-text").textContent = "Parsing...";

    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    fill.classList.add("done");
    document.getElementById("progress-text").textContent = "Done!";

    document.getElementById("result-title").textContent = "Upload OK - " + (data.date_label||"") + " " + (data.time_period||"");
    document.getElementById("result-detail").textContent = data.climate_count + " climate, " + data.behavior_count + " behavior records";
    resultBox.className = "result-box success";
    window._lastBatchId = data.batch_id;
  } catch (e) {
    fill.style.width = "100%";
    fill.style.background = "var(--danger)";
    document.getElementById("progress-text").textContent = "Failed";
    resultBox.className = "result-box error";
    document.getElementById("result-title").textContent = "Upload failed";
    document.getElementById("result-detail").textContent = e.message;
  } finally {
    btn.disabled = false;
  }
}

function goToAnalysis() {
  const id = window._lastBatchId;
  window.location.href = id ? "/analysis?batch_ids=" + id : "/analysis";
}
