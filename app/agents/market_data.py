# app/agents/market_data.py
import json, requests
from pathlib import Path
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup

RESPONSES_DIR = Path("data/responses")
MARKET_DIR = Path("data/market")

ACTUAL_YEARS = (2022, 2023, 2024, 2025)   # 2025 available as of 2026

def fetch_actuals(ticker: str) -> dict[int, dict]:
    """
    Return {year: {revenue_cr, net_income_cr, eps}} for FY2022-2025.
    Tier 1: extracted PDF data. Tier 2: yfinance. Tier 3: Screener.in scrape.
    """
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache = MARKET_DIR / f"{ticker}_actuals.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}

    actuals: dict[int, dict] = {}

    # Tier 1: PDF extraction results (2022–2025 reports)
    for year in ACTUAL_YEARS:
        extract_file = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
        if extract_file.exists():
            data = json.loads(extract_file.read_text())
            for row in data.get("years", []):
                y = row.get("year")
                if y and row.get("revenue_cr") is not None:
                    actuals[y] = {
                        "revenue_cr": row["revenue_cr"],
                        "net_income_cr": row["net_income_cr"],
                        "eps": row.get("eps"),
                        "source": "pdf_extraction",
                    }

    # Tier 2: yfinance for any missing years
    missing = [y for y in ACTUAL_YEARS if y not in actuals]
    if missing:
        try:
            t = yf.Ticker(f"{ticker}.NS")
            fin = t.financials
            if fin is not None and not fin.empty:
                import math
                for col in fin.columns:
                    yr = col.year
                    if yr in missing:
                        rev = fin.loc["Total Revenue", col] / 1e7 if "Total Revenue" in fin.index else None
                        ni = fin.loc["Net Income", col] / 1e7 if "Net Income" in fin.index else None
                        # NaN is truthy — explicitly reject it
                        if rev is not None and not math.isnan(rev):
                            actuals[yr] = {"revenue_cr": round(rev, 2),
                                           "net_income_cr": round(ni, 2) if ni is not None and not math.isnan(ni) else None,
                                           "eps": None, "source": "yfinance"}
        except Exception:
            pass

    # Tier 3: Screener.in public page
    missing = [y for y in ACTUAL_YEARS if y not in actuals]
    if missing:
        try:
            url = f"https://www.screener.in/company/{ticker}/"
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for table in soup.find_all("table"):
                headers = [th.get_text(strip=True) for th in table.find_all("th")]
                years_in_header = [int(h[:4]) for h in headers if h[:4].isdigit()]
                for row in table.find_all("tr"):
                    cells = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
                    if not cells:
                        continue
                    label = cells[0].lower()
                    for i, yr in enumerate(years_in_header):
                        if yr in missing and i + 1 < len(cells):
                            try:
                                val = float(cells[i + 1])
                            except ValueError:
                                continue
                            if yr not in actuals:
                                actuals[yr] = {"revenue_cr": None, "net_income_cr": None,
                                               "eps": None, "source": "screener"}
                            if "sales" in label or "revenue" in label:
                                actuals[yr]["revenue_cr"] = val
                            elif "net profit" in label or "pat" in label:
                                actuals[yr]["net_income_cr"] = val
                            elif "eps" in label:
                                actuals[yr]["eps"] = val
        except Exception:
            pass

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
        t = yf.Ticker(f"{ticker}.NS")
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
        t = yf.Ticker(f"{ticker}.NS")
        cal = t.calendar
        if cal is not None and "Earnings Date" in cal.index:
            dates = [str(d.date()) for d in cal.loc["Earnings Date"] if hasattr(d, "date")]
    except Exception:
        pass
    cache.write_text(json.dumps(dates))
    return dates
