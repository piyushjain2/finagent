# app/agents/metrics.py
import json
from pathlib import Path
import pandas as pd

EVALS_DIR = Path("data/evals")

def _append_csv(filename: str, rows: list[dict]):
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVALS_DIR / filename
    df_new = pd.DataFrame(rows)
    if path.exists():
        df_existing = pd.read_csv(path)
        ticker = rows[0].get("ticker") if rows else None
        if ticker:
            df_existing = df_existing[df_existing["ticker"] != ticker]
        pd.concat([df_existing, df_new], ignore_index=True).to_csv(path, index=False)
    else:
        df_new.to_csv(path, index=False)

def compute_forecast_accuracy(ticker: str, cap_size: str, base_year: int,
                               forecasts: dict, actuals: dict) -> list[dict]:
    rows = []
    for strategy, fcast_data in forecasts.items():
        for entry in fcast_data.get("revised_forecast", fcast_data.get("forecast", [])):
            fy = entry["year"]
            horizon = fy - base_year
            actual = actuals.get(fy, {})
            for metric, pred_key, actual_key in [
                ("revenue", "revenue_cr", "revenue_cr"),
                ("net_income", "net_income_cr", "net_income_cr"),
                ("eps", "eps", "eps"),
            ]:
                pred = entry.get(pred_key)
                act = actual.get(actual_key)
                pct_err = round((act - pred) / act * 100, 2) if act and pred else None
                conf_range = entry.get("confidence_range_pct")
                within = (abs(pct_err) <= conf_range) if pct_err is not None and conf_range else None
                rows.append({
                    "ticker": ticker, "cap_size": cap_size,
                    "base_year": base_year, "forecast_year": fy,
                    "horizon": f"Y{horizon}", "strategy": strategy,
                    "metric": metric, "predicted": pred, "actual": act,
                    "pct_error": pct_err, "confidence_range_pct": conf_range,
                    "within_confidence_range": within,
                })
    _append_csv("forecast_accuracy.csv", rows)
    return rows

def compute_earnings_surprise(ticker: str, year: int, forecast_eps: float,
                               actual_eps: float, price_minus5: float) -> dict:
    signal = round((actual_eps - forecast_eps) / price_minus5, 6) if price_minus5 else None
    row = {"ticker": ticker, "year": year,
           "forecast_eps": forecast_eps, "actual_eps": actual_eps,
           "price_minus5": price_minus5, "signal": signal}
    _append_csv("earnings_surprise.csv", [row])
    return row

def compute_trading_returns(ticker: str, announcement_date: str, signal_direction: int,
                             stock_prices: pd.Series, nifty_prices: pd.Series) -> dict:
    """Buy at open of day+1, sell at close of day+5 post announcement."""
    try:
        idx = stock_prices.index.get_indexer([announcement_date], method="bfill")[0]
        if idx + 5 >= len(stock_prices):
            return {"ticker": ticker, "announcement_date": announcement_date,
                    "return_pct_5d": None, "nifty_return_pct_5d": None, "excess_return": None}
        buy_price = float(stock_prices.iloc[idx + 1])
        sell_price = float(stock_prices.iloc[idx + 5])
        nifty_buy = float(nifty_prices.iloc[idx + 1])
        nifty_sell = float(nifty_prices.iloc[idx + 5])
        ret = round((sell_price - buy_price) / buy_price * 100, 4)
        nifty_ret = round((nifty_sell - nifty_buy) / nifty_buy * 100, 4)
        excess = round(ret - nifty_ret, 4)
        outperformed = ret > nifty_ret
    except Exception:
        ret = nifty_ret = excess = None
        outperformed = None

    row = {"ticker": ticker, "announcement_date": announcement_date,
           "signal_direction": signal_direction,
           "return_pct_5d": ret, "nifty_return_pct_5d": nifty_ret,
           "excess_return": excess, "outperformed": outperformed}
    _append_csv("trading_returns.csv", [row])
    return row

def compute_stock_prediction_accuracy(ticker: str, predictions: list[dict],
                                       actuals_2025: dict) -> list[dict]:
    """Compare LLM stock predictions vs actual prices."""
    rows = []
    for pred in predictions:
        target = pred["target"]
        predicted = pred["predicted_price"]
        actual = actuals_2025.get(target)
        if actual and predicted:
            pct_err = round((actual - predicted) / actual * 100, 2)
            direction_up_predicted = predicted > actuals_2025.get("Dec-2024", predicted)
            direction_up_actual = actual > actuals_2025.get("Dec-2024", actual)
            direction_correct = direction_up_predicted == direction_up_actual
        else:
            pct_err = None
            direction_correct = None
        rows.append({
            "ticker": ticker, "forecast_target": target,
            "predicted_price": predicted, "actual_price": actual,
            "pct_error": pct_err, "direction_correct": direction_correct,
            "confidence": pred.get("confidence"),
        })
    _append_csv("stock_prediction.csv", rows)
    return rows

def compute_cap_summary():
    """Aggregate forecast accuracy by cap size into cap_summary.csv."""
    src = EVALS_DIR / "forecast_accuracy.csv"
    if not src.exists():
        return
    df = pd.read_csv(src)
    rev_df = df[df["metric"] == "revenue"].copy()

    def _mean_abs_by_horizon(group, h):
        sub = group[group["horizon"] == h]["pct_error"].dropna()
        return sub.abs().mean() if len(sub) > 0 else None

    rows = []
    for cap, grp in rev_df.groupby("cap_size"):
        rows.append({
            "cap_size": cap,
            "n_companies": grp["ticker"].nunique(),
            "avg_y1_error": _mean_abs_by_horizon(grp, "Y1"),
            "avg_y2_error": _mean_abs_by_horizon(grp, "Y2"),
            "avg_y3_error": _mean_abs_by_horizon(grp, "Y3"),
        })

    # Add direction accuracy from stock prediction if available
    stock_path = EVALS_DIR / "stock_prediction.csv"
    if stock_path.exists():
        sdf = pd.read_csv(stock_path)
        cap_map = rev_df[["ticker", "cap_size"]].drop_duplicates()
        merged = sdf.merge(cap_map, on="ticker", how="left")
        dir_agg = merged.groupby("cap_size")["direction_correct"].mean().reset_index()
        dir_agg.columns = ["cap_size", "direction_accuracy"]
        summary_df = pd.DataFrame(rows).merge(dir_agg, on="cap_size", how="left")
    else:
        summary_df = pd.DataFrame(rows)

    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(EVALS_DIR / "cap_summary.csv", index=False)
