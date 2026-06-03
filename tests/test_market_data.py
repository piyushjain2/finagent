import json, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.agents.market_data import fetch_actuals, fetch_prices, fetch_earnings_dates

def test_fetch_actuals_from_extracted_json(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.market_data.RESPONSES_DIR", tmp_path)
    monkeypatch.setattr("app.agents.market_data.MARKET_DIR", tmp_path)
    (tmp_path / "RELIANCE_2022_extract.json").write_text(json.dumps({
        "years": [{"year": 2022, "revenue_cr": 721634, "net_income_cr": 60705, "eps": 89.67}]
    }))
    actuals = fetch_actuals("RELIANCE")
    assert actuals[2022]["revenue_cr"] == 721634

def test_fetch_prices_returns_dataframe(tmp_path, monkeypatch):
    import pandas as pd
    monkeypatch.setattr("app.agents.market_data.MARKET_DIR", tmp_path)
    mock_df = pd.DataFrame(
        {"Close": [2300.0, 2320.0, 2310.0, 2340.0, 2350.0]},
        index=pd.date_range("2024-01-01", periods=5, name="Date")
    )
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_df
        prices = fetch_prices("RELIANCE")
    assert len(prices) == 5
    assert "close" in prices.columns
