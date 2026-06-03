import json, pytest
from pathlib import Path
from unittest.mock import patch
from app.agents.critique_revise import critique_forecast, revise_forecast

MOCK_FORECAST = {"strategy": "baseline", "base_year": 2021,
    "forecast": [{"year": 2022, "revenue_cr": 680000, "net_income_cr": 58000, "eps": 85.0}],
    "reasoning": "10% growth assumed."}

MOCK_CRITIQUE = json.dumps({
    "company": "RELIANCE", "base_year": 2021, "strategy": "baseline",
    "assumptions": [{"assumption": "10% growth", "failure_scenario": "slowdown", "risk": "Medium"}],
    "confidence_score": 65, "overall_critique": "Reasonable but optimistic."
})

MOCK_REVISED = json.dumps({
    "strategy": "baseline", "base_year": 2021,
    "revised_forecast": [{"year": 2022, "revenue_cr": 660000, "net_income_cr": 56000,
                           "eps": 82.0, "confidence_range_pct": 8}],
    "revisions_made": ["Reduced revenue growth by 10% for medium-risk assumption"],
    "final_confidence_score": 65
})

def test_critique_forecast(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.critique_revise.RESPONSES_DIR", tmp_path)
    with patch("app.agents.critique_revise.call_claude", return_value=MOCK_CRITIQUE):
        result = critique_forecast("RELIANCE", 2021, "baseline", MOCK_FORECAST)
    assert result["confidence_score"] == 65
    assert len(result["assumptions"]) == 1

def test_revise_forecast(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.critique_revise.RESPONSES_DIR", tmp_path)
    critique = json.loads(MOCK_CRITIQUE)
    with patch("app.agents.critique_revise.call_claude", return_value=MOCK_REVISED):
        result = revise_forecast("RELIANCE", 2021, "baseline", MOCK_FORECAST, critique)
    assert result["revised_forecast"][0]["confidence_range_pct"] == 8
