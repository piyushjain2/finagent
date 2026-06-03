import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.agents.pdf_fetcher import fetch_pdf, PDF_DIR


def test_fetch_pdf_skips_if_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.pdf_fetcher.PDF_DIR", tmp_path)
    pdf = tmp_path / "RELIANCE_2021.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    result = fetch_pdf("RELIANCE", 2021)
    assert result == pdf


def test_fetch_pdf_returns_path_on_download(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.pdf_fetcher.PDF_DIR", tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"%PDF-1.4 test content"
    mock_resp.headers = {"content-type": "application/pdf"}
    with patch("app.agents.pdf_fetcher._find_pdf_url", return_value="http://example.com/ar.pdf"), \
         patch("requests.get", return_value=mock_resp):
        result = fetch_pdf("RELIANCE", 2021)
    assert result == tmp_path / "RELIANCE_2021.pdf"
    assert (tmp_path / "RELIANCE_2021.pdf").exists()
