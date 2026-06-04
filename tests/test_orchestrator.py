# tests/test_orchestrator.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
from app.orchestrator import run_pipeline, _get_cap_size

def test_get_cap_size_large():
    assert _get_cap_size("RELIANCE") == "Large"
    assert _get_cap_size("TCS") == "Large"

def test_get_cap_size_mid():
    assert _get_cap_size("REC") == "Mid"
    assert _get_cap_size("PFC") == "Mid"

def test_get_cap_size_small():
    assert _get_cap_size("KEC") == "Small"
    assert _get_cap_size("SKIPPER") == "Small"

@pytest.mark.asyncio
async def test_run_pipeline_emits_events():
    events = []

    async def mock_emit(ticker, event, data):
        events.append(event)

    empty_df = pd.DataFrame({"close": [100.0, 101.0]},
                            index=pd.date_range("2024-01-01", periods=2, name="date"))

    with patch("app.orchestrator.bus") as mock_bus, \
         patch("app.orchestrator.fetch_pdf", return_value=MagicMock()), \
         patch("app.orchestrator.process_pdf", return_value={"n_chunks": 10, "cached": False}), \
         patch("app.orchestrator.extract_financials", return_value={"years": []}), \
         patch("app.orchestrator.run_forecast", return_value={
             "baseline": {"forecast": [{"year": 2022, "revenue_cr": 1000, "net_income_cr": 100, "eps": 10.0}]},
             "alt_strategy": {"forecast": [{"year": 2022, "revenue_cr": 1100, "net_income_cr": 110, "eps": 11.0}]}
         }), \
         patch("app.orchestrator.critique_forecast", return_value={"assumptions": [], "confidence_score": 70}), \
         patch("app.orchestrator.revise_forecast", return_value={"revised_forecast": [], "final_confidence_score": 70}), \
         patch("app.orchestrator.fetch_actuals", return_value={2022: {"revenue_cr": 1050, "net_income_cr": 105, "eps": 10.5}}), \
         patch("app.orchestrator.fetch_prices", return_value=empty_df), \
         patch("app.orchestrator.fetch_nifty50", return_value=empty_df), \
         patch("app.orchestrator.fetch_earnings_dates", return_value=[]), \
         patch("app.orchestrator.compute_forecast_accuracy", return_value=[]), \
         patch("app.orchestrator.compute_cap_summary"), \
         patch("app.orchestrator.run_stock_prediction", return_value={"predictions": []}), \
         patch("app.orchestrator.compute_stock_prediction_accuracy", return_value=[]):
        mock_bus.emit = mock_emit
        await run_pipeline("RELIANCE")

    assert "agent_start" in events
    assert "pipeline_complete" in events
