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
    q = bus.subscribe(ticker)

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=600)
                    yield {"data": json.dumps(event)}
                    if event["event"] == "pipeline_complete":
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
    from app.orchestrator import run_all_and_report
    import json as j
    tickers = list(j.loads(Path("data/company_urls.json").read_text()).keys())
    asyncio.create_task(run_all_and_report(tickers))
    return {"status": "generating"}


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
