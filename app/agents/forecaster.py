# app/agents/forecaster.py
import json, asyncio, re
from pathlib import Path
from app.claude_client import call_claude, load_skill
from app.agents.rag_processor import query_chunks


def _extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from a Claude response.
    Handles: pure JSON, ```json fenced, prose-then-JSON, JSON-in-prose,
    and trailing garbage after the object ("Extra data") via raw_decode.
    """
    text = raw.strip()
    decoder = json.JSONDecoder()

    # 1. Strip markdown fences and try direct parse
    clean = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # 2. raw_decode parses the FIRST valid object, ignoring trailing content
    #    (handles concatenated objects and prose after the JSON)
    if clean.startswith("{"):
        try:
            obj, _ = decoder.raw_decode(clean)
            return obj
        except json.JSONDecodeError:
            pass

    # 3. Find ```json ... ``` or ``` ... ``` blocks
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text):
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue

    # 4. raw_decode from each '{' position — finds first parseable object anywhere
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON found in response (first 200 chars): {text[:200]}")


def _load_cache_json(path: Path) -> dict | None:
    """Read a cached JSON file; delete and return None if corrupt
    (e.g. from an interrupted write or two processes racing)."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        try:
            path.unlink()
        except OSError:
            pass
        return None

RESPONSES_DIR = Path("data/responses")
BASELINE_SKILL = Path("skills/forecast_baseline.md")
ALT_SKILL = Path("skills/forecast_alt_strategy.md")
STOCK_SKILL = Path("skills/stock_prediction_prompt.md")

def _base_year_revenue(ticker: str, year: int) -> float | None:
    """Read the extracted base-year revenue (used for unit sanity checks)."""
    extract = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
    if not extract.exists():
        return None
    data = _load_cache_json(extract)
    if not data:
        return None
    for row in data.get("years", []):
        if row.get("year") == year and row.get("revenue_cr"):
            return float(row["revenue_cr"])
    return None


def _units_sane(result: dict, base_rev: float | None) -> bool:
    """Detect unit errors: a forecast wildly smaller than base-year revenue
    means the LLM answered in thousand-crores/lakh-crores instead of crores."""
    if not base_rev:
        return True  # nothing to compare against
    for r in result.get("forecast", []):
        rev = r.get("revenue_cr")
        if rev is not None and rev < base_rev * 0.05:
            return False
    return True


def _forecast_one(ticker: str, year: int, strategy: str) -> dict:
    cache = RESPONSES_DIR / f"{ticker}_{year}_{strategy}_forecast.json"
    base_rev = _base_year_revenue(ticker, year)
    if cache.exists():
        cached = _load_cache_json(cache)
        # Reject null/empty/invalid/unit-broken cache — re-run instead
        if isinstance(cached, dict) and cached.get("forecast") and _units_sane(cached, base_rev):
            return cached
        if cache.exists():
            cache.unlink()

    if strategy == "baseline":
        query = "revenues net profit consolidated statement of profit and loss"
        skill = load_skill(BASELINE_SKILL)
        forecast_years = f"{year+1}, {year+2}, {year+3}"
    else:
        query = ("revenues net profit financial highlights ten year five year "
                 "summary CAGR balance sheet MD&A segment performance capex RoE outlook")
        skill = load_skill(ALT_SKILL)
        forecast_years = f"{year+1}, {year+2}, {year+3}"

    chunks = query_chunks(ticker, year, query, n=12)
    context = "\n\n---\n\n".join(chunks)
    prompt = (skill
              .replace("{FORECAST_YEARS}", forecast_years)
              .replace("{BASE_YEAR}", str(year)))
    prompt += f"\n\n=== ANNUAL REPORT TEXT (FY{year} data only) ===\n{context}"

    raw = call_claude(prompt, ticker=ticker, year=year,
                      agent=f"forecaster_{strategy}", max_tokens=4000)
    result = _extract_json(raw)

    # Unit sanity check — retry ONCE with an explicit correction if broken
    if not _units_sane(result, base_rev):
        retry_prompt = (prompt +
            f"\n\nIMPORTANT CORRECTION: Your previous answer used wrong units. "
            f"FY{year} revenue was {base_rev:,.0f} crores. All forecast values must be "
            f"in plain INR Crores at the same scale (similar magnitude, NOT divided by 1000).")
        raw = call_claude(retry_prompt, ticker=ticker, year=year,
                          agent=f"forecaster_{strategy}_retry", max_tokens=4000)
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
        cached = _load_cache_json(cache)
        if isinstance(cached, dict):
            return cached

    if not price_data:
        return {"ticker": ticker, "predictions": [], "reasoning": "No 2024 price data available."}

    rows = "\n".join(f"{r['date']}: {r['close']:.2f}" for r in price_data)
    skill = load_skill(STOCK_SKILL)
    prompt = f"{skill}\n\n=== 2024 DAILY CLOSING PRICES FOR {ticker} ===\n{rows}"

    raw = call_claude(prompt, ticker=ticker, year=2024,
                      agent="stock_predictor", max_tokens=2500)
    if not raw.strip():
        return {"ticker": ticker, "predictions": [], "reasoning": "LLM returned empty response."}
    result = _extract_json(raw)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result


def _structured_history(ticker: str, year: int) -> str:
    """Clean extracted financials from the base-year report as a prompt table."""
    extract = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
    data = _load_cache_json(extract) if extract.exists() else None
    if not data:
        return ""
    lines = ["Year | Revenue (Cr) | Net Income (Cr) | EPS",
             "-----|--------------|-----------------|----"]
    for row in sorted(data.get("years", []), key=lambda r: r.get("year") or 0):
        if row.get("year") and row.get("year") <= year:
            lines.append(f"FY{row['year']} | {row.get('revenue_cr')} | "
                         f"{row.get('net_income_cr')} | {row.get('eps')}")
    defn = data.get("revenue_definition", "")
    return "\n".join(lines) + (f"\n(Revenue line item: {defn})" if defn else "")


def _forecast_alt_v2(ticker: str, year: int) -> dict:
    """Strategy v2: clean structured financials + MD&A outlook chunks.
    The 'more data' improvement the assignment invites — replicates full-P&L
    visibility without raw-chunk unit noise, behind the same anti-leakage rules."""
    cache = RESPONSES_DIR / f"{ticker}_{year}_alt_v2_forecast.json"
    base_rev = _base_year_revenue(ticker, year)
    if cache.exists():
        cached = _load_cache_json(cache)
        if isinstance(cached, dict) and cached.get("forecast") and _units_sane(cached, base_rev):
            return cached
        if cache.exists():
            cache.unlink()

    history = _structured_history(ticker, year)
    chunks = query_chunks(ticker, year,
        "management discussion analysis outlook guidance growth capex plans risks", n=6)
    context = "\n\n---\n\n".join(chunks)

    skill = load_skill(Path("skills/forecast_alt_v2.md"))
    forecast_years = f"{year+1}, {year+2}, {year+3}"
    prompt = (skill
              .replace("{FORECAST_YEARS}", forecast_years)
              .replace("{BASE_YEAR}", str(year)))
    prompt += f"\n\n=== STRUCTURED FINANCIALS (from FY{year} report, INR Crores) ===\n{history}"
    prompt += f"\n\n=== MD&A / OUTLOOK EXCERPTS (FY{year} report) ===\n{context}"

    raw = call_claude(prompt, ticker=ticker, year=year,
                      agent="forecaster_alt_v2", max_tokens=4000)
    result = _extract_json(raw)
    if not _units_sane(result, base_rev):
        retry = prompt + (f"\n\nCORRECTION: FY{year} revenue was {base_rev:,.0f} crores. "
                          f"All values must be plain INR Crores at similar magnitude.")
        raw = call_claude(retry, ticker=ticker, year=year,
                          agent="forecaster_alt_v2_retry", max_tokens=4000)
        result = _extract_json(raw)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return result
