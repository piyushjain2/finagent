# app/orchestrator.py
import asyncio
import json
from pathlib import Path

from app.hooks import bus
from app.agents.pdf_fetcher import fetch_pdf
from app.agents.rag_processor import process_pdf
from app.agents.extractor import extract_financials
from app.agents.forecaster import run_forecast, run_stock_prediction
from app.agents.critique_revise import critique_forecast, revise_forecast
from app.agents.market_data import fetch_actuals, fetch_prices, fetch_nifty50, fetch_earnings_dates
from app.agents.metrics import (
    compute_forecast_accuracy, compute_earnings_surprise,
    compute_trading_returns, compute_stock_prediction_accuracy,
    compute_cap_summary,
)
from app.agents.commentary import generate_commentary
from app.agents.report_writer import generate_report

COMPANY_URLS = Path("data/company_urls.json")
FORECAST_BASE_YEARS = [2021, 2022]
ALL_YEARS = [2021, 2022, 2023, 2024, 2025]   # 2025 = FY2024-25, available as of 2026

_LARGE = {"RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "LT", "NTPC", "ONGC"}
_MID   = {"REC", "PFC", "HUDCO", "IREDA", "IFCI"}

def _get_cap_size(ticker: str) -> str:
    if ticker in _LARGE:
        return "Large"
    if ticker in _MID:
        return "Mid"
    return "Small"

async def run_pipeline(ticker: str) -> None:
    """Run the full 9-agent pipeline for one company."""
    await bus.emit(ticker, "agent_start", {"ticker": ticker})
    try:
        # ── Stage 1+2: Download PDFs and RAG-index for all years ──────────────
        # STRICT PDF-only policy: financial data comes ONLY from official annual
        # reports. No Screener/yfinance fundamentals. Missing PDF = clear error.
        years_with_data: list[int] = []
        for year in ALL_YEARS:
            try:
                pdf_path = fetch_pdf(ticker, year)
                await bus.emit(ticker, "on_pdf_fetched", {"year": year, "path": str(pdf_path)})
                info = process_pdf(ticker, year, pdf_path)
                await bus.emit(ticker, "on_rag_indexed", info)
                years_with_data.append(year)
            except Exception as pdf_err:
                await bus.emit(ticker, "warning",
                               {"year": year,
                                "msg": f"Annual report PDF unavailable for FY{year}. "
                                       f"Place it at data/pdfs/{ticker}_{year}.pdf and re-run. "
                                       f"({pdf_err})"})

        if not any(y in years_with_data for y in FORECAST_BASE_YEARS):
            await bus.emit(ticker, "pipeline_error",
                           {"ticker": ticker,
                            "error": f"No forecasting-input PDFs (2021/2022) available for {ticker}. "
                                     f"Download them to data/pdfs/ and re-run."})
            return

        # ── Stage 3: Extract financials from years that have PDFs ──────────────
        # 2021+2022 feed the forecasts; 2022-2025 provide actuals
        extracts: dict[int, dict] = {}
        for year in years_with_data:
            try:
                extracts[year] = extract_financials(ticker, year)
                await bus.emit(ticker, "on_extract_complete",
                               {"year": year, "data": extracts[year]})
            except Exception as e:
                await bus.emit(ticker, "warning", {"year": year, "msg": f"extract: {e}"})

        # ── Stages 4+5: Forecast then Critique+Revise (both base years) ─────────
        all_revised: dict[int, dict] = {}
        for base_year in FORECAST_BASE_YEARS:
            try:
                forecasts = run_forecast(ticker, base_year)
                await bus.emit(ticker, "on_forecast_ready",
                               {"base_year": base_year, "strategies": list(forecasts.keys())})

                revised: dict[str, dict] = {}
                for strategy, fcast in forecasts.items():
                    critique = critique_forecast(ticker, base_year, strategy, fcast)
                    rev = revise_forecast(ticker, base_year, strategy, fcast, critique)
                    revised[strategy] = rev
                all_revised[base_year] = revised
                await bus.emit(ticker, "on_forecast_revised", {"base_year": base_year})
            except Exception as e:
                await bus.emit(ticker, "warning", {"base_year": base_year, "msg": f"forecast: {e}"})

        # ── Stage 6: Market data ──────────────────────────────────────────────
        actuals = fetch_actuals(ticker)
        await bus.emit(ticker, "on_actuals_fetched", {"n_years": len(actuals)})
        prices = fetch_prices(ticker)
        nifty  = fetch_nifty50()
        earnings_dates = fetch_earnings_dates(ticker)
        await bus.emit(ticker, "on_prices_ready", {"n_rows": len(prices)})

        # ── Stage 7: Metrics ──────────────────────────────────────────────────
        cap = _get_cap_size(ticker)

        # Forecast accuracy
        for base_year, revised in all_revised.items():
            compute_forecast_accuracy(ticker, cap, base_year, revised, actuals)

        # Earnings surprise + trading returns (use first available earnings date)
        for date_str in earnings_dates[:2]:
            for strategy_data in all_revised.get(FORECAST_BASE_YEARS[0], {}).values():
                for row in strategy_data.get("revised_forecast", []):
                    fy = row.get("year")
                    if not fy or not actuals.get(fy, {}).get("eps") or not row.get("eps"):
                        continue
                    try:
                        price_series = prices["close"] if hasattr(prices, "__getitem__") else prices.iloc[:, 0]
                        past = price_series[price_series.index.astype(str) < date_str]
                        if len(past) < 5:
                            continue
                        price_m5 = float(past.iloc[-5])
                        compute_earnings_surprise(
                            ticker, fy, row["eps"], actuals[fy]["eps"], price_m5
                        )
                        compute_trading_returns(
                            ticker, date_str, 1, price_series, nifty["close"]
                        )
                    except Exception:
                        pass
                    break

        # Q2 stock price prediction
        price_rows = [
            {"date": str(d.date()), "close": float(c)}
            for d, c in zip(prices.index, prices.iloc[:, 0])
        ]
        stock_pred = run_stock_prediction(ticker, price_rows)
        await bus.emit(ticker, "on_stock_prediction_ready", {"ticker": ticker})

        # Approximate 2025 actuals for accuracy check
        actuals_2025: dict[str, float | None] = {}
        try:
            import yfinance as yf
            p2025 = yf.Ticker(f"{ticker}.NS").history(start="2025-01-01", end="2025-12-31")
            if not p2025.empty:
                def _eom(df, month):
                    sub = df[df.index.month == month]
                    return float(sub["Close"].iloc[-1]) if not sub.empty else None
                actuals_2025 = {
                    "Jan-2025": _eom(p2025, 1),
                    "Mar-2025": _eom(p2025, 3),
                    "Dec-2025": _eom(p2025, 12),
                    "Dec-2024": float(prices.iloc[-1, 0]),
                }
        except Exception:
            pass

        compute_stock_prediction_accuracy(ticker, stock_pred.get("predictions", []), actuals_2025)
        compute_cap_summary()
        await bus.emit(ticker, "on_metrics_ready", {"ticker": ticker})

        # ── Stages 8+9 are run globally after all companies complete ─────────
        # (commentary + report are triggered via /generate-report endpoint)
        await bus.emit(ticker, "pipeline_complete",
                       {"ticker": ticker, "message": "Pipeline complete"})

    except Exception as e:
        await bus.emit(ticker, "pipeline_error", {"ticker": ticker, "error": str(e)})
        # Don't re-raise — let run_all_and_report continue with remaining tickers


async def run_all_and_report(tickers: list[str]) -> Path:
    """Run pipeline for every ticker, then generate commentary + report."""
    for ticker in tickers:
        try:
            await run_pipeline(ticker)
        except Exception as e:
            print(f"[run_all_and_report] {ticker} failed: {e}")
    return await generate_report_only()


async def generate_report_only() -> Path:
    """
    Generate commentary + report from whatever eval data exists.
    Called by the 'Generate report' button — does NOT re-run any pipelines.
    Safe to call at any time; commentary is skipped gracefully if no eval data yet.
    """
    try:
        generate_commentary()
    except ValueError as e:
        # No eval data yet — write a placeholder narrative so report still builds
        from pathlib import Path as P
        commentary_dir = P("data/commentary")
        commentary_dir.mkdir(parents=True, exist_ok=True)
        cache = commentary_dir / "analyst_narrative.md"
        if not cache.exists():
            cache.write_text(
                "Commentary will be generated once company pipelines have completed. "
                "Run 'Analyze all 20' or analyze individual companies first."
            )
        print(f"[generate_report_only] Commentary skipped: {e}")
    return generate_report()
