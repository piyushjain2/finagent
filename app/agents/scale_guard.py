# app/agents/scale_guard.py
"""
Unit-slip correction using Screener.in as a magnitude reference.

Problem: annual reports state P&L in ₹ million / lakh / crore inconsistently;
LLM extraction occasionally mis-converts by a power of 10. Forecasts and actuals
then sit on different scales and the % errors become meaningless garbage.

Policy (methodologically conservative):
  - PDF-extracted values remain the data source.
  - Screener.in consolidated figures are used ONLY as a magnitude tripwire.
  - A value is corrected ONLY by a power of 10 (10x, 100x, 0.1x ...), and only
    when that correction lands within ±45% of the reference. Genuine forecast
    error is never altered.
  - Every correction is logged to data/evals/scale_corrections.csv for audit.
"""
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MARKET_DIR = Path("data/market")
EVALS_DIR = Path("data/evals")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

_SCREENER_ALIAS = {"REC": "RECLTD"}

_corrections_log: list[dict] = []


def fetch_screener_reference(ticker: str) -> dict[int, dict]:
    """
    {year: {revenue_cr, net_income_cr, eps}} from Screener.in CONSOLIDATED P&L.
    Cached to data/market/{ticker}_screener_ref.json.
    """
    cache = MARKET_DIR / f"{ticker}_screener_ref.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}

    candidate = _SCREENER_ALIAS.get(ticker, ticker)
    out: dict[int, dict] = {}
    for url in (f"https://www.screener.in/company/{candidate}/consolidated/",
                f"https://www.screener.in/company/{candidate}/"):
        try:
            resp = requests.get(url, timeout=20, headers=HEADERS)
            resp.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for section in soup.find_all("section"):
            h2 = section.find("h2")
            if not h2 or "profit & loss" not in h2.get_text().lower():
                continue
            table = section.find("table")
            if not table:
                break
            rows = table.find_all("tr")
            if not rows:
                break
            header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
            years = []
            for h in header[1:]:
                tok = [t for t in h.split() if t.isdigit() and len(t) == 4]
                years.append(int(tok[0]) if tok else None)
            for row in rows[1:]:
                cells = [c.get_text(strip=True).replace(",", "") for c in row.find_all(["th", "td"])]
                if not cells:
                    continue
                label = cells[0].lower()
                key = None
                if label.startswith(("sales", "revenue")):
                    key = "revenue_cr"
                elif label.startswith("net profit"):
                    key = "net_income_cr"
                elif label.startswith("eps"):
                    key = "eps"
                if not key:
                    continue
                for yi, year in enumerate(years):
                    if year is None or yi + 1 >= len(cells):
                        continue
                    try:
                        val = float(cells[yi + 1].replace("%", ""))
                    except ValueError:
                        continue
                    out.setdefault(year, {})[key] = val
            break
        if out:
            break
        time.sleep(1)

    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


def snap_scale(value: float | None, reference: float | None,
               ticker: str = "", year: int = 0, field: str = "",
               source: str = "", null_if_unfixable: bool = False) -> float | None:
    """
    If value is off from reference by ~a power of 10, snap it.
    Otherwise return it unchanged. Corrections are logged.

    null_if_unfixable: for ACTUALS only — when the value is wildly off-basis
    (e.g. standalone vs consolidated AND wrong scale) and no power-of-10
    correction lands near the reference, return None so the comparison is
    excluded (N/A) instead of producing a garbage error percentage.
    Forecasts are never nulled — a wild forecast is a legitimate finding.
    """
    if value is None or reference is None or reference == 0 or value == 0:
        return value
    # Already in the right ballpark (within ±55%) — leave untouched
    if 0.45 <= abs(value / reference) <= 2.2:
        return value
    for k in (1, 2, 3, -1, -2, -3):
        scaled = value * (10 ** k)
        if 0.55 <= abs(scaled / reference) <= 1.8:
            _corrections_log.append({
                "ticker": ticker, "year": year, "field": field, "source": source,
                "original": value, "corrected": scaled, "screener_ref": reference,
                "factor": f"x10^{k}",
            })
            return scaled
    if null_if_unfixable:
        _corrections_log.append({
            "ticker": ticker, "year": year, "field": field, "source": source,
            "original": value, "corrected": None, "screener_ref": reference,
            "factor": "EXCLUDED (off-basis, unfixable)",
        })
        return None
    return value   # genuinely different — leave it (could be real forecast error)


def flush_corrections_log():
    """Write the audit trail of every scale correction."""
    import pandas as pd
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVALS_DIR / "scale_corrections.csv"
    if _corrections_log:
        pd.DataFrame(_corrections_log).to_csv(path, index=False)
    elif path.exists():
        path.unlink()
    n = len(_corrections_log)
    _corrections_log.clear()
    return n
