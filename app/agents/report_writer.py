# app/agents/report_writer.py
import json
from pathlib import Path
import pandas as pd
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUTPUT_DIR = Path("output")
EVALS_DIR = Path("data/evals")
PROMPTS_DIR = Path("data/prompts")
COMMENTARY_DIR = Path("data/commentary")

def _add_heading(doc: Document, text: str, level: int):
    h = doc.add_heading(text, level=level)
    if h.runs:
        h.runs[0].font.color.rgb = RGBColor(0x1A, 0x52, 0x76)

def _df_to_table(doc: Document, df: pd.DataFrame, max_rows: int = 25):
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
            cells[i].text = str(round(val, 2) if isinstance(val, float) else (val if val is not None else ""))
    doc.add_paragraph()

def _add_prompt_sample(doc: Document, ticker: str, agent: str):
    """Add one representative prompt+response sample for the given agent type."""
    for f in PROMPTS_DIR.glob(f"{ticker}_*_{agent}.jsonl"):
        lines = [l for l in f.read_text().splitlines() if l.strip()]
        if lines:
            entry = json.loads(lines[0])
            p = doc.add_paragraph(style="Intense Quote")
            p.add_run(f"Prompt ({ticker}, {entry.get('year')}, {agent}):").bold = True
            doc.add_paragraph(entry["prompt"][:600] + "...", style="No Spacing")
            p2 = doc.add_paragraph(style="Intense Quote")
            p2.add_run("Response:").bold = True
            doc.add_paragraph(entry["response"][:400] + "...", style="No Spacing")
            return

def generate_report() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # Cover
    title = doc.add_heading("B24-T5 Financial Analytics — Group Assignment", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("Group 11 | LLM: Claude Sonnet 4.6 (Anthropic) | June 2026")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # Q1a — Forecast accuracy tables
    _add_heading(doc, "Q1. LLM Reasoning and Prediction", 1)
    _add_heading(doc, "Q1a. Forecast Tables — Revenue & Net Income", 2)
    acc_path = EVALS_DIR / "forecast_accuracy.csv"
    if acc_path.exists():
        df = pd.read_csv(acc_path)
        for strategy in ("baseline", "alt_strategy"):
            _add_heading(doc, f"Strategy: {strategy.replace('_', ' ').title()}", 3)
            sub_df = df[(df["strategy"] == strategy) & (df["metric"] == "revenue")]
            if not sub_df.empty:
                pivot = sub_df.pivot_table(index="ticker", columns="horizon",
                                           values="pct_error", aggfunc="mean").reset_index()
                _df_to_table(doc, pivot)

    # Q1b — Cap-size and horizon accuracy
    _add_heading(doc, "Q1b. Accuracy Analysis — Large vs Mid vs Small Cap", 2)
    cap_path = EVALS_DIR / "cap_summary.csv"
    if cap_path.exists():
        _df_to_table(doc, pd.read_csv(cap_path))

    # Q1c — Alt strategy comparison
    _add_heading(doc, "Q1c. Alternate Strategy (Full-Report CoT vs P&L-only CoT)", 2)
    if acc_path.exists():
        df = pd.read_csv(acc_path)
        rev = df[df["metric"] == "revenue"].copy()
        rev["abs_pct_error"] = rev["pct_error"].abs()
        comp = rev.groupby(["strategy", "horizon"], as_index=False)["abs_pct_error"].mean()
        comp.rename(columns={"abs_pct_error": "avg_abs_pct_error"}, inplace=True)
        _df_to_table(doc, comp)

    # Q1d — Earnings surprise
    _add_heading(doc, "Q1d. Earnings Surprise Signal", 2)
    surp_path = EVALS_DIR / "earnings_surprise.csv"
    if surp_path.exists():
        _df_to_table(doc, pd.read_csv(surp_path))
    ret_path = EVALS_DIR / "trading_returns.csv"
    if ret_path.exists():
        _df_to_table(doc, pd.read_csv(ret_path))

    # Q1e — LLM observations (analyst narrative)
    _add_heading(doc, "Q1e. Overall LLM Observations", 2)
    narrative_path = COMMENTARY_DIR / "analyst_narrative.md"
    if narrative_path.exists():
        doc.add_paragraph(narrative_path.read_text())

    doc.add_page_break()

    # Q2 — Stock price prediction
    _add_heading(doc, "Q2. Stock Price Prediction from 2024 Data", 1)
    stock_path = EVALS_DIR / "stock_prediction.csv"
    if stock_path.exists():
        _df_to_table(doc, pd.read_csv(stock_path))

    doc.add_page_break()

    # Appendix — Prompts
    _add_heading(doc, "Appendix: Prompts Used", 1)
    doc.add_paragraph("One representative prompt+response per agent type:")
    company_urls = json.loads(Path("data/company_urls.json").read_text())
    sample_ticker = next(iter(company_urls.keys()))
    for agent in ("extractor", "forecaster_baseline", "forecaster_alt_strategy",
                  "critique_baseline", "revise_baseline", "stock_predictor",
                  "analyst_commentary"):
        _add_heading(doc, f"Agent: {agent}", 3)
        _add_prompt_sample(doc, sample_ticker, agent)

    out = OUTPUT_DIR / "report.docx"
    doc.save(str(out))
    return out
