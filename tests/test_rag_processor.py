import pytest
from pathlib import Path
from app.agents.rag_processor import process_pdf, query_chunks, VECTOR_DIR

def test_process_pdf_creates_collection(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.rag_processor.VECTOR_DIR", tmp_path / "vs")
    with pytest.MonkeyPatch().context() as m:
        m.setattr("app.agents.rag_processor._extract_text", lambda p: "Revenue 100 crore\n" * 50)
        result = process_pdf("RELIANCE", 2021, Path("fake.pdf"))
    assert result["n_chunks"] > 0
    assert result["ticker"] == "RELIANCE"
    assert result["year"] == 2021

def test_query_chunks_returns_strings(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.rag_processor.VECTOR_DIR", tmp_path / "vs")
    with pytest.MonkeyPatch().context() as m:
        m.setattr("app.agents.rag_processor._extract_text",
                  lambda p: "Revenue 500 crore Net Income 50 crore\n" * 30)
        process_pdf("TCS", 2022, Path("fake.pdf"))
        chunks = query_chunks("TCS", 2022, "Revenue Net Income", n=3)
    assert isinstance(chunks, list)
    assert all(isinstance(c, str) for c in chunks)
