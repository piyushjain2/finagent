import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.claude_client import call_claude, load_skill


def test_call_claude_logs_to_vault(tmp_path, monkeypatch):
    monkeypatch.setattr("app.claude_client.PROMPTS_DIR", tmp_path / "prompts")
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="test response")]
    monkeypatch.setattr("app.claude_client._client", mock_client)

    result = call_claude("hello", ticker="RELIANCE", year=2021, agent="test")

    assert result == "test response"
    log_file = tmp_path / "prompts" / "RELIANCE_2021_test.jsonl"
    assert log_file.exists()
    entry = json.loads(log_file.read_text().strip())
    assert entry["ticker"] == "RELIANCE"
    assert entry["prompt"] == "hello"
    assert entry["response"] == "test response"


def test_load_skill_reads_md_file(tmp_path):
    skill_file = tmp_path / "test_skill.md"
    skill_file.write_text("Step 1: do X\nStep 2: do Y")
    content = load_skill(tmp_path / "test_skill.md")
    assert "Step 1" in content
