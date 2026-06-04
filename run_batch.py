"""
Headless batch runner — no server/UI needed.

Runs the full pipeline for every Group 11 company (cached stages skip free),
then generates commentary + the single consolidated report.
At the end, prints exactly which PDFs are missing for manual download.

Usage:  python run_batch.py            # all 20
        python run_batch.py TCS LT     # specific tickers only
"""
import asyncio
import json
import sys
from pathlib import Path

TICKERS = list(json.loads(Path("data/company_urls.json").read_text()).keys())
PRIORITY_YEARS = [2021, 2022]            # forecasting inputs — required
ALL_YEARS = [2021, 2022, 2023, 2024, 2025]


async def main(selected: list[str]):
    from app.orchestrator import run_pipeline
    from app.agents.commentary import generate_commentary
    from app.agents.report_writer import generate_report
    import pandas as pd

    print(f"Running {len(selected)} companies: {', '.join(selected)}\n")

    for i, ticker in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {ticker} ...", flush=True)
        try:
            await run_pipeline(ticker)
            # Did it actually produce metrics?
            df = pd.read_csv("data/evals/forecast_accuracy.csv")
            if ticker in df["ticker"].unique():
                print(f"    ✅ {ticker} complete")
            else:
                print(f"    ⚠ {ticker} ran but produced no metrics (check PDFs)")
        except Exception as e:
            print(f"    ❌ {ticker} failed: {e}")

    # ── Final consolidated report ─────────────────────────────────────────
    print("\nGenerating commentary + consolidated report ...", flush=True)
    try:
        generate_commentary()
        path = generate_report()
        print(f"📄 Consolidated report: {path}")
    except Exception as e:
        print(f"⚠ Report generation: {e}")

    # ── Missing-PDF shopping list ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("MISSING PDFs (download manually → ~/Downloads/Reports)")
    print("=" * 60)
    any_missing = False
    for ticker in TICKERS:
        missing = [y for y in ALL_YEARS
                   if not (Path(f"data/pdfs/{ticker}_{y}.pdf").exists()
                           and Path(f"data/pdfs/{ticker}_{y}.pdf").stat().st_size > 10_000)]
        critical = [y for y in missing if y in PRIORITY_YEARS]
        if missing:
            any_missing = True
            tag = "🔴 BLOCKS FORECASTING" if critical else "🟡 actuals only"
            print(f"  {ticker:12s} missing {missing}  {tag}")
    if not any_missing:
        print("  None — all PDFs present!")


if __name__ == "__main__":
    selected = sys.argv[1:] if len(sys.argv) > 1 else TICKERS
    selected = [t.upper() for t in selected]
    asyncio.run(main(selected))
