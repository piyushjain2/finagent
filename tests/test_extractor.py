import json, pytest
from pathlib import Path
from unittest.mock import patch
from app.agents.extractor import extract_financials

MOCK_RESPONSE = json.dumps({
    "company": "RELIANCE",
    "years": [{"year": 2021, "revenue_cr": 411256, "net_income_cr": 49128, "eps": 72.54}],
    "currency": "INR Crores", "notes": ""
})

def test_extract_financials_returns_structured_data(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.extractor.RESPONSES_DIR", tmp_path)
    with patch("app.agents.extractor.query_chunks", return_value=["Revenue 411256 crore"]), \
         patch("app.agents.extractor.call_claude", return_value=MOCK_RESPONSE):
        result = extract_financials("RELIANCE", 2021)
    assert result["years"][0]["revenue_cr"] == 411256
    assert result["years"][0]["net_income_cr"] == 49128

def test_extract_financials_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.extractor.RESPONSES_DIR", tmp_path)
    cache = tmp_path / "RELIANCE_2021_extract.json"
    cache.write_text(MOCK_RESPONSE)
    with patch("app.agents.extractor.call_claude") as mock_claude:
        result = extract_financials("RELIANCE", 2021)
    mock_claude.assert_not_called()
    assert result["years"][0]["eps"] == 72.54
