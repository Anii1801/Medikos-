const pageRoot = document.getElementById("page-root");
const pageName = document.body.dataset.page || "dashboard";

function pageShell(title, active, content) {
  pageRoot.innerHTML = `
    <header class="appbar patient-pagebar">
      <a class="brand" href="index.html" aria-label="MediKiosk home">
        <span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="currentColor"/><path d="M5 17h5.2l2.3-6.2 3.4 12.4L18.6 17H27" fill="none" stroke="#F4F7F5" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
        <span class="brand-copy"><span class="brand-name">MediKiosk</span><span class="brand-tagline">Your health, organized.</span></span>
      </a>
      <button class="menu-toggle" id="patient-menu-toggle" type="button" aria-expanded="false" aria-controls="patient-nav" aria-label="Open workspace menu">Menu</button>
      <nav class="page-nav" id="patient-nav" aria-label="Patient workspace">
        ${[
          ["dashboard.html", "Dashboard", "dashboard"],
          ["interview.html", "Medical History", "interview"],
          ["reports.html", "Medical Reports", "reports"],
          ["timeline.html", "Health Timeline", "timeline"],
          ["summary.html", "My Summary", "summary"]
        ].map(x => `<a class="${active === x[2] ? "active" : ""}" href="${x[0]}">${x[1]}</a>`).join("")}
      </nav>
      <button class="btn btn-outline btn-sm" id="page-signout" type="button">Sign out</button>
    </header>
    <main class="patient-page page">${content}</main>
  `;
  const menu = document.getElementById("patient-menu-toggle");
  const nav = document.getElementById("patient-nav");
  menu.onclick = () => {
    const expanded = menu.getAttribute("aria-expanded") === "true";
    menu.setAttribute("aria-expanded", String(!expanded));
    nav.classList.toggle("is-open", !expanded);
  };
  document.getElementById("page-signout").onclick = async () => {
    try { await api("/auth/logout", { method: "POST" }); }
    catch (e) { console.error("Sign out failed", e); }
    sessionStorage.removeItem("mk_token");
    window.location.href = "index.html";
  };
}

async function requireUser() {
  if (!sessionStorage.getItem("mk_token")) {
    window.location.href = "login.html?next=" + encodeURIComponent(location.pathname.split("/").pop());
    return null;
  }
  try { return await api("/me"); }
  catch (_) {
    sessionStorage.removeItem("mk_token");
    window.location.href = "login.html";
    return null;
  }
}

function pageError(message) {
  pageRoot.innerHTML = `<main class="page"><div class="alert alert-urgent" role="alert">${esc(message)}</div><a class="btn btn-outline" href="index.html">Return home</a></main>`;
}

async function renderDashboard() {
  const me = await requireUser(); if (!me) return;
  let records = [], docs = [];
  let recordsError = "", docsError = "";
  try { records = await api("/records"); } catch (e) { recordsError = e.message; }
  try { docs = await api("/documents"); } catch (e) { docsError = e.message; }
  pageShell("Dashboard", "dashboard", `
    <p class="eyebrow">PATIENT DASHBOARD</p>
    <h1>Welcome${me.name ? ", " + esc(me.name.split(" ")[0]) : ""}</h1>
    <p class="subtitle">Prepare your information before your next consultation.</p>
    <div class="dashboard-actions">
      <a class="btn" href="interview.html">${sessionStorage.getItem("mk_iv") ? "Continue Interview" : "Start Interview"}</a>
      <a class="btn btn-outline" href="reports.html">Medical Reports</a>
    </div>
    <div class="patient-card-grid">
      <a class="patient-card" href="interview.html"><span class="action-icon">${ICONS.history}</span><h2>Medical History</h2><p>Answer questions about your symptoms, health history, and medications.</p></a>
      <a class="patient-card" href="reports.html"><span class="action-icon">${ICONS.reports}</span><h2>Medical Reports</h2><p>${docs.length} uploaded document${docs.length === 1 ? "" : "s"} · Upload and organize your reports.</p></a>
      <a class="patient-card" href="timeline.html"><span class="action-icon">${ICONS.timeline}</span><h2>Health Timeline</h2><p>${records.length ? `${records.length} recorded encounter${records.length === 1 ? "" : "s"}.` : "No encounters recorded yet."}</p></a>
      <a class="patient-card" href="summary.html"><span class="action-icon">${ICONS.summary}</span><h2>My Summary</h2><p>Review an available generated draft and its source information.</p></a>
    </div>
    ${recordsError ? `<div class="alert alert-urgent mt" role="alert">Recent activity could not be loaded: ${esc(recordsError)}</div>` :
      records.length ? `<section class="card mt" aria-labelledby="recent-heading"><h2 id="recent-heading">Recent activity</h2><div class="document-list">${records.slice(0, 3).map(r => `<div class="document-row"><span>Encounter ${esc(r.token_no)}</span><span class="chip">${esc(r.status)}</span></div>`).join("")}</div></section>` : ""}
    ${docsError ? `<div class="alert alert-urgent mt" role="alert">Document activity could not be loaded: ${esc(docsError)}</div>` : ""}
    <section class="card mt" aria-labelledby="data-controls-heading">
      <h2 id="data-controls-heading">Account data</h2>
      <p class="caption">You can permanently erase your working data and submitted records from this application. This cannot be undone.</p>
      <button class="btn btn-outline" id="erase-data" type="button">Delete my data</button>
      <p id="erase-status" class="caption" aria-live="polite"></p>
    </section>
  `);
  document.getElementById("erase-data").onclick = async event => {
    if (!window.confirm("Permanently erase your documents, encounter records, evidence, and account? This cannot be undone.")) return;
    event.currentTarget.disabled = true;
    try {
      await api("/me/data", { method: "DELETE" });
      sessionStorage.removeItem("mk_token");
      window.location.href = "index.html";
    } catch (e) {
      document.getElementById("erase-status").textContent = "Data deletion failed: " + e.message;
      event.currentTarget.disabled = false;
    }
  };
}

async function renderInterview() {
  const me = sessionStorage.getItem("mk_token") ? await requireUser() : null;
  pageShell("Medical History", "interview", `
    <p class="eyebrow">MEDICAL HISTORY</p>
    <h1>Complete your medical history</h1>
    <p class="subtitle">The guided interview adapts to your answers and preserves your progress.</p>
    <div class="card page-entry-card">
      <h2>${sessionStorage.getItem("mk_iv") ? "Continue your interview" : "Ready to begin?"}</h2>
      <p>${sessionStorage.getItem("mk_iv") ? "Your saved session is ready to continue." : "Answer one question at a time. You can go back and review your answers."}</p>
      <button class="btn" id="open-interview">${sessionStorage.getItem("mk_iv") ? "Continue Interview" : "Start Interview"}</button>
      ${!me ? `<button class="btn btn-outline" id="guest-interview" type="button">Continue as guest</button><p class="caption">Guest working-session data is removed after submission. Encounter evidence and source documents remain attached to the submitted record for clinician review.</p>` : ""}
    </div>
  `);
  document.getElementById("open-interview").onclick = () => {
    if (me) { sessionStorage.setItem("mk_start_interview", "1"); location.href = "index.html"; }
    else location.href = "login.html?next=interview.html";
  };
  document.getElementById("guest-interview")?.addEventListener("click", async e => {
    e.currentTarget.disabled = true;
    try {
      const result = await api("/auth/guest", { method: "POST" });
      setToken(result.token); sessionStorage.setItem("mk_start_interview", "1"); location.href = "index.html";
    } catch (err) { e.currentTarget.disabled = false; alert(err.message); }
  });
}

async function renderReports() {
  const me = await requireUser(); if (!me) return;
  let docs = [];
  let docsError = "";
  try { docs = await api("/documents"); } catch (e) { docsError = e.message; }
  pageShell("Medical Reports", "reports", `
    <p class="eyebrow">MEDICAL REPORTS</p><h1>Documents</h1>
    <p class="subtitle">Upload prescriptions, laboratory reports, and other medical documents.</p>
    <div class="card">
      <label class="input-label" for="report-file">Choose a document</label>
      <input id="report-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt" multiple>
      <p class="caption">Up to 10 files, 8 MiB each and 32 MiB per batch.</p>
      <button class="btn" id="upload-report" type="button">Upload Reports</button>
      <p id="report-status" class="caption" aria-live="polite"></p>
    </div>
    ${docsError ? `<div class="alert alert-urgent" role="alert">Documents could not be loaded: ${esc(docsError)}</div>` : `<div class="card"><h2>Uploaded documents</h2>
      ${docs.length ? `<div class="document-list">${docs.map(d => `<details class="document-row"><summary><b>${esc(d.filename || d.name || "Document")}</b><span class="chip">${esc(d.processing_status || d.doc_type || "Uploaded")}</span></summary>
        <p class="caption">Source: ${esc(d.filename || "uploaded document")} · Extraction engine: ${esc(d.engine || "not reported")} · Document date: ${esc(d.date || "Not extracted")} · Uploaded: ${esc(d.created ? new Date(d.created * 1000).toLocaleString() : "Not recorded")}</p>
        ${d.processing_error ? `<p class="alert alert-urgent" role="status">${esc(d.processing_error)}</p>` : ""}
        ${d.has_original ? `<button class="btn btn-outline btn-sm" type="button" data-report-download="${d.id}" data-filename="${esc(d.filename)}">Download original</button>` : ""}
        <label class="input-label" for="category-${d.id}">Document category</label>
        <select id="category-${d.id}" data-document-category="${d.id}">
          ${[["lab_report", "Laboratory report"], ["prescription", "Prescription"], ["discharge_summary", "Discharge summary"], ["other", "Other"]].map(([value, label]) => `<option value="${value}" ${d.doc_type === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
        <button class="btn btn-outline btn-sm" type="button" data-document-save-category="${d.id}">Save category</button>
        ${d.processing_status === "failed" ? `<label class="input-label" for="replacement-${d.id}">Optional: choose an unlocked or corrected replacement file</label><input id="replacement-${d.id}" type="file" data-document-replacement="${d.id}" accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt"><button class="btn btn-outline btn-sm" type="button" data-document-retry="${d.id}">Retry extraction</button>` : ""}
        <button class="btn btn-outline btn-sm" type="button" data-document-delete="${d.id}">Remove document</button>
        ${d.text ? `<details><summary>Preview extracted text</summary><pre class="document-preview">${esc(d.text)}</pre></details>` : `<p class="caption">No text was extracted. Verify the original or retry extraction.</p>`}
        ${d.entities?.diagnoses?.length ? `<h3>Diagnoses mentioned</h3><p>${d.entities.diagnoses.map(esc).join(", ")}</p>` : ""}
        ${d.entities?.medications?.length ? `<h3>Medication mentions</h3><ul>${d.entities.medications.map(m => `<li>${esc(m.name)} ${esc(m.dose || "")} ${esc(m.frequency || "")} · ${esc(m.status || "reported")}</li>`).join("")}</ul>` : ""}
        ${d.entities?.allergies?.length ? `<h3>Allergy mentions</h3><ul>${d.entities.allergies.map(esc).map(x => `<li>${x}</li>`).join("")}</ul>` : ""}
        ${d.entities?.labs?.length ? `<h3>Laboratory findings</h3><div class="table-wrap"><table class="stack-table"><thead><tr><th>Test</th><th>Value</th><th>Reference range</th><th>Uncertainty</th></tr></thead><tbody>${d.entities.labs.map(l => `<tr><td data-label="Test">${esc(l.test)}</td><td data-label="Value">${esc(l.value)} ${esc(l.unit)}</td><td data-label="Reference range">${esc(l.ref || "Not provided")}</td><td data-label="Uncertainty">${esc(l.uncertainty || l.reference_source || "Not reported")}</td></tr>`).join("")}</tbody></table></div>` : `<p class="caption">No laboratory findings were extracted from this document.</p>`}
      </details>`).join("")}</div>` : `<p class="empty-state">No documents uploaded yet.</p>`}</div>`}
    </div>
  `);
  document.querySelectorAll("[data-report-download]").forEach(button => button.onclick = async () => {
    try { await downloadDocument("/documents/" + button.dataset.reportDownload + "/file", button.dataset.filename); }
    catch (e) { document.getElementById("report-status").textContent = "Download failed: " + e.message; }
  });
  document.querySelectorAll("[data-document-save-category]").forEach(button => button.onclick = async () => {
    const select = document.querySelector(`[data-document-category="${button.dataset.documentSaveCategory}"]`);
    const status = document.getElementById("report-status");
    button.disabled = true;
    try {
      await api("/documents/" + button.dataset.documentSaveCategory, {
        method: "PUT", json: { doc_type: select.value }
      });
      status.textContent = "Document category updated.";
    } catch (e) { status.textContent = "Category update failed: " + e.message; }
    finally { button.disabled = false; }
  });
  document.querySelectorAll("[data-document-retry]").forEach(button => button.onclick = async () => {
    const status = document.getElementById("report-status");
    button.disabled = true;
    try {
      const replacement = document.querySelector(`[data-document-replacement="${button.dataset.documentRetry}"]`)?.files?.[0];
      const body = new FormData();
      if (replacement) body.append("file", replacement);
      const result = await api("/documents/" + button.dataset.documentRetry + "/retry", { method: "POST", body });
      status.textContent = result.processing_status === "failed" ? "Retry did not extract the document: " + result.processing_error : "Document extraction retried.";
      await renderReports();
    } catch (e) { status.textContent = "Retry failed: " + e.message; button.disabled = false; }
  });
  document.querySelectorAll("[data-document-delete]").forEach(button => button.onclick = async () => {
    const status = document.getElementById("report-status");
    if (!window.confirm("Remove this document from your working list? Submitted encounter copies are not changed.")) return;
    button.disabled = true;
    try {
      await api("/documents/" + button.dataset.documentDelete, { method: "DELETE" });
      status.textContent = "Document removed.";
      await renderReports();
    } catch (e) { status.textContent = "Removal failed: " + e.message; button.disabled = false; }
  });
  document.getElementById("upload-report").onclick = async () => {
    const files = Array.from(document.getElementById("report-file").files || []), status = document.getElementById("report-status");
    if (!files.length) { status.textContent = "Choose at least one file."; return; }
    const data = new FormData(); files.forEach(file => data.append("files", file)); status.textContent = `Processing ${files.length} document${files.length === 1 ? "" : "s"}…`;
    try {
      const result = await api("/documents/batch", { body: data });
      status.textContent = `${result.succeeded} processed, ${result.failed} failed. Each document shows its extraction status below.`;
      await renderReports();
    }
    catch (e) { status.textContent = "Upload failed: " + e.message; }
  };
}

async function renderTimeline() {
  const me = await requireUser(); if (!me) return;
  let records = [], docs = [];
  try { [records, docs] = await Promise.all([api("/records"), api("/documents")]); }
  catch (e) { pageError("Timeline could not be loaded: " + e.message); return; }
  const events = [
    ...records.map(r => ({ kind: "Encounter", date: r.created, description: `Encounter ${r.token_no}`, detail: `Priority: ${["", "Emergency", "Urgent", "Routine"][r.priority] || "Not reported"} · Status: ${r.status}` })),
    ...docs.map(d => ({ kind: "Document", date: d.created, description: d.filename, detail: `${d.doc_type} · ${d.processing_status}`, id: d.id, hasOriginal: d.has_original }))
  ].filter(item => Number.isFinite(Number(item.date))).sort((a, b) => Number(b.date) - Number(a.date));
  pageShell("Health Timeline", "timeline", `<p class="eyebrow">HEALTH TIMELINE</p><h1>Your recorded history</h1><p class="subtitle">Encounter dates and document upload dates are shown separately; an upload date is not a clinical event date.</p>
    <div class="card">${events.length ? `<div class="document-list">${events.map(item => `<article class="document-row"><span class="chip">${esc(item.kind)}</span><strong>${esc(item.description)}</strong><span>${new Date(Number(item.date) * 1000).toLocaleString("en-IN")}</span><span class="caption">${esc(item.detail)}</span>${item.hasOriginal ? `<button class="btn btn-outline btn-sm" type="button" data-timeline-download="${item.id}" data-filename="${esc(item.description)}">Download source</button>` : ""}</article>`).join("")}</div>` : `<p class="empty-state">No encounters or documents are available yet.</p>`}</div>`);
  document.querySelectorAll("[data-timeline-download]").forEach(button => button.onclick = async () => {
    try { await downloadDocument("/documents/" + button.dataset.timelineDownload + "/file", button.dataset.filename); }
    catch (e) { alert("Document download failed: " + e.message); }
  });
}

async function renderSummary() {
  const me = await requireUser(); if (!me) return;
  let records = [];
  try { records = await api("/records"); } catch (e) { pageError("Summary records could not be loaded: " + e.message); return; }
  let report = null;
  if (records[0]) {
    try { report = (await api("/records/" + records[0].id)).clinical_report; }
    catch (e) { pageError("The latest summary could not be loaded: " + e.message); return; }
  }
  pageShell("My Summary", "summary", `<p class="eyebrow">MY SUMMARY</p><h1>Clinical summary</h1><p class="subtitle">Patient-reported and document-extracted information remain attributed and unresolved conflicts are preserved.</p>${report ? renderClinicalReport(report, { mode: "patient" }) : `<div class="empty-state">Complete and submit a medical history interview to create a summary.</div>`}`);
}

async function bootPatientPage() {
  try {
    if (pageName === "dashboard") await renderDashboard();
    else if (pageName === "interview") await renderInterview();
    else if (pageName === "reports") await renderReports();
    else if (pageName === "timeline") await renderTimeline();
    else if (pageName === "summary") await renderSummary();
    else await renderDashboard();
  } catch (e) { pageError(e.message); }
}
bootPatientPage();
