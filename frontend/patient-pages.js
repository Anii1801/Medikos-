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
          ["summary.html", "My Summary", "summary"],
          ["settings.html", "Privacy & Consent", "settings"]
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
  let records = [];
  let recordsError = "";
  try { records = await api("/records"); } catch (e) { recordsError = e.message; }
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
      <a class="patient-card" href="reports.html"><span class="action-icon">${ICONS.reports}</span><h2>Medical Reports</h2><p>Upload and organize your medical documents.</p></a>
      <a class="patient-card" href="timeline.html"><span class="action-icon">${ICONS.timeline}</span><h2>Health Timeline</h2><p>${records.length ? `${records.length} recorded encounter${records.length === 1 ? "" : "s"}.` : "No encounters recorded yet."}</p></a>
      <a class="patient-card" href="summary.html"><span class="action-icon">${ICONS.summary}</span><h2>My Summary</h2><p>Review an available generated draft and its source information.</p></a>
    </div>
    ${recordsError ? `<div class="alert alert-urgent mt" role="alert">Recent activity could not be loaded: ${esc(recordsError)}</div>` :
      records.length ? `<section class="card mt" aria-labelledby="recent-heading"><h2 id="recent-heading">Recent activity</h2><div class="document-list">${records.slice(0, 3).map(r => `<div class="document-row"><span>Encounter ${esc(r.token_no)}</span><span class="chip">${esc(r.status)}</span></div>`).join("")}</div></section>` : ""}
  `);
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
      ${!me ? `<button class="btn btn-outline" id="guest-interview" type="button">Continue as guest</button><p class="caption">Guest sessions are wiped after submission, consistent with the current application policy.</p>` : ""}
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
      <input id="report-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt">
      <button class="btn" id="upload-report" type="button">Upload Report</button>
      <p id="report-status" class="caption" aria-live="polite"></p>
    </div>
    ${docsError ? `<div class="alert alert-urgent" role="alert">Documents could not be loaded: ${esc(docsError)}</div>` : `<div class="card"><h2>Uploaded documents</h2>
      ${docs.length ? `<div class="document-list">${docs.map(d => `<details class="document-row"><summary><b>${esc(d.filename || d.name || "Document")}</b><span class="chip">${esc(d.doc_type || "Uploaded")}</span></summary>
        <p class="caption">Source: ${esc(d.filename || "uploaded document")} · Extraction engine: ${esc(d.engine || "not reported")}</p>
        ${d.entities?.labs?.length ? `<h3>Laboratory findings</h3><div class="table-wrap"><table class="stack-table"><thead><tr><th>Test</th><th>Value</th><th>Reference range</th><th>Uncertainty</th></tr></thead><tbody>${d.entities.labs.map(l => `<tr><td data-label="Test">${esc(l.test)}</td><td data-label="Value">${esc(l.value)} ${esc(l.unit)}</td><td data-label="Reference range">${esc(l.ref || "Not provided")}</td><td data-label="Uncertainty">${esc(l.uncertainty || l.reference_source || "Not reported")}</td></tr>`).join("")}</tbody></table></div>` : `<p class="caption">No laboratory findings were extracted from this document.</p>`}
      </details>`).join("")}</div>` : `<p class="empty-state">No documents uploaded yet.</p>`}</div>`}
    </div>
  `);
  document.getElementById("upload-report").onclick = async () => {
    const file = document.getElementById("report-file").files[0], status = document.getElementById("report-status");
    if (!file) { status.textContent = "Choose a file first."; return; }
    const data = new FormData(); data.append("file", file); status.textContent = "Uploading…";
    try { await api("/documents", { body: data }); status.textContent = "Upload completed."; setTimeout(() => renderReports(), 400); }
    catch (e) { status.textContent = "Upload failed: " + e.message; }
  };
}

async function renderTimeline() {
  const me = await requireUser(); if (!me) return;
  let records = [];
  try { records = await api("/records"); } catch (_) {}
  pageShell("Health Timeline", "timeline", `<p class="eyebrow">HEALTH TIMELINE</p><h1>Your recorded history</h1><p class="subtitle">Available encounters and statuses from your account.</p>
    <div class="card">${records.length ? `<div class="table-wrap"><table class="stack-table"><thead><tr><th>Token</th><th>Date</th><th>Priority</th><th>Status</th></tr></thead><tbody>${records.map(r => `<tr><td data-label="Token">${esc(r.token_no)}</td><td data-label="Date">${new Date(r.created * 1000).toLocaleDateString("en-IN")}</td><td data-label="Priority">${esc(["", "Emergency", "Urgent", "Routine"][r.priority] || "—")}</td><td data-label="Status">${esc(r.status)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="empty-state">No encounters recorded yet.</p>`}</div>`);
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

async function renderSettings() {
  const me = await requireUser(); if (!me) return;
  let consent = {};
  try { consent = await api("/consent"); } catch (_) {}
  pageShell("Privacy & Consent", "settings", `<p class="eyebrow">PRIVACY & CONSENT</p><h1>Your privacy choices</h1><p class="subtitle">Review consent and data-handling information supported by your account.</p><div class="card"><h2>Data handling</h2><p>History capture and sharing require explicit consent. Guest sessions are wiped after submission. Image bytes are not stored.</p><label class="consent-item"><input type="checkbox" id="consent-history" ${consent.history_capture ? "checked" : ""}> I consent to my health information being recorded for my doctor.</label><label class="consent-item"><input type="checkbox" id="consent-abdm" ${consent.abdm_share ? "checked" : ""}> I consent to sharing with the hospital system and ABHA record.</label><p id="consent-status" class="caption" aria-live="polite"></p><button class="btn btn-outline" id="manage-consent" type="button">Save consent</button></div>`);
  document.getElementById("manage-consent").onclick = async () => {
    const status = document.getElementById("consent-status");
    try { await api("/consent", { json: { purpose: "history_capture", granted: document.getElementById("consent-history").checked }}); await api("/consent", { json: { purpose: "abdm_share", granted: document.getElementById("consent-abdm").checked }}); status.textContent = "Consent updated."; }
    catch (e) { status.textContent = e.message; }
  };
}

async function bootPatientPage() {
  try {
    if (pageName === "dashboard") await renderDashboard();
    else if (pageName === "interview") await renderInterview();
    else if (pageName === "reports") await renderReports();
    else if (pageName === "timeline") await renderTimeline();
    else if (pageName === "summary") await renderSummary();
    else await renderSettings();
  } catch (e) { pageError(e.message); }
}
bootPatientPage();
