import json, pytest
from pathlib import Path
from unittest.mock import patch
from app.agents.forecaster import run_forecast, RESPONSES_DIR

MOCK_BASELINE = json.dumps({
    "strategy": "baseline", "base_year": 2021,
    "forecast": [
        {"year": 2022, "revenue_cr": 680000, "net_income_cr": 58000, "eps": 85.0},
        {"year": 2023, "revenue_cr": 750000, "net_income_cr": 65000, "eps": 94.0},
        {"year": 2024, "revenue_cr": 820000, "net_income_cr": 73000, "eps": 105.0},
    ],
    "reasoning": "Projected at 10% YoY based on FY21 growth."
})

def test_run_forecast_returns_both_strategies(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.forecaster.RESPONSES_DIR", tmp_path)
    with patch("app.agents.forecaster.query_chunks", return_value=["Revenue data"]), \
         patch("app.agents.forecaster.call_claude", return_value=MOCK_BASELINE):
        result = run_forecast("RELIANCE", 2021)
    assert "baseline" in result
    assert "alt_strategy" in result
    assert len(result["baseline"]["forecast"]) == 3

def test_run_forecast_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.forecaster.RESPONSES_DIR", tmp_path)
    (tmp_path / "RELIANCE_2021_baseline_forecast.json").write_text(MOCK_BASELINE)
    (tmp_path / "RELIANCE_2021_alt_strategy_forecast.json").write_text(
        MOCK_BASELINE.replace('"baseline"', '"alt_strategy"'))
    with patch("app.agents.forecaster.call_claude") as mock:
        run_forecast("RELIANCE", 2021)
    mock.assert_not_called()
