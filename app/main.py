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
    result = {}
    evals_dir = Path("data/evals")
    if evals_dir.exists():
        for csv in evals_dir.glob("*.csv"):
            result[csv.stem] = pd.read_csv(csv).to_dict(orient="records")
    return result


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
