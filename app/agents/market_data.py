# app/agents/market_data.py
# Financial actuals: PDF extraction ONLY (official annual reports).
# yfinance is used solely for daily price data (Q2) and the NIFTY50 benchmark.
import json
from pathlib import Path
import yfinance as yf
import pandas as pd

RESPONSES_DIR = Path("data/responses")
MARKET_DIR = Path("data/market")

ACTUAL_YEARS = (2022, 2023, 2024, 2025)   # 2025 available as of 2026

# NSE symbol → Yahoo Finance symbol where they differ
_YF_TICKER_MAP = {
    "REC": "RECLTD",
}

def _yf_symbol(ticker: str) -> str:
    return f"{_YF_TICKER_MAP.get(ticker, ticker)}.NS"

def fetch_actuals(ticker: str) -> dict[int, dict]:
    """
    Return {year: {revenue_cr, net_income_cr, eps}} for FY2022-2025.

    STRICT POLICY: actuals come ONLY from official annual report PDF extractions
    (consolidated figures). No yfinance/Screener fundamentals — those mix
    standalone and consolidated data and cannot be trusted for comparisons.
    A year with no extracted PDF simply has no actual (shown as N/A in reports).
    """
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / f"{ticker}_actuals.json"
    if cache.exists():
        cached = {int(k): v for k, v in json.loads(cache.read_text()).items()}
        # Invalidate caches from older policies (multi-tier or pre-self_row)
        if cached and all(v.get("source") == "pdf_extraction" and "self_row" in v
                          for v in cached.values()):
            return cached
        cache.unlink()

    actuals: dict[int, dict] = {}
    for year in ACTUAL_YEARS:
        extract_file = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
        if extract_file.exists():
            try:
                data = json.loads(extract_file.read_text())
            except json.JSONDecodeError:
                extract_file.unlink()
                continue
            for row in data.get("years", []):
                y = row.get("year")
                if not (y and row.get("revenue_cr") is not None):
                    continue
                # SAME-YEAR PREFERENCE: a report's own audited year beats another
                # report's comparative column. Never overwrite a self-row.
                is_self_row = (y == year)
                existing = actuals.get(y)
                if existing and existing.get("self_row") and not is_self_row:
                    continue
                actuals[y] = {
                    "revenue_cr": row["revenue_cr"],
                    "net_income_cr": row["net_income_cr"],
                    "eps": row.get("eps"),
                    "source": "pdf_extraction",
                    "self_row": is_self_row,
                }

    cache.write_text(json.dumps(actuals))
    return actuals

def fetch_prices(ticker: str) -> pd.DataFrame:
    """Download Jan-Dec 2024 daily closing prices. Returns DataFrame with 'close' column."""
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / f"{ticker}_2024_prices.csv"
    if cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df

    try:
        t = yf.Ticker(_yf_symbol(ticker))
        df = t.history(start="2024-01-01", end="2024-12-31")
        df = df[["Close"]].rename(columns={"Close": "close"})
        df.index.name = "date"
        df.to_csv(cache)
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to fetch prices for {ticker}: {e}") from e

def fetch_nifty50() -> pd.DataFrame:
    """Download 2024 NIFTY50 daily closes as benchmark."""
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / "NIFTY50_2024_prices.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    try:
        df = yf.Ticker("^NSEI").history(start="2024-01-01", end="2024-12-31")[["Close"]]
        df.columns = ["close"]
        df.index.name = "date"
        df.to_csv(cache)
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to fetch NIFTY50: {e}") from e

def fetch_earnings_dates(ticker: str) -> list[str]:
    """Fetch earnings announcement dates from yfinance calendar."""
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / f"{ticker}_earnings_dates.json"
    if cache.exists():
        return json.loads(cache.read_text())
    dates = []
    try:
        t = yf.Ticker(_yf_symbol(ticker))
        cal = t.calendar
        if cal is not None and "Earnings Date" in cal.index:
            dates = [str(d.date()) for d in cal.loc["Earnings Date"] if hasattr(d, "date")]
    except Exception:
        pass
    cache.write_text(json.dumps(dates))
    return dates

# ── Q1d: earnings announcements + multi-year prices ───────────────────────────

def fetch_annual_announcement_dates(ticker: str) -> dict[int, str]:
    """
    FY → annual results announcement date (Indian FY ends March; results
    announced April–June). Sourced from yfinance historical earnings dates.
    """
    cache = MARKET_DIR / f"{ticker}_announcements.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}

    out: dict[int, str] = {}
    try:
        t = yf.Ticker(_yf_symbol(ticker))
        ed = t.get_earnings_dates(limit=60)
        if ed is not None and not ed.empty:
            for ts in sorted(ed.index):
                if ts.month in (4, 5, 6) and ts.year in (2022, 2023, 2024, 2025):
                    out.setdefault(ts.year, str(ts.date()))   # earliest in window = Q4/annual
    except Exception:
        pass
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


def fetch_prices_range(ticker: str, start: str = "2022-01-01", end: str = "2025-12-31") -> pd.DataFrame:
    """Daily closes across the full analysis window (announcement-window returns)."""
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / f"{ticker}_full_prices.csv"
    if cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df
    t = yf.Ticker(_yf_symbol(ticker))
    df = t.history(start=start, end=end)
    df = df[["Close"]].rename(columns={"Close": "close"})
    df.index.name = "date"
    df.to_csv(cache)
    return df


def fetch_nifty_range(start: str = "2022-01-01", end: str = "2025-12-31") -> pd.DataFrame:
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / "NIFTY50_full_prices.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)
    df = yf.Ticker("^NSEI").history(start=start, end=end)[["Close"]]
    df.columns = ["close"]
    df.index.name = "date"
    df.to_csv(cache)
    return df
