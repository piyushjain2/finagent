import pandas as pd, pytest
from app.agents.metrics import (
    compute_forecast_accuracy, compute_earnings_surprise,
    compute_trading_returns, compute_stock_prediction_accuracy
)

def test_pct_error_formula(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.metrics.EVALS_DIR", tmp_path)
    rows = compute_forecast_accuracy(
        ticker="RELIANCE", cap_size="Large",
        base_year=2021,
        forecasts={"baseline": {"forecast": [
            {"year": 2022, "revenue_cr": 680000, "net_income_cr": 58000, "eps": 85.0}]}},
        actuals={2022: {"revenue_cr": 721634, "net_income_cr": 60705, "eps": 89.67}}
    )
    assert len(rows) > 0
    row = next(r for r in rows if r["metric"] == "revenue" and r["forecast_year"] == 2022)
    expected_err = round((721634 - 680000) / 721634 * 100, 2)
    assert abs(row["pct_error"] - expected_err) < 0.01

def test_earnings_surprise_formula(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.metrics.EVALS_DIR", tmp_path)
    signal = compute_earnings_surprise(
        ticker="RELIANCE", year=2022,
        forecast_eps=85.0, actual_eps=89.67, price_minus5=2340.0
    )
    expected = round((89.67 - 85.0) / 2340.0, 6)
    assert abs(signal["signal"] - expected) < 1e-5

def test_trading_returns(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.metrics.EVALS_DIR", tmp_path)
    prices = pd.Series(
        [100.0, 102.0, 104.0, 103.0, 105.0, 107.0],
        index=pd.date_range("2022-03-01", periods=6)
    )
    result = compute_trading_returns(
        ticker="RELIANCE", announcement_date="2022-03-01",
        signal_direction=1, stock_prices=prices, nifty_prices=prices * 0.99
    )
    # buy at day+1 = 102, sell at day+5 = 107
    expected_return = round((107.0 - 102.0) / 102.0 * 100, 4)
    assert abs(result["return_pct_5d"] - expected_return) < 0.01
