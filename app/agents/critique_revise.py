# app/agents/critique_revise.py
import json
from pathlib import Path
from app.claude_client import call_claude, load_skill

RESPONSES_DIR = Path("data/responses")
CRITIQUE_SKILL = Path("skills/critique_prompt.md")
REVISE_SKILL = Path("skills/revise_prompt.md")

def critique_forecast(ticker: str, year: int, strategy: str, forecast: dict) -> dict:
    cache = RESPONSES_DIR / f"{ticker}_{year}_{strategy}_critique.json"
    if cache.exists():
        return json.loads(cache.read_text())

    skill = load_skill(CRITIQUE_SKILL)
    prompt = (skill
        .replace("{COMPANY}", ticker)
        .replace("{BASE_YEAR}", str(year))
        .replace("{FORECAST_JSON}", json.dumps(forecast, indent=2)))

    raw = call_claude(prompt, ticker=ticker, year=year,
                      agent=f"critique_{strategy}", max_tokens=1024)
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(clean)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result

def revise_forecast(ticker: str, year: int, strategy: str,
                    forecast: dict, critique: dict) -> dict:
    cache = RESPONSES_DIR / f"{ticker}_{year}_{strategy}_revised_forecast.json"
    if cache.exists():
        return json.loads(cache.read_text())

    skill = load_skill(REVISE_SKILL)
    prompt = (skill
        .replace("{FORECAST_JSON}", json.dumps(forecast, indent=2))
        .replace("{CRITIQUE_JSON}", json.dumps(critique, indent=2)))

    raw = call_claude(prompt, ticker=ticker, year=year,
                      agent=f"revise_{strategy}", max_tokens=1024)
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(clean)
    cache.write_text(json.dumps(result, indent=2))
    return result
