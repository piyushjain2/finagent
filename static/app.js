const COMPANIES = [
  {t:"RELIANCE",cap:"L"},{t:"INFY",cap:"L"},{t:"TCS",cap:"L"},
  {t:"HDFCBANK",cap:"L"},{t:"ICICIBANK",cap:"L"},{t:"SBIN",cap:"L"},
  {t:"ITC",cap:"L"},{t:"LT",cap:"L"},{t:"NTPC",cap:"L"},{t:"ONGC",cap:"L"},
  {t:"REC",cap:"M"},{t:"PFC",cap:"M"},{t:"HUDCO",cap:"M"},
  {t:"IREDA",cap:"M"},{t:"IFCI",cap:"M"},
  {t:"KEC",cap:"S"},{t:"TEXRAIL",cap:"S"},{t:"POWERMECH",cap:"S"},
  {t:"VINDHYATEL",cap:"S"},{t:"SKIPPER",cap:"S"}
];

// State
let activeTicker = null;
const eventSources = {};
const companyStatus = {};  // ticker -> {dot: 'running'|'done'|'error', preview: string}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function renderList(companies) {
  const list = document.getElementById("companyList");
  const grouped = {L: [], M: [], S: []};
  companies.forEach(c => grouped[c.cap].push(c));
  const labels = {L: "Large-cap", M: "Mid-cap", S: "Small-cap"};
  let html = "";
  for (const cap of ["L","M","S"]) {
    if (!grouped[cap].length) continue;
    html += `<div class="sidebar-section">${labels[cap]}</div>`;
    grouped[cap].forEach(c => {
      const st = companyStatus[c.t] || {};
      html += `
        <div class="company-item ${activeTicker===c.t?'active':''}" onclick="selectCompany('${c.t}','${c.cap}')">
          <div class="c-avatar cap-${c.cap}">${c.t.slice(0,4)}</div>
          <div class="c-info">
            <div class="c-name">${c.t}</div>
            <div class="c-status" id="status-${c.t}">${st.preview||'Ready'}</div>
          </div>
          <div class="c-dot ${st.dot||''}" id="dot-${c.t}"></div>
        </div>`;
    });
  }
  list.innerHTML = html;
}

function filterList() {
  const q = document.getElementById("search").value.toLowerCase();
  renderList(COMPANIES.filter(c => c.t.toLowerCase().includes(q)));
}

function showAllCompanies() {
  document.getElementById("search").value = "";
  renderList(COMPANIES);
}

// ── Company selection ─────────────────────────────────────────────────────────

function selectCompany(ticker, cap) {
  activeTicker = ticker;
  document.getElementById("headerName").textContent = ticker;
  document.getElementById("headerAvatar").textContent = ticker.slice(0,3);
  const capLabel = cap==="L" ? "Large-cap" : cap==="M" ? "Mid-cap" : "Small-cap";
  document.getElementById("headerStatus").textContent = `NSE · ${capLabel}`;
  document.getElementById("pipelineBar").style.display = "flex";
  document.getElementById("messages").innerHTML = "";
  resetPipeline();
  renderList(COMPANIES);

  // If the pipeline is mid-run for this ticker, just show progress.
  const st = companyStatus[ticker];
  if (st && st.dot === "running") {
    addBubble(`⟳ ${ticker} pipeline is running — progress will stream here.`, "bot");
    return;
  }

  // Otherwise ask the server what state this company is in and offer ONE clear action.
  fetch(`/status/${ticker}`).then(r => r.json()).then(s => {
    if (s.report_ready) {
      addBubble(
        `<b>${ticker}</b> has been analyzed and its report is ready.<br><br>
         <button class="btn" onclick="window.location.href='/report/download/${ticker}'">⬇ Download report</button>
         <button class="btn secondary" onclick="rerunCompany('${ticker}')">🔁 Re-run analysis</button>`, "bot");
    } else if (s.analyzed) {
      addBubble(
        `<b>${ticker}</b> has analysis data but no report yet.<br><br>
         <button class="btn" onclick="generateCompanyReport('${ticker}')">📄 Generate report</button>
         <button class="btn secondary" onclick="rerunCompany('${ticker}')">🔁 Re-run analysis</button>`, "bot");
    } else {
      addBubble(
        `Ready to analyze <b>${ticker}</b> — downloads annual reports, runs the 9-agent pipeline,
         and produces a forecast report automatically.<br><br>
         <button class="btn" onclick="analyzeTicker('${ticker}')">▶ Analyze ${ticker}</button>`, "bot");
    }
  }).catch(() => {
    addBubble(`<button class="btn" onclick="analyzeTicker('${ticker}')">▶ Analyze ${ticker}</button>`, "bot");
  });
}

function resetPipeline() {
  document.querySelectorAll(".pipe-step").forEach(s => {
    s.classList.remove("done","active");
  });
}

// ── Analysis ──────────────────────────────────────────────────────────────────

function analyzeTicker(ticker) {
  setCompanyStatus(ticker, "running", "Starting pipeline…");
  addBubble(`▶ Starting full analysis for <b>${ticker}</b>…`, "bot");
  fetch(`/analyze/${ticker}`, {method:"POST"})
    .then(() => startStream(ticker))
    .catch(e => addBubble(`Error starting: ${e}`, "bot"));
}

function rerunCompany(ticker) {
  addBubble(`🔁 Re-running analysis for <b>${ticker}</b> (cached stages are reused)…`, "bot");
  setCompanyStatus(ticker, "running", "Re-running…");
  fetch(`/analyze/${ticker}`, {method:"POST"})
    .then(() => startStream(ticker))
    .catch(e => addBubble(`Error: ${e}`, "bot"));
}

function analyzeAll() {
  addBubble("▶ Starting pipeline for all 20 companies…", "bot");
  fetch("/analyze-all", {method:"POST"})
    .then(r => r.json())
    .then(d => {
      COMPANIES.forEach(c => {
        setCompanyStatus(c.t, "running", "Queued…");
        startStream(c.t);
      });
      addBubble(`▶ ${d.count} pipelines started. Click any company to see its progress.`, "bot");
    });
}

function generateCompanyReport(ticker) {
  fetch(`/generate-report/${ticker}`, {method:"POST"})
    .then(r => r.json())
    .then(d => {
      if (d.status === "done") {
        addBubble(
          `✅ <b>${ticker}</b> report ready.<br><br>
           <button class="btn" onclick="window.location.href='/report/download/${ticker}'">⬇ Download ${ticker} report</button>
           <button class="btn secondary" onclick="showEvals()">📊 View evals</button>`, "bot");
      } else {
        addBubble(`❌ Report failed: ${d.detail || "unknown error"}`, "bot");
      }
    })
    .catch(e => addBubble(`❌ Could not generate report: ${e}`, "bot"));
}

function generateReport() {
  addBubble("⟳ Generating commentary and report — this may take a minute…", "bot");
  fetch("/generate-report", {method:"POST"})
    .then(r => r.json())
    .then(d => {
      if (d.status === "generating") {
        addBubble("⟳ Report generation started in background. Watch for the download link…", "bot");
        // Poll until the report is ready
        const poll = setInterval(() => {
          fetch("/report/status").then(r => r.json()).then(s => {
            if (s.ready) {
              clearInterval(poll);
              addBubble(`✅ Report ready! <a href="/report/download" target="_blank">⬇ Download report.docx</a>`, "bot");
            } else if (s.error) {
              clearInterval(poll);
              addBubble(`❌ Report generation failed: ${s.error}`, "bot");
            }
          }).catch(() => clearInterval(poll));
        }, 3000);
      }
    })
    .catch(e => addBubble(`❌ Could not start report generation: ${e}`, "bot"));
}

function downloadReport() {
  fetch("/report/status").then(r => r.json()).then(s => {
    if (s.ready) {
      window.location.href = "/report/download";
    } else {
      addBubble("⚠ No report ready yet. Analyze a company first, then click <b>📄 Generate report</b> in the completion bubble or the quick chips.", "bot");
    }
  }).catch(() => {
    addBubble("⚠ Could not check report status. Make sure the server is running.", "bot");
  });
}

// ── SSE streaming ─────────────────────────────────────────────────────────────

function startStream(ticker) {
  if (eventSources[ticker]) { eventSources[ticker].close(); }
  const es = new EventSource(`/stream/${ticker}`);
  eventSources[ticker] = es;
  es.onmessage = e => handleEvent(ticker, JSON.parse(e.data));
  es.onerror = () => { es.close(); delete eventSources[ticker]; };
}

const STEP_MAP = {
  on_pdf_fetched:"ps1", on_rag_indexed:"ps2",
  on_extract_complete:"ps3", on_forecast_ready:"ps4",
  on_forecast_revised:"ps5", on_actuals_fetched:"ps6",
  on_prices_ready:"ps6", on_metrics_ready:"ps7",
  on_commentary_ready:"ps8", pipeline_complete:"ps9"
};

function handleEvent(ticker, payload) {
  const ev = payload.event, data = payload.data || {};

  // Update sidebar status for all companies (not just active)
  const previewMap = {
    agent_start: "⟳ Starting…",
    on_pdf_fetched: `⟳ Downloading PDFs…`,
    on_rag_indexed: "⟳ Indexing…",
    on_extract_complete: "⟳ Extracting financials…",
    on_forecast_ready: "⟳ Forecasting…",
    on_forecast_revised: "⟳ Critique/Revise…",
    on_actuals_fetched: "⟳ Fetching market data…",
    on_metrics_ready: "⟳ Computing metrics…",
    pipeline_complete: "✅ Done",
    pipeline_error: "❌ Error",
    warning: "⚠ Warning",
  };
  if (previewMap[ev]) {
    const dot = ev === "pipeline_complete" ? "done" : ev === "pipeline_error" ? "error" : "running";
    setCompanyStatus(ticker, dot, previewMap[ev]);
  }

  // Only update pipeline bar + chat for active ticker
  if (ticker !== activeTicker) return;

  // Advance pipeline bar
  const stepId = STEP_MAP[ev];
  if (stepId) {
    document.querySelectorAll(".pipe-step").forEach(s => s.classList.remove("active"));
    const el = document.getElementById(stepId);
    if (el) {
      // Mark all prior steps done
      let found = false;
      document.querySelectorAll(".pipe-step").forEach(s => {
        if (s.id === stepId) { found = true; s.classList.add("active"); }
        else if (!found) s.classList.add("done");
      });
    }
    if (ev === "pipeline_complete") {
      document.querySelectorAll(".pipe-step").forEach(s => { s.classList.remove("active"); s.classList.add("done"); });
    }
  }

  // Build chat bubble content
  let html = "";
  const now = new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});

  switch(ev) {
    case "on_pdf_fetched":
      html = `<span class="agent-label al-pdf">① PDF Fetcher</span><br>✅ ${ticker}_${data.year}.pdf downloaded`; break;
    case "on_rag_indexed":
      html = `<span class="agent-label al-rag">② RAG</span><br>✅ ${data.n_chunks} chunks indexed`; break;
    case "on_extract_complete":
      const yrs = (data.data?.years||[]).map(y=>`FY${y.year}: ₹${(y.revenue_cr||0).toLocaleString()}Cr`).join(" | ");
      html = `<span class="agent-label al-ext">③ Extractor</span><br>✅ FY${data.year} financials extracted${yrs ? `<br><small>${yrs}</small>` : ""}`; break;
    case "on_forecast_ready":
      html = `<span class="agent-label al-fore">④ Forecast</span><br>✅ Baseline + Alt strategy complete (base ${data.base_year})`; break;
    case "on_forecast_revised":
      html = `<span class="agent-label al-crit">⑤ Critique/Revise</span><br>✅ Confidence ranges added (base ${data.base_year})`; break;
    case "on_actuals_fetched":
    case "on_prices_ready":
      html = `<span class="agent-label al-mkt">⑥ Market Data</span><br>✅ Actuals + 2024 prices fetched`; break;
    case "on_metrics_ready":
      html = `<span class="agent-label al-met">⑦ Metrics</span><br>✅ Accuracy tables updated`; break;
    case "pipeline_complete":
      html = `<span class="agent-label al-rep">✅ Pipeline Complete</span><br>
        <strong>${ticker}</strong> analysis done — generating report…`;
      // Auto-generate the per-company report; download link appears when ready
      setTimeout(() => generateCompanyReport(ticker), 500);
      break;
    case "pipeline_error":
      html = `⚠️ Pipeline error: ${data.error||"unknown"}`; break;
    case "warning":
      html = `<div class="warn">⚠ ${data.year||""} ${data.msg||""}</div>`; break;
    default: return;
  }
  addBubble(html, "bot");
}

function addBubble(html, type) {
  const msgs = document.getElementById("messages");
  const now = new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
  msgs.innerHTML += `<div class="bubble-wrap ${type}">
    <div class="bubble ${type}">${html}<div class="bubble-time">${now}</div></div></div>`;
  msgs.scrollTop = msgs.scrollHeight;
}

function setCompanyStatus(ticker, dot, preview) {
  companyStatus[ticker] = {dot, preview};
  const dotEl = document.getElementById(`dot-${ticker}`);
  const statusEl = document.getElementById(`status-${ticker}`);
  if (dotEl) { dotEl.className = `c-dot ${dot}`; }
  if (statusEl) { statusEl.textContent = preview; }
}

// ── Input handling ────────────────────────────────────────────────────────────

function sendCommand() {
  const box = document.getElementById("inputBox");
  const text = box.textContent.trim();
  if (!text) return;
  box.textContent = "";
  addBubble(text, "user");
  const upper = text.toUpperCase();
  const match = COMPANIES.find(c => upper.includes(c.t));
  if (match) { analyzeTicker(match.t); return; }
  if (upper.includes("ALL")) { analyzeAll(); return; }
  if (upper.includes("REPORT")) { generateReport(); return; }
  if (upper.includes("EVAL")) { showEvals(); return; }
  addBubble("Type a company name (e.g. RELIANCE), 'analyze all', 'report', or 'evals'.", "bot");
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendCommand(); }
}

// ── Evals panel ───────────────────────────────────────────────────────────────

function showEvals() {
  fetch("/evals").then(r => r.json()).then(data => {
    let html = "";
    for (const [name, rows] of Object.entries(data)) {
      if (!rows.length) continue;
      html += `<div class="eval-section"><h3>${name.replace(/_/g," ")}</h3>
        <table class="eval-table"><thead><tr>
        ${Object.keys(rows[0]).map(k=>`<th>${k}</th>`).join("")}</tr></thead><tbody>
        ${rows.slice(0,30).map(r=>`<tr>${Object.values(r).map(v=>`<td>${v??""}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div>`;
    }
    document.getElementById("evalsBody").innerHTML = html || "<p style='padding:16px;color:#64748b'>No eval data yet. Run the pipeline first.</p>";
    document.getElementById("evalsPanel").classList.add("open");
  });
}

function closeEvals() { document.getElementById("evalsPanel").classList.remove("open"); }

function showPrompts() {
  if (!activeTicker) { alert("Select a company first."); return; }
  window.open(`/prompts/${activeTicker}`, "_blank");
}

// ── Init ──────────────────────────────────────────────────────────────────────
renderList(COMPANIES);
