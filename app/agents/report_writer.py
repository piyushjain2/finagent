# app/agents/report_writer.py
import json
from pathlib import Path
import pandas as pd
from docx import Document
from docx.shared import RGBColor, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUTPUT_DIR   = Path("output")
EVALS_DIR    = Path("data/evals")
PROMPTS_DIR  = Path("data/prompts")
RESPONSES_DIR = Path("data/responses")
MARKET_DIR   = Path("data/market")
COMMENTARY_DIR = Path("data/commentary")

FORECAST_BASE_YEARS = [2021, 2022]   # base year → predicts next 3 FYs


# ── Helpers ──────────────────────────────────────────────────────────────────

def _add_heading(doc: Document, text: str, level: int):
    h = doc.add_heading(text, level=level)
    if h.runs:
        h.runs[0].font.color.rgb = RGBColor(0x1A, 0x52, 0x76)


def _df_to_table(doc: Document, df: pd.DataFrame, max_rows: int = 60):
    df = df.head(max_rows)
    table = doc.add_table(rows=1, cols=len(df.columns))
    try:
        table.style = "Light Grid Accent 1"
    except KeyError:
        table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, col in enumerate(df.columns):
        hdr[i].text = str(col)
        if hdr[i].paragraphs[0].runs:
            hdr[i].paragraphs[0].runs[0].font.bold = True
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, val in enumerate(row):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                cells[i].text = "N/A"
            elif isinstance(val, float):
                cells[i].text = str(round(val, 2))
            else:
                cells[i].text = str(val)
    doc.add_paragraph()


def _load_revised_forecast(ticker: str, base_year: int, strategy: str) -> dict | None:
    """Load revised forecast; fall back to plain forecast if revised doesn't exist."""
    for suffix in (f"{strategy}_revised_forecast", f"{strategy}_forecast"):
        p = RESPONSES_DIR / f"{ticker}_{base_year}_{suffix}.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def _load_actuals(ticker: str) -> dict[int, dict]:
    p = MARKET_DIR / f"{ticker}_actuals.json"
    if p.exists():
        return {int(k): v for k, v in json.loads(p.read_text()).items()}
    return {}


def _forecast_comparison_table(doc: Document, ticker: str, base_year: int):
    """
    Build side-by-side prediction vs actual table for one base year.
    Rows: Revenue, Net Income  |  Columns per forecast year: Predicted / Actual / Error%
    Shows both Baseline and Alt Strategy.
    """
    actuals = _load_actuals(ticker)
    forecast_years = [base_year + 1, base_year + 2, base_year + 3]

    for strategy_label, strategy_key in [("Baseline (P&L-only CoT)", "baseline"),
                                          ("Alt Strategy (Full-Report CoT)", "alt_strategy")]:
        fcast = _load_revised_forecast(ticker, base_year, strategy_key)
        if not fcast:
            doc.add_paragraph(f"  {strategy_label}: no forecast data available.")
            continue

        rows_data = fcast.get("revised_forecast") or fcast.get("forecast", [])
        fcast_by_year = {r["year"]: r for r in rows_data}

        _add_heading(doc, strategy_label, 4)

        # Build DataFrame
        cols = ["Metric"]
        for fy in forecast_years:
            label = f"FY{fy}"
            cols += [f"{label} Predicted", f"{label} Actual", f"{label} Error%"]

        table_rows = []
        for metric_label, pred_key, actual_key in [
            ("Revenue (₹ Cr)", "revenue_cr", "revenue_cr"),
            ("Net Income (₹ Cr)", "net_income_cr", "net_income_cr"),
        ]:
            row = [metric_label]
            for fy in forecast_years:
                pred = fcast_by_year.get(fy, {}).get(pred_key)
                act  = actuals.get(fy, {}).get(actual_key)
                if pred and act:
                    err = round((act - pred) / act * 100, 1)
                    row += [f"{pred:,.0f}", f"{act:,.0f}", f"{err}%"]
                elif pred:
                    row += [f"{pred:,.0f}", "N/A", "N/A"]
                else:
                    row += ["N/A", "N/A", "N/A"]
            table_rows.append(row)

        _df_to_table(doc, pd.DataFrame(table_rows, columns=cols))


def _add_prompt_sample(doc: Document, ticker: str, agent: str):
    """One representative prompt + response for a given agent type."""
    for f in PROMPTS_DIR.glob(f"{ticker}_*_{agent}.jsonl"):
        lines = [l for l in f.read_text().splitlines() if l.strip()]
        if lines:
            entry = json.loads(lines[0])
            p = doc.add_paragraph(style="Intense Quote")
            p.add_run(f"Prompt ({ticker}, FY{entry.get('year')}, {agent}):").bold = True
            doc.add_paragraph(entry["prompt"][:800] + "\n[…]", style="No Spacing")
            p2 = doc.add_paragraph(style="Intense Quote")
            p2.add_run("Response:").bold = True
            doc.add_paragraph(entry["response"][:600] + "\n[…]", style="No Spacing")
            doc.add_paragraph()
            return


# ── Per-company report ────────────────────────────────────────────────────────

def generate_company_report(ticker: str) -> Path:
    """
    Minimal report for a single company:
    - Predictions from 2021 report (→ FY2022/23/24)
    - Predictions from 2022 report (→ FY2023/24/25)
    - Comparison table for each (predicted vs actual + error%)
    No prompts section — keeps it clean for a quick check.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()

    title = doc.add_heading(f"{ticker} — Financial Forecast Analysis", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("Group 11 | LLM: Claude Sonnet 4.6 (Anthropic) | June 2026")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    for base_year in FORECAST_BASE_YEARS:
        forecast_years = [base_year + 1, base_year + 2, base_year + 3]
        _add_heading(doc,
            f"Q1. Using FY{base_year} Annual Report → Predict FY{forecast_years[0]}, "
            f"FY{forecast_years[1]}, FY{forecast_years[2]}", 1)
        _forecast_comparison_table(doc, ticker, base_year)

    # Q2 stock prediction for this ticker
    stock_path = EVALS_DIR / "stock_prediction.csv"
    if stock_path.exists():
        df = pd.read_csv(stock_path)
        ticker_df = df[df["ticker"] == ticker]
        if not ticker_df.empty:
            _add_heading(doc, "Q2. Stock Price Prediction (2024 data → 2025 forecasts)", 1)
            _df_to_table(doc, ticker_df.drop(columns=["ticker"], errors="ignore"))

    out = OUTPUT_DIR / f"report_{ticker}.docx"
    doc.save(str(out))
    return out


# ── Full 20-company report ────────────────────────────────────────────────────

def generate_report() -> Path:
    """
    Full submission report for all 20 companies.
    Includes forecast + comparison tables per company, accuracy analysis,
    earnings surprise, commentary, Q2 stock prediction, and ONE prompts appendix.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # Cover
    title = doc.add_heading("B24-T5 Financial Analytics — Group Assignment", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("Group 11 | LLM: Claude Sonnet 4.6 (Anthropic) | June 2026")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # ── Q1 ──────────────────────────────────────────────────────────────────
    _add_heading(doc, "Q1. LLM Reasoning and Prediction", 1)

    # Q1a — per-company prediction + comparison tables
    _add_heading(doc, "Q1a. Forecast Tables — Revenue & Net Income", 2)

    company_urls = json.loads(Path("data/company_urls.json").read_text())
    tickers = list(company_urls.keys())

    for base_year in FORECAST_BASE_YEARS:
        forecast_years = [base_year + 1, base_year + 2, base_year + 3]
        _add_heading(doc,
            f"Using FY{base_year} Annual Report → Predict "
            f"FY{forecast_years[0]}, FY{forecast_years[1]}, FY{forecast_years[2]}", 3)
        for ticker in tickers:
            _add_heading(doc, ticker, 4)
            _forecast_comparison_table(doc, ticker, base_year)

    # Q1b — accuracy by cap size + horizon
    _add_heading(doc, "Q1b. Accuracy Analysis — Large vs Mid vs Small Cap", 2)
    cap_path = EVALS_DIR / "cap_summary.csv"
    if cap_path.exists():
        _df_to_table(doc, pd.read_csv(cap_path))

    acc_path = EVALS_DIR / "forecast_accuracy.csv"
    if acc_path.exists():
        df = pd.read_csv(acc_path)
        rev = df[df["metric"] == "revenue"].copy()
        rev["abs_pct_error"] = rev["pct_error"].abs()
        horizon_df = rev.groupby(["cap_size", "horizon"], as_index=False)["abs_pct_error"].mean()
        horizon_df.rename(columns={"abs_pct_error": "avg_abs_error%"}, inplace=True)
        _df_to_table(doc, horizon_df)

    # Q1c — baseline vs alt strategy
    _add_heading(doc, "Q1c. Alternate Strategy — P&L-only CoT vs Full-Report CoT", 2)
    if acc_path.exists():
        df = pd.read_csv(acc_path)
        rev = df[df["metric"] == "revenue"].copy()
        rev["abs_pct_error"] = rev["pct_error"].abs()
        comp = rev.groupby(["strategy", "horizon"], as_index=False)["abs_pct_error"].mean()
        comp.rename(columns={"abs_pct_error": "avg_abs_error%"}, inplace=True)
        _df_to_table(doc, comp)

    # Q1d — earnings surprise
    _add_heading(doc, "Q1d. Earnings Surprise Signal", 2)
    for csv_name in ("earnings_surprise", "trading_returns"):
        p = EVALS_DIR / f"{csv_name}.csv"
        if p.exists():
            _df_to_table(doc, pd.read_csv(p))

    # Q1e — LLM observations
    _add_heading(doc, "Q1e. Overall LLM Observations", 2)
    narrative_path = COMMENTARY_DIR / "analyst_narrative.md"
    if narrative_path.exists():
        doc.add_paragraph(narrative_path.read_text())

    doc.add_page_break()

    # ── Q2 ──────────────────────────────────────────────────────────────────
    _add_heading(doc, "Q2. Stock Price Prediction from 2024 Daily Data", 1)
    stock_path = EVALS_DIR / "stock_prediction.csv"
    if stock_path.exists():
        _df_to_table(doc, pd.read_csv(stock_path))

    doc.add_page_break()

    # ── Appendix — Prompts (once only) ──────────────────────────────────────
    _add_heading(doc, "Appendix: Prompts Used", 1)
    doc.add_paragraph(
        "One representative prompt+response per agent type, shown for the first available company. "
        "The same prompt template was used consistently across all 20 companies."
    )
    sample_ticker = tickers[0]
    for agent in ("extractor", "forecaster_baseline", "forecaster_alt_strategy",
                  "critique_baseline", "revise_baseline", "stock_predictor",
                  "analyst_commentary"):
        _add_heading(doc, f"Agent: {agent}", 3)
        _add_prompt_sample(doc, sample_ticker, agent)

    out = OUTPUT_DIR / "report.docx"
    doc.save(str(out))
    return out
