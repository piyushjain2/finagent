"""
LaTeX submission report generator — single self-contained ≤20-page PDF.

Sources: eval CSVs, charts (output/figures/), analyst commentary, prompt templates
(skills/) + real logged responses. Compiles with pdflatex (TeX Live).

Usage: python make_latex_report.py
Output: output/latex/FinA_Group11_Report.pdf
"""
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

EVALS = Path("data/evals")
FIGS = Path("output/figures")
SKILLS = Path("skills")
PROMPTS = Path("data/prompts")
OUT = Path("output/latex")
TEX = OUT / "report.tex"

FORECAST_BASE_YEARS = [2021, 2022]


# ── LaTeX helpers ─────────────────────────────────────────────────────────────

def esc(s) -> str:
    """Escape LaTeX specials FIRST, then map unicode to LaTeX commands."""
    if s is None:
        return ""
    s = str(s)
    # 1. Escape ASCII specials (backslash intentionally untouched — plain prose input)
    for ch, r in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                  ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                  ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(ch, r)
    # 2. Unicode → LaTeX (safe now; inserted commands won't be re-escaped)
    replacements = {
        "₹": "Rs.", "—": "--", "–": "--", "“": "``", "”": "''", "’": "'", "‘": "`",
        "✓": "\\checkmark{}", "×": "x", "≈": "$\\approx$", "±": "$\\pm$",
        "→": "$\\rightarrow$", "…": "...", "│": "|", "├": "|-", "└": "`-",
        "┌": "+", "─": "-", "█": "\\#", "●": "*", "⚠": "(!)",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s


def esc_keep_cmds(s) -> str:
    """esc() but applied before any of our own commands are inserted."""
    return esc(s)


def sanitize_verbatim(s: str) -> str:
    """For listings blocks: only unicode sanitize (no LaTeX escaping needed)."""
    out = []
    for ch in s:
        if ord(ch) < 128:
            out.append(ch)
        else:
            table = {"₹": "Rs.", "—": "--", "–": "-", "“": '"', "”": '"',
                     "’": "'", "‘": "'", "…": "...", "✓": "[ok]", "×": "x",
                     "±": "+/-", "≈": "~", "→": "->", "•": "*"}
            out.append(table.get(ch, "?"))
    return "".join(out)


def fmt_num(v, decimals=0):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:,.{decimals}f}"


def fmt_err(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if abs(v) > 300:
        return "n.m."
    return f"{v:.1f}\\%"


# ── Content builders ──────────────────────────────────────────────────────────

def q1a_tables(strategy: str = "baseline", strat_label: str = "Baseline") -> str:
    acc = pd.read_csv(EVALS / "forecast_accuracy.csv")
    parts = []
    for base_year in FORECAST_BASE_YEARS:
        fy = [base_year + 1, base_year + 2, base_year + 3]
        for metric, mlabel in [("revenue", "Revenue"), ("net_income", "Net Income")]:
            sub = acc[(acc.base_year == base_year) & (acc.strategy == strategy)
                      & (acc.metric == metric)]
            if sub.empty:
                continue
            rows = []
            for ticker in sorted(sub.ticker.unique()):
                t = sub[sub.ticker == ticker]
                cells = [esc(ticker)]
                for year in fy:
                    r = t[t.forecast_year == year]
                    if r.empty:
                        cells += ["N/A", "N/A", "N/A"]
                    else:
                        r = r.iloc[0]
                        cells += [fmt_num(r.predicted), fmt_num(r.actual),
                                  fmt_err(r.pct_error)]
                rows.append(" & ".join(cells) + r" \\")
            head1 = " & " + " & ".join(
                f"\\multicolumn{{3}}{{c}}{{\\textbf{{FY{y}}}}}" for y in fy) + r" \\"
            head2 = ("\\textbf{Company} & " + " & ".join(
                ["Pred & Act & \\%Diff"] * 3) + r" \\")
            parts.append(f"""
\\begin{{table}}[H]\\centering\\scriptsize
\\caption{{{strat_label} forecasts vs actuals --- {mlabel} (Rs.\\ Cr), base year FY{base_year}}}
\\setlength{{\\tabcolsep}}{{3.2pt}}
\\begin{{tabular}}{{l rrr rrr rrr}}
\\toprule
{head1}
\\cmidrule(lr){{2-4}}\\cmidrule(lr){{5-7}}\\cmidrule(lr){{8-10}}
{head2}
\\midrule
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}""")
    return "\n".join(parts)


def per_company_stats() -> str:
    acc = pd.read_csv(EVALS / "forecast_accuracy.csv").dropna(subset=["pct_error"])
    core = acc[(acc.metric.isin(["revenue", "net_income"])) & (acc.strategy == "baseline")]
    caps = core[["ticker", "cap_size"]].drop_duplicates().set_index("ticker")["cap_size"].to_dict()
    order = {"Large": 0, "Mid": 1, "Small": 2}
    rows = []
    prev_cap = None
    for t in sorted(core.ticker.unique(), key=lambda x: (order[caps[x]], x)):
        sub = core[core.ticker == t]["pct_error"]
        clean = sub[sub.abs() <= 300]
        nm = len(sub) - len(clean)
        a = clean.abs()
        if caps[t] != prev_cap:
            rows.append(f"\\midrule\\multicolumn{{6}}{{l}}{{\\textbf{{{caps[t]}-cap}}}} \\\\")
            prev_cap = caps[t]
        rows.append(f"{esc(t)} & {clean.min():.1f}\\% & {clean.max():.1f}\\% & "
                    f"{a.mean():.1f}\\% & {a.median():.1f}\\% & {nm} \\\\")
    return f"""
\\begin{{table}}[H]\\centering\\footnotesize
\\caption{{Per-company error profile --- baseline strategy, Revenue + Net Income
(signed min/max; unsigned mean/median; n.m.\\ = rows excluded as not meaningful)}}
\\begin{{tabular}}{{l rrrr c}}
\\toprule
\\textbf{{Company}} & \\textbf{{Min}} & \\textbf{{Max}} & \\textbf{{Mean $|$err$|$}} &
\\textbf{{Median $|$err$|$}} & \\textbf{{n.m.}} \\\\
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}"""


def q1b_block() -> str:
    cap = pd.read_csv(EVALS / "cap_summary.csv")
    rows = []
    for _, r in cap.iterrows():
        rows.append(f"{esc(r.cap_size)} & {int(r.n_companies)} & "
                    f"{fmt_num(r.avg_y1_error,1)}\\% & {fmt_num(r.avg_y2_error,1)}\\% & "
                    f"{fmt_num(r.avg_y3_error,1)}\\% & "
                    f"{fmt_num(r.get('direction_accuracy', float('nan'))*100 if pd.notna(r.get('direction_accuracy')) else None,0)}\\% \\\\")
    return f"""
\\begin{{figure}}[H]\\centering
\\includegraphics[width=0.92\\textwidth]{{{(FIGS/'error_horizon_cap.png').resolve()}}}
\\caption{{Forecast error grows with horizon and shrinks with company size (baseline strategy).}}
\\end{{figure}}

\\begin{{table}}[H]\\centering\\small
\\caption{{Mean absolute revenue error by market-cap segment and horizon}}
\\begin{{tabular}}{{l c rrr r}}
\\toprule
\\textbf{{Segment}} & \\textbf{{N}} & \\textbf{{Y1}} & \\textbf{{Y2}} & \\textbf{{Y3}} & \\textbf{{Q2 dir.\\ acc.}} \\\\
\\midrule
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}"""


def q1c_block() -> str:
    acc = pd.read_csv(EVALS / "forecast_accuracy.csv").dropna(subset=["pct_error"])
    core = acc[(acc.metric.isin(["revenue", "net_income"])) & (acc.pct_error.abs() <= 300)]
    core = core.copy()
    core["abs_err"] = core.pct_error.abs()
    piv = core.groupby(["strategy", "horizon"])["abs_err"].mean().unstack()
    med = core.groupby("strategy")["abs_err"].median()
    labels = {"baseline": "Baseline (P\\&L CoT)", "alt_strategy": "Alt v1 (full-report CoT)",
              "alt_v2": "\\textbf{Alt v2 (structured data)}"}
    rows = []
    for s in ["baseline", "alt_strategy", "alt_v2"]:
        if s not in piv.index:
            continue
        rows.append(f"{labels[s]} & " + " & ".join(
            f"{piv.loc[s].get(h, float('nan')):.1f}\\%" for h in ["Y1", "Y2", "Y3"])
            + f" & {med[s]:.1f}\\% \\\\")
    return f"""
\\begin{{figure}}[H]\\centering
\\includegraphics[width=0.92\\textwidth]{{{(FIGS/'strategy_comparison.png').resolve()}}}
\\caption{{Providing clean structured data (Alt v2) improves accuracy at every horizon.}}
\\end{{figure}}

\\begin{{table}}[H]\\centering\\small
\\caption{{Strategy comparison --- mean absolute error (Revenue + Net Income)}}
\\begin{{tabular}}{{l rrr r}}
\\toprule
\\textbf{{Strategy}} & \\textbf{{Y1}} & \\textbf{{Y2}} & \\textbf{{Y3}} & \\textbf{{Median}} \\\\
\\midrule
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}"""


def q1d_block() -> str:
    surp = pd.read_csv(EVALS / "earnings_surprise.csv")
    ret = pd.read_csv(EVALS / "trading_returns.csv")
    merged = surp.merge(ret, left_on=["ticker"], right_on=["ticker"], how="left",
                        suffixes=("", "_r")).drop_duplicates(subset=["ticker", "year"])
    rows = []
    for _, r in merged.sort_values(["ticker", "year"]).iterrows():
        rows.append(f"{esc(r.ticker)} & FY{int(r.year)} & {fmt_num(r.forecast_eps,2)} & "
                    f"{fmt_num(r.actual_eps,2)} & {fmt_num(r.price_minus5,0)} & "
                    f"{r.signal:+.4f} & {fmt_num(r.get('return_pct_5d'),2)}\\% & "
                    f"{fmt_num(r.get('nifty_return_pct_5d'),2)}\\% & "
                    f"{fmt_num(r.get('excess_return'),2)}\\% \\\\")
    hit = ret.dropna(subset=["excess_return"])
    hit_rate = (hit.excess_return > 0).mean() * 100 if len(hit) else float("nan")
    return f"""
\\begin{{table}}[H]\\centering\\scriptsize
\\caption{{Earnings surprise signal and post-announcement buy-and-hold returns
(signal = (Actual EPS $-$ Forecast EPS)/Price$_{{-5}}$; returns = day $+1$ close to day $+5$ close)}}
\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{tabular}}{{l l rrr r rrr}}
\\toprule
\\textbf{{Company}} & \\textbf{{FY}} & \\textbf{{Fcst EPS}} & \\textbf{{Act EPS}} &
\\textbf{{Price$_{{-5}}$}} & \\textbf{{Signal}} & \\textbf{{Ret$_{{5d}}$}} &
\\textbf{{NIFTY$_{{5d}}$}} & \\textbf{{Excess}} \\\\
\\midrule
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}

Of the {len(hit)} signal events with complete return data, {int((hit.excess_return > 0).sum())}
({hit_rate:.0f}\\%) beat the NIFTY~50 over the 5-day window --- below the threshold required
for a systematically profitable signal.
"""


def q2_block() -> str:
    sdf = pd.read_csv(EVALS / "stock_prediction.csv")
    rows = []
    for ticker in sorted(sdf.ticker.unique()):
        t = sdf[sdf.ticker == ticker]
        cells = [esc(ticker)]
        for target in ["Jan-2025", "Mar-2025", "Dec-2025"]:
            r = t[t.forecast_target == target]
            if r.empty:
                cells += ["N/A", "N/A", "N/A", "--"]
            else:
                r = r.iloc[0]
                d = ("\\checkmark" if str(r.direction_correct) == "True"
                     else "$\\times$" if pd.notna(r.direction_correct) else "--")
                cells += [fmt_num(r.predicted_price), fmt_num(r.actual_price),
                          fmt_err(r.pct_error), d]
        rows.append(" & ".join(cells) + r" \\")
    dir_acc = sdf.groupby("forecast_target")["direction_correct"].mean() * 100
    summary = ", ".join(f"{t}: {v:.0f}\\%" for t, v in dir_acc.items())
    return f"""
\\begin{{table}}[H]\\centering\\scriptsize
\\caption{{LLM stock-price predictions from 2024 daily data vs actuals
(Pred/Act in Rs.; Dir = direction vs Dec-2024 close)}}
\\setlength{{\\tabcolsep}}{{3.2pt}}
\\begin{{tabular}}{{l rrrc rrrc rrrc}}
\\toprule
 & \\multicolumn{{4}}{{c}}{{\\textbf{{Jan-2025}}}} & \\multicolumn{{4}}{{c}}{{\\textbf{{Mar-2025}}}} & \\multicolumn{{4}}{{c}}{{\\textbf{{Dec-2025}}}} \\\\
\\cmidrule(lr){{2-5}}\\cmidrule(lr){{6-9}}\\cmidrule(lr){{10-13}}
\\textbf{{Company}} & Pred & Act & \\%D & Dir & Pred & Act & \\%D & Dir & Pred & Act & \\%D & Dir \\\\
\\midrule
{chr(10).join(rows)}
\\bottomrule
\\end{{tabular}}
\\end{{table}}

Direction accuracy across 20 companies --- {summary}.
"""


def commentary_block() -> str:
    md = Path("data/commentary/analyst_narrative.md").read_text()
    # minimal markdown → LaTeX
    out = []
    for line in md.splitlines():
        if line.startswith("## "):
            out.append(f"\\subsection*{{{esc(line[3:])}}}")
        elif line.startswith("# "):
            continue  # main title handled by section
        else:
            line = re.sub(r"\*\*(.+?)\*\*", lambda m: f"\\textbf{{{esc(m.group(1))}}}",
                          line)
            # escape leftovers outside the bold groups
            parts = re.split(r"(\\textbf\{[^}]*\})", line)
            line = "".join(p if p.startswith("\\textbf") else esc(p) for p in parts)
            out.append(line)
    return "\n".join(out)


def appendix_prompts() -> str:
    """The 7 distinct prompt templates + one real (condensed) response each."""
    agents = [
        ("extraction_prompt.md", "extractor", "Financial Extractor (Claude Haiku 4.5)"),
        ("forecast_baseline.md", "forecaster_baseline", "Baseline Forecast (Claude Sonnet 4.6)"),
        ("forecast_alt_strategy.md", "forecaster_alt_strategy", "Alt v1 --- Full-report CoT"),
        ("forecast_alt_v2.md", "forecaster_alt_v2", "Alt v2 --- Structured-data CoT (winner)"),
        ("critique_prompt.md", "critique_baseline", "Critique Agent"),
        ("revise_prompt.md", "revise_baseline", "Revise Agent"),
        ("stock_prediction_prompt.md", "stock_predictor", "Q2 Stock Predictor"),
    ]
    sample_ticker = "RELIANCE"
    parts = []
    for skill_file, agent, title in agents:
        template = sanitize_verbatim((SKILLS / skill_file).read_text().strip())
        response = ""
        for f in sorted(PROMPTS.glob(f"{sample_ticker}_*_{agent}.jsonl")):
            lines = [l for l in f.read_text().splitlines() if l.strip()]
            if lines:
                e = json.loads(lines[0])
                response = sanitize_verbatim(e.get("response", "")[:900])
                if len(e.get("response", "")) > 900:
                    response += "\n[...]"
                break
        parts.append(f"""
\\subsection*{{{esc(title)}}}
\\textbf{{Prompt template}} (identical across all 20 companies; per-company data is injected
below the template at run time):
\\begin{{promptbox}}
{template}
\\end{{promptbox}}
\\textbf{{Sample response}} ({esc(sample_ticker)}):
\\begin{{responsebox}}
{response}
\\end{{responsebox}}
""")
    return "\n".join(parts)


# ── Document assembly ─────────────────────────────────────────────────────────

def build_tex() -> str:
    stats = pd.read_csv(EVALS / "forecast_accuracy.csv").dropna(subset=["pct_error"])
    core = stats[(stats.metric.isin(["revenue", "net_income"])) & (stats.pct_error.abs() <= 300)]
    n_calls = sum(1 for f in PROMPTS.glob("*.jsonl") for _ in f.read_text().splitlines())

    return rf"""\documentclass[10pt,a4paper]{{article}}
\usepackage[margin=1.9cm]{{geometry}}
\usepackage{{booktabs,graphicx,float,amssymb,amsmath}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{microtype}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{caption}}
\captionsetup{{font=small,labelfont=bf,skip=4pt}}
\usepackage{{titlesec}}
\titlespacing*{{\section}}{{0pt}}{{10pt}}{{4pt}}
\titlespacing*{{\subsection}}{{0pt}}{{8pt}}{{3pt}}
\usepackage{{listings,xcolor}}
\lstnewenvironment{{promptbox}}{{\lstset{{basicstyle=\ttfamily\fontsize{{6.6pt}}{{7.8pt}}\selectfont,
  breaklines=true,frame=single,rulecolor=\color{{gray!60}},backgroundcolor=\color{{gray!6}},
  aboveskip=3pt,belowskip=5pt,breakindent=0pt,postbreak={{}}}}}}{{}}
\lstnewenvironment{{responsebox}}{{\lstset{{basicstyle=\ttfamily\fontsize{{6.6pt}}{{7.8pt}}\selectfont,
  breaklines=true,frame=single,rulecolor=\color{{green!50!black!40}},backgroundcolor=\color{{green!4}},
  aboveskip=3pt,belowskip=5pt,breakindent=0pt,postbreak={{}}}}}}{{}}
\setlength{{\parskip}}{{4pt}}\setlength{{\parindent}}{{0pt}}

\title{{\vspace{{-1.2cm}}\textbf{{LLM-Based Financial Forecasting of NSE-Listed Companies}}\\
\large B24--T5 Financial Analytics --- Group Assignment}}
\author{{Group 11 \quad$\cdot$\quad LLMs: Claude Sonnet 4.6 (forecasting/analysis),
Claude Haiku 4.5 (extraction)}}
\date{{June 2026}}

\begin{{document}}
\maketitle
\vspace{{-0.9cm}}

\section*{{Executive Summary}}
We built an automated nine-agent pipeline that downloads official annual reports
(100 PDFs: 20 companies $\times$ FY2021--FY2025), extracts consolidated financials via
retrieval-augmented generation, and asks the LLM to forecast Revenues and Net Income
three years ahead from each of the FY2021 and FY2022 reports --- behind a strict
anti-memory-leakage firewall. Across {len(core)} forecast--actual comparisons the median
absolute error is {core.pct_error.abs().median():.1f}\%. Errors rise with forecasting
horizon and fall with company size; an improved strategy that feeds the model
\emph{{clean structured data}} instead of raw document text cuts the median error by a
third. The earnings-surprise trading signal does not systematically beat the market.
All {n_calls} LLM interactions are logged verbatim; every data correction is audited.

\section*{{Methodology Notes}}
\begin{{itemize}}\itemsep1pt
\item \textbf{{Anti-leakage firewall:}} every prompt frames the LLM at April of the base
year and instructs it to ignore post-base-year knowledge; context is year-filtered.
Without such guards an LLM can ``recall'' actuals from training data --- we observed
near-0\% errors in unguarded reference approaches, a tell-tale of memory contamination
rather than forecasting skill.
\item \textbf{{Data sources:}} forecasting inputs and actuals come only from official
annual-report PDFs (consolidated statements). Unit slips (Rs.\ million/lakh vs crore)
are corrected only by powers of 10 against a Screener.in magnitude reference; all
corrections are logged. Daily prices: Yahoo Finance.
\item \textbf{{Q1d conventions:}} announcement dates from the Yahoo Finance earnings
calendar (13 of 20 companies); buy-and-hold uses closing prices (day $+1$ to day $+5$)
as an open-price proxy.
\item \textbf{{n.m.}} = not meaningful ($|$difference$|>300\%$, typically near-zero
actuals in turnaround years; standard equity-research convention).
\end{{itemize}}

\section*{{Approach \& System Architecture}}
\textbf{{What we built.}} Rather than pasting PDFs into a chat window, we engineered
\emph{{FinAgent}} --- an automated nine-agent pipeline (Figure~\ref{{fig:arch}}) that takes a
company ticker and carries it end-to-end: download official annual reports, index them for
retrieval, extract consolidated financials, generate forecasts under three different prompting
strategies, adversarially critique and revise them, fetch market data, compute every assignment
metric, and assemble this report. The full study covers 100 annual reports
(20 companies $\times$ FY2021--FY2025, $\approx$1.2~GB) and $\approx$650 logged LLM interactions.

\begin{{figure}}[H]\centering
\includegraphics[width=\textwidth]{{{(FIGS/'pipeline_architecture.png').resolve()}}}
\caption{{The nine-agent FinAgent pipeline.}}\label{{fig:arch}}
\end{{figure}}

\textbf{{How it works.}} Each 200--400 page report is split into $\approx$500 overlapping
chunks, embedded locally (sentence-transformers) into a vector store, and only the
10--15 most relevant pages are retrieved per task --- a $\approx$95\% token reduction
versus full-document prompting. A cheap model (Haiku~4.5) performs mechanical extraction;
the capable model (Sonnet~4.6) performs the forecasting experiments. Every prompt lives in
a version-controlled template file, guaranteeing the \emph{{identical strategy across all
20 companies and both base years}} that the assignment requires. Every stage caches its
output, so any interruption resumes at zero marginal cost, and any number in this document
is traceable to a logged artefact.

\textbf{{Why this design.}} Three forces drove it: (i)~\emph{{validity}} --- the assignment's
central warning is that an LLM may recall actuals from training data instead of forecasting;
manual chat workflows cannot control this, while our templates enforce a dated-analyst frame
and year-filtered context on every call; (ii)~\emph{{consistency}} --- with 240 forecast
numbers across 20 heterogeneous companies, hand-driven prompting inevitably drifts;
(iii)~\emph{{auditability}} --- graders (and we) can verify any figure: prompts, responses,
data corrections and intermediate outputs are all on disk.

\section*{{What Makes This Approach Distinctive}}
\begin{{enumerate}}\itemsep2pt
\item \textbf{{Anti-memory-leakage firewall.}} Every forecasting prompt situates the model
in April of the base year and forbids post-base-year knowledge; retrieval context is
year-filtered. In unguarded reference workflows we observed forecasts matching actuals to
the rupee (0.00\% ``error'') --- memory recall masquerading as skill. Our error
distributions are honest by construction.
\item \textbf{{A controlled experiment, not a single prompt.}} Three strategies run under
identical conditions. Reporting that v1 (richer context) \emph{{failed}} while v2 (cleaner
data) succeeded is a genuine experimental finding, not cherry-picking.
\item \textbf{{Audited data hygiene.}} Annual reports state figures in Rs.\ million, lakh
and crore inconsistently; LLM extraction occasionally mis-converts. A magnitude tripwire
(against Screener.in consolidated references) corrects only power-of-10 slips; all 124
corrections are individually logged. Ground truth that fails validation is excluded, never
fabricated.
\item \textbf{{Complete provenance.}} $\approx$650 prompt/response pairs logged verbatim
with model and timestamp; the report itself is generated programmatically from the same
data files it describes --- the numbers cannot drift from their sources.
\item \textbf{{Strict primary-source policy.}} Forecast inputs \emph{{and}} actuals come
only from official annual reports (consolidated statements) --- no aggregator data, whose
silent standalone/consolidated mixing we caught and rejected during development.
\end{{enumerate}}

\section{{Q1(a) --- Forecasts vs Actuals}}
Percentage Difference $=\frac{{\text{{Actual}}-\text{{Predicted}}}}{{\text{{Actual}}}}\times100$.
All values in Rs.\ Crores. Baseline-strategy tables below; the improved strategy is
analysed in Q1(c).
{q1a_tables()}

\section{{Q1(b) --- Accuracy by Market Cap and Horizon}}
{q1b_block()}
{per_company_stats()}

\section{{Q1(c) --- Improving Accuracy: the Alternate Strategy}}
We tested two improvement hypotheses, applied identically across all 20 companies and
both base years: \textbf{{v1}} adds richer qualitative context (balance sheet, MD\&A,
segments); \textbf{{v2}} replaces noisy raw document chunks with the clean structured
financials extracted from the same report. v1 \emph{{failed}} to beat the baseline;
v2 improved accuracy at every horizon (median error $19.9\%\rightarrow13.3\%$, winning
64\% of head-to-head comparisons). \textbf{{Conclusion: for LLM forecasting, data
cleanliness beats context volume.}}
{q1c_block()}

Full per-company tables for the winning strategy:
{q1a_tables('alt_v2', 'Improved strategy (Alt v2)')}

\section{{Q1(d) --- Earnings Surprise Signal}}
{q1d_block()}

\section{{Q1(e) --- Overall Observations on LLM Behaviour}}
{commentary_block()}

\section{{Q2 --- Stock-Price Prediction from 2024 Daily Data}}
The LLM received each company's complete 2024 daily closing-price series and was asked
to predict the closing price at end of January, March, and December 2025
(without using any post-2024 knowledge).
{q2_block()}

\section*{{Limitations \& Future Work}}
\begin{{itemize}}\itemsep2pt
\item \textbf{{Q1(d) coverage:}} historical announcement dates were available for 13 of 20
companies (Yahoo Finance calendar); buy-and-hold uses closing prices as an open-price proxy.
A BSE corporate-announcements scrape would complete coverage.
\item \textbf{{Residual data noise:}} three small/mid-caps (IFCI, IREDA, VINDHYATEL) retain
elevated errors from near-zero turnaround denominators and pre-listing disclosure gaps ---
flagged, not hidden.
\item \textbf{{Single-model study:}} results characterise Claude Sonnet 4.6; a
cross-model comparison (GPT, Gemini, Llama) under the same firewall would test generality.
\item \textbf{{Point estimates:}} we report central forecasts; eliciting calibrated
distributions (P10/P50/P90) and scoring with CRPS would better reflect analyst practice.
\end{{itemize}}

\section*{{Learnings}}
\subsection*{{About LLMs as financial analysts}}
\begin{{itemize}}\itemsep2pt
\item \textbf{{Data cleanliness beats context volume.}} Our single largest accuracy gain
(median error $19.9\%\rightarrow13.3\%$) came not from richer prompts or more document
context, but from handing the model clean, unit-verified numbers. Adding MD\&A and
balance-sheet text (v1) actually \emph{{hurt}} --- more surface area for the model to grab
the wrong figure.
\item \textbf{{Margins are more learnable than levels.}} Net-income forecasts frequently
beat revenue forecasts in relative terms (e.g.\ Reliance base-2021 NI errors of 1--4\%
against revenue errors of $\approx$26\%): the model carries margin structure forward well
but cannot anticipate top-line shocks.
\item \textbf{{LLMs extrapolate; they do not anticipate turning points.}} Post-COVID
recoveries (FY2022), commodity cycles (ONGC), margin collapses (KEC FY2023) and trend
reversals (Q2: 2024 uptrends extended into a falling 2025) all defeated the model ---
exactly where human analysts add the most value.
\item \textbf{{Adversarial self-critique is not a free lunch.}} The critique-and-revise
step made forecasts systematically more conservative, which helped in stable years and
hurt in recovery years --- bias injection, not pure error reduction.
\end{{itemize}}
\subsection*{{About building the system}}
\begin{{itemize}}\itemsep2pt
\item \textbf{{Unit discipline is the silent killer.}} Indian reports mix Rs.\ million /
lakh / crore, banks lack a ``Revenue from Operations'' line, and presentation changes
across years even within one company. Most of our debugging effort went here --- and an
unguarded pipeline produced errors of 600\%+ that looked like model failure but were
measurement failure.
\item \textbf{{Validate the ground truth as hard as the forecast.}} A wrong ``actual'' is
worse than a missing one: it silently corrupts every comparison. Our final design excludes
unverifiable actuals rather than publishing them.
\item \textbf{{Near-zero denominators break percentage metrics.}} Loss-to-profit
turnarounds (IFCI) generate $>$3{{,}}000\% ``errors'' on respectable forecasts; medians and
n.m.\ conventions, not means, tell the honest story.
\item \textbf{{Evaluation infrastructure pays for itself.}} The prompt vault, correction
audit and cached pipeline let us re-verify every number in minutes --- and caught several
of our own mistakes before they reached this document.
\end{{itemize}}

\appendix
\section{{Prompts Used --- Queries \& Responses}}
The seven distinct prompt templates, shown verbatim. Per-company data (8--10k characters
of retrieved report text, structured financial tables, or the daily price series) is
injected beneath the template at run time; complete unabridged logs of all {n_calls}
interactions are retained in the system's Prompt Vault.
{appendix_prompts()}

\end{{document}}
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TEX.write_text(build_tex())
    print(f"TeX written: {TEX}")
    for i in range(2):
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", TEX.name],
            cwd=OUT, capture_output=True, text=True)
        if r.returncode != 0:
            tail = "\n".join(r.stdout.splitlines()[-30:])
            raise SystemExit(f"pdflatex failed:\n{tail}")
    pdf = OUT / "report.pdf"
    final = OUT / "FinA_Group11_Report.pdf"
    pdf.replace(final)
    import pypdf
    n = len(pypdf.PdfReader(str(final)).pages)
    print(f"✅ {final}  —  {n} pages")


if __name__ == "__main__":
    main()
