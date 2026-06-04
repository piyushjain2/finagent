# tests/test_report_writer.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.agents.report_writer import generate_report, _df_to_table, _add_heading
from docx import Document
import pandas as pd


def test_generate_report_creates_docx(tmp_path, monkeypatch):
    """generate_report() creates a .docx file even with no eval data."""
    import app.agents.report_writer as rw
    monkeypatch.setattr(rw, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(rw, "EVALS_DIR", tmp_path / "evals")
    monkeypatch.setattr(rw, "PROMPTS_DIR", tmp_path / "prompts")
    monkeypatch.setattr(rw, "COMMENTARY_DIR", tmp_path / "commentary")
    # Write minimal company_urls.json that generate_report reads
    urls = {"RELIANCE": {"ir_url": "http://x.com", "nse_code": "RELIANCE"}}
    (tmp_path / "evals").mkdir(parents=True)
    # Patch the Path("data/company_urls.json") read inside generate_report
    original_read = Path.read_text
    def fake_read(self, *a, **kw):
        if "company_urls" in str(self):
            return json.dumps(urls)
        return original_read(self, *a, **kw)
    monkeypatch.setattr(Path, "read_text", fake_read)
    out = generate_report()
    assert out.exists()
    assert out.suffix == ".docx"


def test_df_to_table_writes_header_and_rows():
    """_df_to_table adds one header row + one data row to the document."""
    doc = Document()
    df = pd.DataFrame({"ticker": ["RELIANCE"], "pct_error": [5.2]})
    _df_to_table(doc, df)
    # Document should now have a table
    assert len(doc.tables) == 1
    tbl = doc.tables[0]
    assert tbl.rows[0].cells[0].text == "ticker"
    assert tbl.rows[1].cells[0].text == "RELIANCE"


def test_add_heading_does_not_crash_on_empty_heading():
    """_add_heading is safe even when the heading produces no runs."""
    doc = Document()
    # Should not raise
    _add_heading(doc, "Test Heading", 1)
    _add_heading(doc, "", 2)
