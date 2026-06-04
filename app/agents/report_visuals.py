# app/agents/report_visuals.py
"""
Charts + prompt 'screenshot' panels for the submission report.
All figures are generated from the eval CSVs / Prompt Vault — fully reproducible.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

EVALS_DIR = Path("data/evals")
PROMPTS_DIR = Path("data/prompts")
FIG_DIR = Path("output/figures")

CAP_ORDER = ["Large", "Mid", "Small"]
CAP_COLORS = {"Large": "#1a5276", "Mid": "#1e8449", "Small": "#922b21"}
STRAT_LABELS = {"baseline": "Baseline (P&L CoT)",
                "alt_strategy": "Alt v1 (Full-report CoT)",
                "alt_v2": "Alt v2 (Structured data)"}
STRAT_COLORS = {"baseline": "#5d6d7e", "alt_strategy": "#b9770e", "alt_v2": "#1a5276"}


def _clean_core() -> pd.DataFrame:
    df = pd.read_csv(EVALS_DIR / "forecast_accuracy.csv").dropna(subset=["pct_error"])
    df = df[df.metric.isin(["revenue", "net_income"])]
    return df[df["pct_error"].abs() <= 300]


def chart_error_by_horizon_cap() -> Path:
    """Grouped bars: mean |error| by horizon, grouped by cap size (baseline strategy)."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = _clean_core()
    df = df[df.strategy == "baseline"]
    pivot = (df.groupby(["cap_size", "horizon"])["pct_error"]
               .apply(lambda x: x.abs().mean()).unstack())

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = range(len(pivot.columns))
    width = 0.26
    for i, cap in enumerate(CAP_ORDER):
        if cap not in pivot.index:
            continue
        vals = [pivot.loc[cap].get(h, 0) for h in pivot.columns]
        bars = ax.bar([xi + (i - 1) * width for xi in x], vals, width,
                      label=f"{cap}-cap", color=CAP_COLORS[cap])
        ax.bar_label(bars, fmt="%.0f%%", fontsize=8, padding=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{h} ({'1' if h=='Y1' else '2' if h=='Y2' else '3'} yr ahead)"
                        for h in pivot.columns])
    ax.set_ylabel("Mean |% error| (Revenue + Net Income)")
    ax.set_title("LLM forecast error grows with horizon and shrinks with company size",
                 fontsize=11, fontweight="bold")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = FIG_DIR / "error_horizon_cap.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def chart_strategy_comparison() -> Path:
    """Bars: mean |error| by horizon for the three strategies (Q1c)."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = _clean_core()
    pivot = (df.groupby(["strategy", "horizon"])["pct_error"]
               .apply(lambda x: x.abs().mean()).unstack())

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = range(len(pivot.columns))
    width = 0.26
    for i, strat in enumerate(["baseline", "alt_strategy", "alt_v2"]):
        if strat not in pivot.index:
            continue
        vals = [pivot.loc[strat].get(h, 0) for h in pivot.columns]
        bars = ax.bar([xi + (i - 1) * width for xi in x], vals, width,
                      label=STRAT_LABELS[strat], color=STRAT_COLORS[strat])
        ax.bar_label(bars, fmt="%.0f%%", fontsize=8, padding=2)
    ax.set_xticks(list(x))
    ax.set_xticklabels(list(pivot.columns))
    ax.set_ylabel("Mean |% error| (Revenue + Net Income)")
    ax.set_title("Q1c: Providing clean structured data (Alt v2) improves accuracy at every horizon",
                 fontsize=11, fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = FIG_DIR / "strategy_comparison.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def render_prompt_panel(ticker: str, agent: str, title: str,
                        prompt_chars: int = 700, response_chars: int = 500) -> Path | None:
    """
    Render a real Prompt Vault entry as a terminal-style image — the
    'screenshot of query and response' the assignment asks for, generated
    verbatim from the logged interaction.
    """
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    entry = None
    for f in sorted(PROMPTS_DIR.glob(f"{ticker}_*_{agent}.jsonl")):
        lines = [l for l in f.read_text().splitlines() if l.strip()]
        if lines:
            entry = json.loads(lines[0])
            break
    if not entry:
        return None

    def _wrap(text: str, limit: int, width: int = 95) -> str:
        import textwrap
        text = text[:limit] + (" […]" if len(text) > limit else "")
        return "\n".join(textwrap.fill(line, width=width)
                         for line in text.splitlines() if line.strip())

    prompt_txt = _wrap(entry["prompt"], prompt_chars)
    resp_txt = _wrap(entry["response"], response_chars)
    body = (f"┌─ QUERY  ({entry['model']} · {entry.get('timestamp','')[:10]}) "
            f"{'─'*30}\n{prompt_txt}\n\n"
            f"┌─ RESPONSE {'─'*52}\n{resp_txt}")

    n_lines = body.count("\n") + 1
    fig_h = max(2.0, n_lines * 0.135 + 0.5)
    fig, ax = plt.subplots(figsize=(8.4, fig_h))
    ax.axis("off")
    fig.patch.set_facecolor("#0d1117")
    ax.text(0.01, 0.99, f"● {title}", transform=ax.transAxes, fontsize=9.5,
            fontweight="bold", color="#58a6ff", va="top", family="monospace")
    ax.text(0.01, 0.93, body, transform=ax.transAxes, fontsize=6.8,
            color="#c9d1d9", va="top", family="monospace", linespacing=1.35)
    out = FIG_DIR / f"panel_{agent}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def chart_pipeline_architecture() -> Path:
    """Nine-agent pipeline flow diagram."""
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    stages = [
        ("PDF\nFetcher", "BSE / company\nIR sites\n(100 PDFs)", "#1a5276"),
        ("RAG\nIndexer", "chunk + embed\nChromaDB\n(local, free)", "#6c3483"),
        ("Extractor", "Haiku 4.5\nP&L → JSON\n(unit-checked)", "#1e8449"),
        ("Forecasters\n×3", "Sonnet 4.6\nbaseline / v1 / v2\n(firewalled)", "#b9770e"),
        ("Critique +\nRevise", "adversarial\nreview, conf.\nranges", "#884ea0"),
        ("Market\nData", "yfinance\nprices, announce\ndates", "#2874a6"),
        ("Metrics", "% diff, surprise\nsignal, returns\nvs NIFTY", "#a93226"),
        ("Scale\nGuard", "Screener tripwire\npower-of-10 snap\n124 audited", "#117864"),
        ("Report", "LaTeX +\ncommentary\n(this document)", "#283747"),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 2.9))
    ax.set_xlim(0, len(stages) * 1.18)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for i, (title, sub, color) in enumerate(stages):
        x = i * 1.18 + 0.05
        box = FancyBboxPatch((x, 0.30), 1.02, 0.52,
                             boxstyle="round,pad=0.02",
                             facecolor=color, edgecolor="none", alpha=0.92)
        ax.add_patch(box)
        ax.text(x + 0.51, 0.70, title, ha="center", va="center",
                fontsize=8.3, fontweight="bold", color="white")
        ax.text(x + 0.51, 0.44, sub, ha="center", va="center",
                fontsize=5.9, color="white", alpha=0.95)
        ax.text(x + 0.51, 0.88, f"{i+1}", ha="center", va="center", fontsize=7,
                fontweight="bold", color=color,
                bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec=color, lw=1.2))
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + 1.18, 0.56), xytext=(x + 1.06, 0.56),
                        arrowprops=dict(arrowstyle="-|>", color="#5d6d7e", lw=1.4))
    ax.text(len(stages) * 1.18 / 2, 0.10,
            "Every stage checkpointed to disk — a failed run resumes free; "
            "every LLM call logged verbatim to the Prompt Vault",
            ha="center", fontsize=7.4, style="italic", color="#5d6d7e")
    fig.tight_layout()
    out = FIG_DIR / "pipeline_architecture.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out
