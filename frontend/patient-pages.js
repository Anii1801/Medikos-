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
  let records = [];
  let recordsError = "";
  try { records = await api("/records"); } catch (e) { recordsError = e.message; }
  pageShell("Dashboard", "dashboard", `
    <p class="eyebrow">${tr("dashboardEyebrow")}</p>
    <h1>${tr("welcomeName")}${me.name ? ", " + esc(me.name.split(" ")[0]) : ""}</h1>
    <p class="subtitle">${tr("prepareConsultation")}</p>
    <div class="dashboard-actions">
      <a class="btn" href="interview.html">${sessionStorage.getItem("mk_iv") ? tr("continueInterview") : tr("startInterview")}</a>
    </div>
    <div class="patient-card-grid">
      <a class="patient-card" href="interview.html"><span class="action-icon">${ICONS.history}</span><h2>${tr("medicalHistory")}</h2><p>${tr("medicalHistoryHelp")}</p></a>
      <a class="patient-card" href="timeline.html"><span class="action-icon">${ICONS.timeline}</span><h2>${tr("timeline")}</h2><p>${records.length ? `${records.length} ${tr("encountersCount")}` : tr("noEncounters")}</p></a>
      <a class="patient-card" href="summary.html"><span class="action-icon">${ICONS.summary}</span><h2>${tr("mySummary")}</h2><p>${tr("summaryReviewHelp")}</p></a>
    </div>
    ${recordsError ? `<div class="alert alert-urgent mt" role="alert">${tr("recentActivity")}: ${esc(patientError(recordsError))}</div>` :
      records.length ? `<section class="card mt" aria-labelledby="recent-heading"><h2 id="recent-heading">${tr("recentActivity")}</h2><div class="document-list">${records.slice(0, 3).map(r => `<div class="document-row"><span>${tr("encounter")} ${esc(r.token_no)}</span><span class="chip">${esc(tr(r.status))}</span></div>`).join("")}</div></section>` : ""}
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
    else if (pageName === "timeline") await renderTimeline();
    else if (pageName === "summary") await renderSummary();
    else await renderDashboard();
  } catch (e) { pageError(e.message); }
}
bootPatientPage();
