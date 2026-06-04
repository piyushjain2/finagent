"""
Rebuild all eval CSVs from cached pipeline outputs — ZERO Claude API calls.
Only network use: yfinance (announcement dates + price history), all cached after first run.

Computes:
  - forecast_accuracy.csv   (both base years — fixes the dedup-wipe bug)
  - earnings_surprise.csv   (Q1d signal using Y1 forecasts + announcement dates)
  - trading_returns.csv     (Q1d buy-hold +5d vs NIFTY50)
  - stock_prediction.csv    (Q2, rebuilt from cached predictions)
  - cap_summary.csv

Usage: python rebuild_evals.py
"""
import json
from pathlib import Path

import pandas as pd

from app.orchestrator import _get_cap_size
from app.agents.market_data import (
    fetch_actuals, fetch_annual_announcement_dates,
    fetch_prices_range, fetch_nifty_range, _yf_symbol,
)
from app.agents.metrics import (
    compute_forecast_accuracy, compute_earnings_surprise,
    compute_trading_returns, compute_stock_prediction_accuracy,
    compute_cap_summary, EVALS_DIR,
)
from app.agents.scale_guard import (
    fetch_screener_reference, snap_scale, flush_corrections_log,
)


def _snap_actuals(ticker: str, actuals: dict, ref: dict) -> dict:
    """Power-of-10 unit-slip correction on PDF-extracted actuals.
    Unfixable off-basis actuals are EXCLUDED (None) — a wrong ground truth
    is worse than a missing one."""
    for year, vals in actuals.items():
        r = ref.get(year, {})
        for field in ("revenue_cr", "net_income_cr", "eps"):
            vals[field] = snap_scale(vals.get(field), r.get(field),
                                     ticker, year, field, source="actual",
                                     null_if_unfixable=True)
    return actuals


def _snap_forecasts(ticker: str, forecasts: dict, ref: dict) -> dict:
    """Power-of-10 unit-slip correction on LLM forecasts (against same-year reference)."""
    for strategy, fcast in forecasts.items():
        rows = fcast.get("revised_forecast") or fcast.get("forecast", [])
        for row in rows:
            r = ref.get(row.get("year"), {})
            for field in ("revenue_cr", "net_income_cr", "eps"):
                row[field] = snap_scale(row.get(field), r.get(field),
                                        ticker, row.get("year", 0), field,
                                        source=f"forecast_{strategy}")
    return forecasts

RESPONSES_DIR = Path("data/responses")
TICKERS = list(json.loads(Path("data/company_urls.json").read_text()).keys())
FORECAST_BASE_YEARS = [2021, 2022]


def _load_forecasts(ticker: str, base_year: int) -> dict:
    """Load revised forecasts (fall back to plain) for both strategies."""
    out = {}
    for strategy in ("baseline", "alt_strategy"):
        for suffix in (f"{strategy}_revised_forecast", f"{strategy}_forecast"):
            p = RESPONSES_DIR / f"{ticker}_{base_year}_{suffix}.json"
            if p.exists():
                try:
                    out[strategy] = json.loads(p.read_text())
                    break
                except json.JSONDecodeError:
                    continue
    return out


def _y1_forecast_eps(ticker: str, fy: int) -> float | None:
    """EPS forecast for FY made one year earlier (Y1 horizon, baseline strategy)."""
    forecasts = _load_forecasts(ticker, fy - 1)
    fcast = forecasts.get("baseline", {})
    rows = fcast.get("revised_forecast") or fcast.get("forecast", [])
    for r in rows:
        if r.get("year") == fy and r.get("eps"):
            return float(r["eps"])
    return None


def main():
    # Start fresh — the old CSVs have dedup-wiped data
    for f in EVALS_DIR.glob("*.csv"):
        f.unlink()
    print("Old eval CSVs cleared.\n")

    nifty_full = fetch_nifty_range()

    for ticker in TICKERS:
        print(f"{ticker}:")
        cap = _get_cap_size(ticker)
        actuals = fetch_actuals(ticker)

        # ── Scale guard: snap power-of-10 unit slips against Screener reference ──
        ref = fetch_screener_reference(ticker)
        if ref:
            actuals = _snap_actuals(ticker, actuals, ref)
        else:
            print(f"  ⚠ no Screener reference — scale guard skipped")

        # ── Forecast accuracy (both base years) ───────────────────────────
        for base_year in FORECAST_BASE_YEARS:
            forecasts = _load_forecasts(ticker, base_year)
            if forecasts:
                if ref:
                    forecasts = _snap_forecasts(ticker, forecasts, ref)
                rows = compute_forecast_accuracy(ticker, cap, base_year, forecasts, actuals)
                print(f"  forecast_accuracy base {base_year}: {len(rows)} rows")
            else:
                print(f"  ⚠ no forecasts for base {base_year}")

        # ── Q1d: earnings surprise + trading returns ──────────────────────
        announcements = fetch_annual_announcement_dates(ticker)
        try:
            prices_full = fetch_prices_range(ticker)
        except Exception as e:
            print(f"  ⚠ prices: {e}")
            prices_full = pd.DataFrame()

        for fy in (2022, 2023):   # Y1-horizon forecasts exist for these
            date_str = announcements.get(fy)
            fcast_eps = _y1_forecast_eps(ticker, fy)
            actual_eps = actuals.get(fy, {}).get("eps")
            if not (date_str and fcast_eps and actual_eps and not prices_full.empty):
                print(f"  ⚠ Q1d FY{fy}: missing "
                      f"{'date ' if not date_str else ''}"
                      f"{'fcast_eps ' if not fcast_eps else ''}"
                      f"{'actual_eps ' if not actual_eps else ''}"
                      f"{'prices' if prices_full.empty else ''}")
                continue
            # price 5 trading days before announcement
            closes = prices_full["close"]
            closes.index = closes.index.tz_localize(None)
            before = closes[closes.index < pd.Timestamp(date_str)]
            if len(before) < 5:
                print(f"  ⚠ Q1d FY{fy}: insufficient price history before {date_str}")
                continue
            price_m5 = float(before.iloc[-5])
            surprise = compute_earnings_surprise(ticker, fy, fcast_eps, actual_eps, price_m5)
            direction = 1 if (surprise["signal"] or 0) > 0 else -1
            nifty_closes = nifty_full["close"]
            nifty_closes.index = pd.to_datetime(nifty_closes.index).tz_localize(None)
            compute_trading_returns(ticker, date_str, direction, closes, nifty_closes)
            print(f"  Q1d FY{fy}: signal={surprise['signal']} (ann {date_str})")

        # ── Q2: stock prediction accuracy ──────────────────────────────────
        pred_file = RESPONSES_DIR / f"{ticker}_stock_prediction.json"
        if pred_file.exists():
            try:
                stock_pred = json.loads(pred_file.read_text())
            except json.JSONDecodeError:
                stock_pred = {}
            predictions = stock_pred.get("predictions", [])
            if predictions:
                actuals_2025: dict = {}
                try:
                    if not prices_full.empty:
                        c = prices_full["close"]
                        c.index = pd.to_datetime(c.index).tz_localize(None)
                        def _eom(year, month):
                            sub = c[(c.index.year == year) & (c.index.month == month)]
                            return float(sub.iloc[-1]) if not sub.empty else None
                        actuals_2025 = {
                            "Jan-2025": _eom(2025, 1), "Mar-2025": _eom(2025, 3),
                            "Dec-2025": _eom(2025, 12), "Dec-2024": _eom(2024, 12),
                        }
                except Exception:
                    pass
                rows = compute_stock_prediction_accuracy(ticker, predictions, actuals_2025)
                print(f"  Q2: {len(rows)} prediction rows")

    compute_cap_summary()
    n_corrections = flush_corrections_log()
    print(f"\n✅ Eval rebuild complete. Scale corrections applied: {n_corrections} "
          f"(audit: data/evals/scale_corrections.csv)")

    # Summary
    for csv in sorted(EVALS_DIR.glob("*.csv")):
        df = pd.read_csv(csv)
        print(f"  {csv.name}: {len(df)} rows, {df['ticker'].nunique() if 'ticker' in df else '-'} tickers")


if __name__ == "__main__":
    main()
