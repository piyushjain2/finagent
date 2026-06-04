import pytest
from pathlib import Path
from unittest.mock import patch
from app.agents.commentary import generate_commentary

def test_generate_commentary_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.commentary.COMMENTARY_DIR", tmp_path)
    monkeypatch.setattr("app.agents.commentary.EVALS_DIR", tmp_path)
    (tmp_path / "analyst_narrative.md").write_text("Cached narrative.")
    with patch("app.agents.commentary.call_claude") as mock:
        result = generate_commentary()
    mock.assert_not_called()
    assert result == "Cached narrative."

def test_generate_commentary_raises_on_empty_data(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.commentary.COMMENTARY_DIR", tmp_path)
    monkeypatch.setattr("app.agents.commentary.EVALS_DIR", tmp_path)
    # No CSV files in tmp_path → should raise ValueError
    with pytest.raises(ValueError, match="No evaluation data"):
        generate_commentary()

def test_generate_commentary_calls_claude_with_data(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.commentary.COMMENTARY_DIR", tmp_path)
    monkeypatch.setattr("app.agents.commentary.EVALS_DIR", tmp_path)
    # Create a minimal CSV
    (tmp_path / "forecast_accuracy.csv").write_text("ticker,pct_error\nRELIANCE,5.2\n")
    with patch("app.agents.commentary.call_claude", return_value="Generated narrative.") as mock, \
         patch("app.agents.commentary.load_skill", return_value="Skill prompt."):
        result = generate_commentary()
    mock.assert_called_once()
    assert result == "Generated narrative."
    assert (tmp_path / "analyst_narrative.md").read_text() == "Generated narrative."
