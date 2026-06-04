from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from pathlib import Path
import pandas as pd
from app.hooks import bus

app = FastAPI(title="FinAgent")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return HTMLResponse(Path("static/index.html").read_text())


@app.post("/analyze/{ticker}")
async def analyze(ticker: str):
    from app.orchestrator import run_pipeline
    asyncio.create_task(run_pipeline(ticker.upper()))
    return {"status": "started", "ticker": ticker.upper()}


@app.post("/analyze-all")
async def analyze_all():
    from app.orchestrator import run_pipeline
    import json as j
    tickers = list(j.loads(Path("data/company_urls.json").read_text()).keys())
    for t in tickers:
        asyncio.create_task(run_pipeline(t))
    return {"status": "started", "count": len(tickers)}


@app.get("/stream/{ticker}")
async def stream(ticker: str):
    # Subscribe BEFORE snapshotting history — single event loop guarantees no gap
    q = bus.subscribe(ticker)
    history = bus.history(ticker)

    async def generator():
        try:
            # Replay everything that already happened (fixes late-connection race)
            finished = False
            for event in history:
                yield {"data": json.dumps(event)}
                if event["event"] in ("pipeline_complete", "pipeline_error"):
                    finished = True
            if finished:
                return
            # Then stream live events
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=600)
                    yield {"data": json.dumps(event)}
                    if event["event"] in ("pipeline_complete", "pipeline_error"):
                        break
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"event": "ping", "data": {}})}
        finally:
            bus.unsubscribe(ticker, q)

    return EventSourceResponse(generator())


@app.get("/evals")
async def get_evals():
    import math
    result = {}
    evals_dir = Path("data/evals")
    if evals_dir.exists():
        for csv in evals_dir.glob("*.csv"):
            df = pd.read_csv(csv)
            # pandas coerces None back to NaN in float columns — sanitize at the
            # record level instead (Starlette serializes with allow_nan=False)
            records = df.to_dict(orient="records")
            result[csv.stem] = [
                {k: (None if isinstance(v, float) and math.isnan(v) else v)
                 for k, v in row.items()}
                for row in records
            ]
    return result


_CONTEXT_MARKERS = (
    "=== ANNUAL REPORT TEXT",
    "=== STRUCTURED FINANCIALS",
    "=== MD&A / OUTLOOK EXCERPTS",
    "=== 2024 DAILY CLOSING PRICES",
    "=== EVALUATION DATA",
)


def _condense_prompt(prompt: str) -> str:
    """Keep the full prompt TEMPLATE; summarize the injected data context.
    The template is the experimental design; the context is reproducible data."""
    for marker in _CONTEXT_MARKERS:
        idx = prompt.find(marker)
        if idx != -1:
            head = prompt[:idx].rstrip()
            tail = prompt[idx:]
            label_end = tail.find("===", 3)
            label = tail[:label_end + 3] if label_end != -1 else marker + " ==="
            omitted = len(tail)
            return (f"{head}\n\n{label}\n"
                    f"[… {omitted:,} characters of injected data context omitted for brevity — "
                    f"full text logged in data/prompts/ …]")
    return prompt


@app.get("/prompts/{ticker}/print")
async def print_prompts(ticker: str, full: int = 0):
    """Print-friendly record of prompts & responses.
    Default (condensed): full prompt templates + full responses, data context summarized
    — one entry per agent type (~6-8 pages). Pass ?full=1 for the unabridged version."""
    t = ticker.upper()
    logs = []
    for f in sorted(Path("data/prompts").glob(f"{t}_*.jsonl")):
        logs.extend(json.loads(l) for l in f.read_text().splitlines() if l.strip())
    logs.sort(key=lambda e: e.get("timestamp", ""))

    if not full:
        # Only the 7 DISTINCT prompt templates (alt-strategy critique/revise use
        # templates identical to baseline; retries repeat the original prompt)
        core_agents = ["extractor", "forecaster_baseline", "forecaster_alt_strategy",
                       "forecaster_alt_v2", "critique_baseline", "revise_baseline",
                       "stock_predictor"]
        seen = set()
        by_agent = {}
        for e in logs:
            agent = e.get("agent", "")
            if agent in core_agents and agent not in seen:
                seen.add(agent)
                e = dict(e)
                e["prompt"] = _condense_prompt(e.get("prompt", ""))
                by_agent[agent] = e
        logs = [by_agent[a] for a in core_agents if a in by_agent]

    import html as html_mod
    cards = []
    for e in logs:
        cards.append(f"""
        <div class="card">
          <div class="head">
            <span class="agent">{html_mod.escape(e.get('agent',''))}</span>
            <span class="meta">{html_mod.escape(e.get('model',''))} · FY{e.get('year')} ·
              {html_mod.escape((e.get('timestamp') or '')[:19].replace('T',' '))}</span>
          </div>
          <div class="label">QUERY (full template; injected data context summarized unless ?full=1)</div>
          <pre class="q">{html_mod.escape(e.get('prompt',''))}</pre>
          <div class="label">RESPONSE (complete)</div>
          <pre class="r">{html_mod.escape(e.get('response',''))}</pre>
        </div>""")

    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>{t} — Complete Queries &amp; Responses</title>
    <style>
      body{{font-family:-apple-system,'Segoe UI',sans-serif;max-width:900px;margin:24px auto;
           padding:0 16px;color:#1e293b}}
      h1{{font-size:20px}} .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
      .card{{border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:20px;
            page-break-inside:avoid}}
      .head{{display:flex;justify-content:space-between;flex-wrap:wrap;margin-bottom:10px}}
      .agent{{font-weight:700;color:#1a5276;font-size:14px}}
      .meta{{color:#94a3b8;font-size:11px;font-family:monospace}}
      .label{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#64748b;margin:10px 0 4px}}
      pre{{font-family:ui-monospace,Menlo,monospace;font-size:10px;line-height:1.5;
          white-space:pre-wrap;word-break:break-word;border-radius:6px;padding:10px;margin:0}}
      .q{{background:#f8fafc;border:1px solid #e2e8f0}}
      .r{{background:#f0fdf4;border:1px solid #bbf7d0}}
      @media print{{ .card{{page-break-inside:auto;padding:8px 10px;margin-bottom:10px}} pre{{font-size:7.5px;line-height:1.35;padding:6px}} .sub{{font-size:10px}} h1{{font-size:15px}} body{{margin:8px auto}} }}
    </style></head><body>
    <h1>📝 {t} — Complete LLM Queries &amp; Responses</h1>
    <p class="sub">{len(logs)} interactions, logged verbatim by FinAgent's Prompt Vault.
    Identical prompt templates were used across all 20 companies and both base years. Shown: the 7 distinct templates (critique/revise for alternate strategies reuse the baseline templates; unit-correction retries repeat the original prompt with a correction suffix).
    Condensed view: one entry per agent type, complete prompt templates, complete responses; bulk data context summarized. Append <b>?full=1</b> to the URL for the unabridged version. Print this page (Cmd+P → Save as PDF).</p>
    {''.join(cards)}
    </body></html>"""
    return HTMLResponse(page)


@app.get("/prompts/{ticker}")
async def get_prompts(ticker: str):
    logs = []
    for f in Path("data/prompts").glob(f"{ticker}_*.jsonl"):
        logs.extend(json.loads(l) for l in f.read_text().splitlines() if l.strip())
    return logs


@app.post("/generate-report")
async def generate_report_endpoint():
    """Generate full 20-company report from all available eval data."""
    from app.orchestrator import generate_report_only
    asyncio.create_task(generate_report_only())
    return {"status": "generating"}


@app.post("/generate-report/{ticker}")
async def generate_company_report_endpoint(ticker: str):
    """Generate a single-company report immediately (no background task needed)."""
    from app.agents.report_writer import generate_company_report
    try:
        path = generate_company_report(ticker.upper())
        return {"status": "done", "ticker": ticker.upper(), "file": path.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{ticker}")
async def company_status(ticker: str):
    """What state is this company in? Drives the UI's call-to-action."""
    t = ticker.upper()
    has_forecast = any(Path("data/responses").glob(f"{t}_*_forecast.json"))
    report = Path(f"output/report_{t}.docx")
    return {"analyzed": has_forecast, "report_ready": report.exists()}


@app.get("/report/status")
async def report_status():
    report_path = Path("output/report.docx")
    if report_path.exists():
        return {"ready": True, "size_kb": report_path.stat().st_size // 1024}
    return {"ready": False}


@app.get("/report/download/{ticker}")
async def download_company_report(ticker: str):
    from fastapi.responses import FileResponse
    report_path = Path(f"output/report_{ticker.upper()}.docx")
    if not report_path.exists():
        raise HTTPException(status_code=404,
            detail=f"No report for {ticker} yet. Run the pipeline first.")
    return FileResponse(str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"FinAgent_{ticker.upper()}_Report.docx")


@app.get("/report/download")
async def download_report():
    from fastapi.responses import FileResponse
    report_path = Path("output/report.docx")
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report not generated yet. Run the pipeline first, then click 'Generate report'."
        )
    return FileResponse(
        str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="FinA_Group11_Report.docx",
    )
