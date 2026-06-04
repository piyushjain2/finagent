# app/agents/forecaster.py
import json, asyncio, re
from pathlib import Path
from app.claude_client import call_claude, load_skill
from app.agents.rag_processor import query_chunks


def _extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from a Claude response.
    Handles: pure JSON, ```json fenced, prose-then-JSON, JSON-in-prose.
    """
    text = raw.strip()

    # 1. Strip markdown fences and try direct parse
    clean = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # 2. Find ```json ... ``` or ``` ... ``` blocks
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text):
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue

    # 3. Find the last {...} block in the text (handles "Here is my answer: {...}")
    for m in reversed(list(re.finditer(r"\{[\s\S]*\}", text))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON found in response (first 200 chars): {text[:200]}")

RESPONSES_DIR = Path("data/responses")
BASELINE_SKILL = Path("skills/forecast_baseline.md")
ALT_SKILL = Path("skills/forecast_alt_strategy.md")
STOCK_SKILL = Path("skills/stock_prediction_prompt.md")

def _forecast_one(ticker: str, year: int, strategy: str) -> dict:
    cache = RESPONSES_DIR / f"{ticker}_{year}_{strategy}_forecast.json"
    if cache.exists():
        return json.loads(cache.read_text())

    if strategy == "baseline":
        query = "revenue net income profit P&L growth rate"
        skill = load_skill(BASELINE_SKILL)
        forecast_years = f"{year+1}, {year+2}, {year+3}"
    else:
        query = "revenue net income balance sheet MD&A segment performance capex RoE"
        skill = load_skill(ALT_SKILL)
        forecast_years = f"{year+1}, {year+2}, {year+3}"

    chunks = query_chunks(ticker, year, query, n=12)
    context = "\n\n---\n\n".join(chunks)
    prompt = (skill
              .replace("{FORECAST_YEARS}", forecast_years)
              .replace("{BASE_YEAR}", str(year)))
    prompt += f"\n\n=== ANNUAL REPORT TEXT (FY{year} data only) ===\n{context}"

    raw = call_claude(prompt, ticker=ticker, year=year,
                      agent=f"forecaster_{strategy}", max_tokens=2048)
    result = _extract_json(raw)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result

def run_forecast(ticker: str, year: int) -> dict:
    """Run baseline and alt_strategy forecasts. Returns both."""
    baseline = _forecast_one(ticker, year, "baseline")
    alt = _forecast_one(ticker, year, "alt_strategy")
    return {"baseline": baseline, "alt_strategy": alt}

def run_stock_prediction(ticker: str, price_data: list[dict]) -> dict:
    """Q2: predict Jan/Mar/Dec 2025 from 2024 daily prices."""
    cache = RESPONSES_DIR / f"{ticker}_stock_prediction.json"
    if cache.exists():
        return json.loads(cache.read_text())

    if not price_data:
        return {"ticker": ticker, "predictions": [], "reasoning": "No 2024 price data available."}

    rows = "\n".join(f"{r['date']}: {r['close']:.2f}" for r in price_data)
    skill = load_skill(STOCK_SKILL)
    prompt = f"{skill}\n\n=== 2024 DAILY CLOSING PRICES FOR {ticker} ===\n{rows}"

    raw = call_claude(prompt, ticker=ticker, year=2024,
                      agent="stock_predictor", max_tokens=1024)
    if not raw.strip():
        return {"ticker": ticker, "predictions": [], "reasoning": "LLM returned empty response."}
    result = _extract_json(raw)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result
