# app/agents/commentary.py
import json
from pathlib import Path
import pandas as pd
from app.claude_client import call_claude, load_skill

COMMENTARY_DIR = Path("data/commentary")
EVALS_DIR = Path("data/evals")
SKILL_PATH = Path("skills/analyst_commentary_prompt.md")

def generate_commentary() -> str:
    """Read all eval CSVs and generate analyst narrative. Cached."""
    COMMENTARY_DIR.mkdir(parents=True, exist_ok=True)
    cache = COMMENTARY_DIR / "analyst_narrative.md"
    if cache.exists():
        return cache.read_text()

    context_parts = []
    for csv_name in ("forecast_accuracy", "cap_summary", "earnings_surprise",
                     "trading_returns", "stock_prediction"):
        path = EVALS_DIR / f"{csv_name}.csv"
        if path.exists():
            df = pd.read_csv(path)
            if not df.empty:
                context_parts.append(f"=== {csv_name.upper()} ===\n{df.to_string(index=False)}")

    if not context_parts:
        raise ValueError("No evaluation data found. Run the pipeline for at least one company first.")

    skill = load_skill(SKILL_PATH)
    prompt = f"{skill}\n\n{'='*60}\nEVALUATION DATA:\n{'='*60}\n\n" + "\n\n".join(context_parts)

    narrative = call_claude(prompt, ticker="ALL", year=0, agent="analyst_commentary",
                            max_tokens=1200)
    cache.write_text(narrative)
    return narrative
