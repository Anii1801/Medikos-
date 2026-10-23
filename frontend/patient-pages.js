const pageRoot = document.getElementById("page-root");
const pageName = document.body.dataset.page || "dashboard";

function pageShell(title, active, content) {
  document.title = `${tr(title)} | MediKiosk`;
  pageRoot.innerHTML = `
    <header class="appbar patient-pagebar">
      <a class="brand" href="index.html" aria-label="${tr("home")} — MediKiosk">
        <span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="currentColor"/><path d="M5 17h5.2l2.3-6.2 3.4 12.4L18.6 17H27" fill="none" stroke="#F4F7F5" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
        <span class="brand-copy"><span class="brand-name">MediKiosk</span><span class="brand-tagline">${tr("Your health, organized.")}</span></span>
      </a>
      <button class="menu-toggle" id="patient-menu-toggle" type="button" aria-expanded="false" aria-controls="patient-nav" aria-label="${tr("Open workspace menu")}">${tr("menu")}</button>
      <nav class="page-nav" id="patient-nav" aria-label="${tr("Patient workspace")}">
        ${[
          ["dashboard.html", tr("dashboard"), "dashboard"],
          ["interview.html", tr("medicalHistory"), "interview"],
          ["reports.html", tr("medicalReports"), "reports"],
          ["timeline.html", tr("timeline"), "timeline"],
          ["summary.html", tr("mySummary"), "summary"]
        ].map(x => `<a class="${active === x[2] ? "active" : ""}" href="${x[0]}">${x[1]}</a>`).join("")}
      </nav>
      ${languageSelector()}
      <button class="btn btn-outline btn-sm" id="page-signout" type="button">${tr("signOut")}</button>
    </header>
    <main class="patient-page page">${content}</main>
  `;
  bindLanguageSelector();
  document.documentElement.removeAttribute("data-language-pending");
  const menu = document.getElementById("patient-menu-toggle");
  const nav = document.getElementById("patient-nav");
  menu.onclick = () => {
    const expanded = menu.getAttribute("aria-expanded") === "true";
    menu.setAttribute("aria-expanded", String(!expanded));
    nav.classList.toggle("is-open", !expanded);
    menu.setAttribute("aria-label", tr(expanded ? "Open workspace menu" : "Close workspace menu"));
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
  pageRoot.innerHTML = `<main class="page">${languageSelector()}<div class="alert alert-urgent" role="alert">${esc(patientError(message))}</div><a class="btn btn-outline" href="index.html">${tr("returnHome")}</a></main>`;
  bindLanguageSelector();
  document.documentElement.removeAttribute("data-language-pending");
}

async function renderDashboard() {
  const me = await requireUser(); if (!me) return;
  let records = [], docs = [];
  let recordsError = "", docsError = "";
  try { records = await api("/records"); } catch (e) { recordsError = e.message; }
  try { docs = await api("/documents"); } catch (e) { docsError = e.message; }
  pageShell("Dashboard", "dashboard", `
    <p class="eyebrow">${tr("dashboardEyebrow")}</p>
    <h1>${tr("welcomeName")}${me.name ? ", " + esc(me.name.split(" ")[0]) : ""}</h1>
    <p class="subtitle">${tr("prepareConsultation")}</p>
    <div class="dashboard-actions">
      <a class="btn" href="interview.html">${sessionStorage.getItem("mk_iv") ? tr("continueInterview") : tr("startInterview")}</a>
      <a class="btn btn-outline" href="reports.html">${tr("medicalReports")}</a>
    </div>
    <div class="patient-card-grid">
      <a class="patient-card" href="interview.html"><span class="action-icon">${ICONS.history}</span><h2>${tr("medicalHistory")}</h2><p>${tr("medicalHistoryHelp")}</p></a>
      <a class="patient-card" href="reports.html"><span class="action-icon">${ICONS.reports}</span><h2>${tr("medicalReports")}</h2><p>${docs.length} ${tr("documentsCount")} · ${tr("uploadOrganize")}</p></a>
      <a class="patient-card" href="timeline.html"><span class="action-icon">${ICONS.timeline}</span><h2>${tr("timeline")}</h2><p>${records.length ? `${records.length} ${tr("encountersCount")}` : tr("noEncounters")}</p></a>
      <a class="patient-card" href="summary.html"><span class="action-icon">${ICONS.summary}</span><h2>${tr("mySummary")}</h2><p>${tr("summaryReviewHelp")}</p></a>
    </div>
    ${recordsError ? `<div class="alert alert-urgent mt" role="alert">${tr("recentActivity")}: ${esc(patientError(recordsError))}</div>` :
      records.length ? `<section class="card mt" aria-labelledby="recent-heading"><h2 id="recent-heading">${tr("recentActivity")}</h2><div class="document-list">${records.slice(0, 3).map(r => `<div class="document-row"><span>${tr("encounter")} ${esc(r.token_no)}</span><span class="chip">${esc(tr(r.status))}</span></div>`).join("")}</div></section>` : ""}
    ${docsError ? `<div class="alert alert-urgent mt" role="alert">${tr("documentsLoadFailed")}: ${esc(patientError(docsError))}</div>` : ""}
    <section class="card mt" aria-labelledby="data-controls-heading">
      <h2 id="data-controls-heading">${tr("accountData")}</h2>
      <p class="caption">${tr("eraseWarning")}</p>
      <button class="btn btn-outline" id="erase-data" type="button">${tr("erase")}</button>
      <p id="erase-status" class="caption" aria-live="polite"></p>
    </section>
  `);
  document.getElementById("erase-data").onclick = async event => {
    if (!window.confirm(tr("confirmErase"))) return;
    event.currentTarget.disabled = true;
    try {
      await api("/me/data", { method: "DELETE" });
      sessionStorage.removeItem("mk_token");
      window.location.href = "index.html";
    } catch (e) {
      document.getElementById("erase-status").textContent = tr("eraseFailed") + ": " + patientError(e);
      event.currentTarget.disabled = false;
    }
  };
}

async function renderInterview() {
  const me = sessionStorage.getItem("mk_token") ? await requireUser() : null;
  const savedMode = localStorage.getItem("mk_input_mode") === "voice" ? "voice" : "click";
  const recognitionSupported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  pageShell("Medical History", "interview", `
    <p class="eyebrow">${tr("medicalHistory")}</p>
    <h1>${tr("completeHistory")}</h1>
    <p class="subtitle">${tr("guidedInterviewHelp")}</p>
    <div class="card page-entry-card">
      <h2>${sessionStorage.getItem("mk_iv") ? tr("continueYourInterview") : tr("readyBegin")}</h2>
      <p>${sessionStorage.getItem("mk_iv") ? tr("savedSessionReady") : tr("oneQuestionHelp")}</p>
      <label class="input-label" for="input-mode">${tr("inputMode")}</label>
      <select id="input-mode">
        <option value="click" ${savedMode === "click" ? "selected" : ""}>${tr("clickMode")}</option>
        <option value="voice" ${savedMode === "voice" ? "selected" : ""}>${tr("voiceMode")}</option>
      </select>
      <p id="mode-help" class="caption">${savedMode === "voice" ? tr("voiceModeHelp") : tr("clickModeHelp")}</p>
      <div id="mic-status" class="caption" role="status">${tr("micPermission")}: ${recognitionSupported ? tr("micNotRequested") : tr("micUnavailable")}</div>
      <button class="btn" id="open-interview">${sessionStorage.getItem("mk_iv") ? tr("continueInterview") : tr("startInterview")}</button>
      ${!me ? `<button class="btn btn-outline" id="guest-interview" type="button">${tr("guestContinue")}</button><p class="caption">${tr("guestRetention")}</p>` : ""}
    </div>
  `);
  document.getElementById("input-mode").onchange = event => {
    localStorage.setItem("mk_input_mode", event.target.value === "voice" ? "voice" : "click");
    document.getElementById("mode-help").textContent = event.target.value === "voice" ? tr("voiceModeHelp") : tr("clickModeHelp");
    document.getElementById("mic-status").textContent = `${tr("micPermission")}: ${event.target.value === "voice" ? (recognitionSupported ? tr("micNotRequested") : tr("micUnavailable")) : tr("micNotRequested")}`;
  };
  document.getElementById("open-interview").onclick = () => {
    localStorage.setItem("mk_input_mode", document.getElementById("input-mode").value);
    if (me) { sessionStorage.setItem("mk_start_interview", "1"); location.href = "index.html"; }
    else location.href = "login.html?next=interview.html";
  };
  document.getElementById("guest-interview")?.addEventListener("click", async e => {
    e.currentTarget.disabled = true;
    try {
      const result = await api("/auth/guest", { method: "POST" });
      localStorage.setItem("mk_input_mode", document.getElementById("input-mode").value);
      setToken(result.token); sessionStorage.setItem("mk_start_interview", "1"); location.href = "index.html";
    } catch (err) { e.currentTarget.disabled = false; alert(patientError(err)); }
  });
}

async function renderReports() {
  const me = await requireUser(); if (!me) return;
  let docs = [];
  let docsError = "";
  try { docs = await api("/documents"); } catch (e) { docsError = e.message; }
  pageShell("Medical Reports", "reports", `
    <p class="eyebrow">${tr("medicalReports")}</p><h1>${tr("Uploaded Documents")}</h1>
    <p class="subtitle">${PATIENT_I18N[getPatientLanguage()].docsS}</p>
    <div class="card">
      <label class="input-label" for="report-file">${tr("Choose a document")}</label>
      <input id="report-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt" multiple>
      <p class="caption">${PATIENT_I18N[getPatientLanguage()].maxUpload}</p>
      <button class="btn" id="upload-report" type="button">${PATIENT_I18N[getPatientLanguage()].uploadReports}</button>
      <p id="report-status" class="caption" aria-live="polite"></p>
    </div>
    ${docsError ? `<div class="alert alert-urgent" role="alert">${tr("documentsLoadFailed")}: ${esc(docsError)}</div>` : `<div class="card"><h2>${tr("uploadedDocuments")}</h2>
      ${docs.length ? `<div class="document-list">${docs.map(d => `<details class="document-row"><summary><b>${esc(d.filename || d.name || tr("document"))}</b><span class="chip">${esc(tr(d.processing_status || d.doc_type || "uploaded"))}</span></summary>
        <p class="caption">${tr("documentDate")}: ${esc(d.date || tr("Not extracted"))} · ${tr("extractionEngine")}: ${esc(d.engine || tr("Not reported"))} · ${tr("uploadDate")}: ${esc(d.created ? new Date(d.created * 1000).toLocaleString(getPatientLanguage() === "hi" ? "hi-IN" : "en-IN") : tr("Not recorded"))}</p>
        <p class="caption">${tr("documentCategory")}: ${esc(tr(d.doc_type || "Unclassified"))}</p>
        <p class="caption">${tr("extractionStatus")}: ${esc(tr(d.processing_status || "needs_review"))}</p>
        ${d.processing_error ? `<p class="alert alert-urgent" role="status">${d.processing_status === "failed" ? tr("extractionFailed") : tr("extractionPartial")}<br>${esc(patientError(d.processing_error))}</p>` : ""}
        ${d.has_original ? `<button class="btn btn-outline btn-sm" type="button" data-report-download="${d.id}" data-filename="${esc(d.filename)}">${tr("viewDownloadOriginal")}</button>` : ""}
        <label class="input-label" for="category-${d.id}">${tr("documentCategory")}</label>
        <select id="category-${d.id}" data-document-category="${d.id}">
          ${[["lab_report", "Laboratory report"], ["prescription", "Prescription"], ["discharge_summary", "Discharge summary"], ["other", "Other"]].map(([value, label]) => `<option value="${value}" ${d.doc_type === value ? "selected" : ""}>${tr(label)}</option>`).join("")}
        </select>
        <button class="btn btn-outline btn-sm" type="button" data-document-save-category="${d.id}">${tr("saveCategory")}</button>
        ${d.processing_status === "failed" ? `<label class="input-label" for="replacement-${d.id}">${tr("Optional: choose an unlocked or corrected replacement file")}</label><input id="replacement-${d.id}" type="file" data-document-replacement="${d.id}" accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.txt"><button class="btn btn-outline btn-sm" type="button" data-document-retry="${d.id}">${tr("retryExtraction")}</button>` : ""}
        <button class="btn btn-outline btn-sm" type="button" data-document-delete="${d.id}">${tr("removeDocument")}</button>
        ${d.text ? `<details><summary>${tr("extractedText")}</summary><pre class="document-preview">${esc(d.text)}</pre></details>` : `<p class="caption">${tr("noExtractedText")}</p>`}
        ${d.entities?.diagnoses?.length ? `<h3>${tr("Diagnoses mentioned")}</h3><p>${d.entities.diagnoses.map(esc).join(", ")}</p>` : ""}
        ${d.entities?.medications?.length ? `<h3>${tr("Medication mentions")}</h3><ul>${d.entities.medications.map(m => `<li>${esc(m.name)} ${esc(m.dose || "")} ${esc(m.frequency || "")} · ${esc(tr(m.status || "reported"))}</li>`).join("")}</ul>` : ""}
        ${d.entities?.allergies?.length ? `<h3>${tr("Allergy mentions")}</h3><ul>${d.entities.allergies.map(esc).map(x => `<li>${x}</li>`).join("")}</ul>` : ""}
        ${d.entities?.labs?.length ? `<h3>${tr("Laboratory findings")}</h3><div class="table-wrap"><table class="stack-table"><thead><tr><th>${tr("Test")}</th><th>${tr("Value")}</th><th>${tr("Reference range")}</th><th>${tr("Uncertainty")}</th></tr></thead><tbody>${d.entities.labs.map(l => `<tr><td data-label="${tr("Test")}">${esc(l.test)}</td><td data-label="${tr("Value")}">${esc(l.value)} ${esc(l.unit)}</td><td data-label="${tr("Reference range")}">${esc(l.ref || tr("Not provided"))}</td><td data-label="${tr("Uncertainty")}">${esc(l.uncertainty || l.reference_source || tr("Not reported"))}</td></tr>`).join("")}</tbody></table></div>` : `<p class="caption">${tr("noFindings")}</p>`}
      </details>`).join("")}</div>` : `<p class="empty-state">${tr("No documents uploaded yet.")}</p>`}</div>`}
    </div>
  `);
  document.querySelectorAll("[data-report-download]").forEach(button => button.onclick = async () => {
    try { await downloadDocument("/documents/" + button.dataset.reportDownload + "/file", button.dataset.filename); }
    catch (e) { document.getElementById("report-status").textContent = tr("documentDownloadFailed") + ": " + patientError(e); }
  });
  document.querySelectorAll("[data-document-save-category]").forEach(button => button.onclick = async () => {
    const select = document.querySelector(`[data-document-category="${button.dataset.documentSaveCategory}"]`);
    const status = document.getElementById("report-status");
    button.disabled = true;
    try {
      await api("/documents/" + button.dataset.documentSaveCategory, {
        method: "PUT", json: { doc_type: select.value }
      });
      status.textContent = PATIENT_I18N[getPatientLanguage()].categoryUpdated;
    } catch (e) { status.textContent = PATIENT_I18N[getPatientLanguage()].categoryFailed + ": " + patientError(e); }
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
      status.textContent = result.processing_status === "failed" ? `${tr("retryFailed")}: ${patientError(result.processing_error)}` : tr("Document extraction retried.");
      await renderReports();
    } catch (e) { status.textContent = `${tr("retryFailed")}: ${patientError(e)}`; button.disabled = false; }
  });
  document.querySelectorAll("[data-document-delete]").forEach(button => button.onclick = async () => {
    const status = document.getElementById("report-status");
    if (!window.confirm(PATIENT_I18N[getPatientLanguage()].removeConfirm)) return;
    button.disabled = true;
    try {
      await api("/documents/" + button.dataset.documentDelete, { method: "DELETE" });
      status.textContent = PATIENT_I18N[getPatientLanguage()].documentRemoved;
      await renderReports();
    } catch (e) { status.textContent = `${PATIENT_I18N[getPatientLanguage()].removalFailed}: ${patientError(e)}`; button.disabled = false; }
  });
  document.getElementById("upload-report").onclick = async () => {
    const files = Array.from(document.getElementById("report-file").files || []), status = document.getElementById("report-status");
    if (!files.length) { status.textContent = PATIENT_I18N[getPatientLanguage()].chooseAtLeastOne; return; }
    const data = new FormData(); files.forEach(file => data.append("files", file)); status.textContent = `${PATIENT_I18N[getPatientLanguage()].processingDocuments} (${files.length})`;
    try {
      const result = await api("/documents/batch", { body: data });
      status.textContent = `${result.succeeded} ${tr("processed")}, ${result.failed} ${tr("failed")}. ${tr("Each document shows its extraction status below.")}`;
      await renderReports();
    }
    catch (e) { status.textContent = `${PATIENT_I18N[getPatientLanguage()].uploadFailed}: ${patientError(e)}`; }
  };
}

async function renderTimeline() {
  const me = await requireUser(); if (!me) return;
  let records = [], docs = [];
  try { [records, docs] = await Promise.all([api("/records"), api("/documents")]); }
  catch (e) { pageError(`${PATIENT_I18N[getPatientLanguage()].timelineFailed}: ${e.message}`); return; }
  const events = [
    ...records.map(r => ({ kind: "Encounter", date: r.created, description: `${tr("encounter")} ${r.token_no}`, detail: `${tr("priority")}: ${tr(["", "Emergency", "Urgent", "Routine"][r.priority] || "Not reported")} · ${tr("status")}: ${tr(r.status)}` })),
    ...docs.map(d => ({ kind: "Document", date: d.created, description: d.filename, detail: `${tr(d.doc_type || "Unclassified")} · ${tr(d.processing_status)}`, id: d.id, hasOriginal: d.has_original }))
  ].filter(item => Number.isFinite(Number(item.date))).sort((a, b) => Number(b.date) - Number(a.date));
  pageShell("Health Timeline", "timeline", `<p class="eyebrow">${tr("documentTimeline")}</p><h1>${tr("recordedHistory")}</h1><p class="subtitle">${PATIENT_I18N[getPatientLanguage()].timelineDisclaimer}</p>
    <div class="card">${events.length ? `<div class="document-list">${events.map(item => `<article class="document-row"><span class="chip">${tr(item.kind)}</span><strong>${esc(item.description)}</strong><span>${new Date(Number(item.date) * 1000).toLocaleString(getPatientLanguage() === "hi" ? "hi-IN" : "en-IN")}</span><span class="caption">${esc(item.detail)}</span>${item.hasOriginal ? `<button class="btn btn-outline btn-sm" type="button" data-timeline-download="${item.id}" data-filename="${esc(item.description)}">${tr("downloadSource")}</button>` : ""}</article>`).join("")}</div>` : `<p class="empty-state">${tr("No encounters or documents are available yet.")}</p>`}</div>`);
  document.querySelectorAll("[data-timeline-download]").forEach(button => button.onclick = async () => {
    try { await downloadDocument("/documents/" + button.dataset.timelineDownload + "/file", button.dataset.filename); }
    catch (e) { alert(`${PATIENT_I18N[getPatientLanguage()].documentDownloadFailed}: ${e.message}`); }
  });
}

async function renderSummary() {
  const me = await requireUser(); if (!me) return;
  let records = [];
  try { records = await api("/records"); } catch (e) { pageError(`${PATIENT_I18N[getPatientLanguage()].summaryRecordsFailed}: ${e.message}`); return; }
  let report = null;
  if (records[0]) {
    try { report = (await api("/records/" + records[0].id)).clinical_report; }
    catch (e) { pageError(`${PATIENT_I18N[getPatientLanguage()].latestSummaryFailed}: ${e.message}`); return; }
  }
  pageShell("My Summary", "summary", `<p class="eyebrow">${tr("summaryEyebrow")}</p><h1>${tr("clinicalSummary")}</h1><p class="subtitle">${PATIENT_I18N[getPatientLanguage()].summaryDisclaimer}</p>${report ? renderClinicalReport(report, { mode: "patient" }) : `<div class="empty-state">${PATIENT_I18N[getPatientLanguage()].submitToCreateSummary}</div>`}`);
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
