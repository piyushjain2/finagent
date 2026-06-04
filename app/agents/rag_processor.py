from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import pypdf

VECTOR_DIR = Path("data/vector_stores")
_EF = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
CHUNK_SIZE = 600     # words approx
CHUNK_OVERLAP = 80


def _get_collection(ticker: str, year: int):
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DIR / f"{ticker}_{year}"))
    return client.get_or_create_collection("annual_report", embedding_function=_EF)


def _extract_text(pdf_path: Path) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i: i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def process_pdf(ticker: str, year: int, pdf_path: Path) -> dict:
    """
    Chunk, embed and index PDF into ChromaDB. Idempotent.
    If the existing index was built from the Screener.in fallback (ids prefixed
    'screener_') and a real PDF is now available, wipe and re-index from the PDF —
    the PDF has consolidated financials and is the authoritative source.
    """
    col = _get_collection(ticker, year)
    if col.count() > 0:
        sample = col.get(limit=1)
        ids = sample.get("ids", [])
        built_from_screener = bool(ids) and ids[0].startswith("screener_")
        if not built_from_screener:
            return {"ticker": ticker, "year": year, "n_chunks": col.count(), "cached": True}
        # Real PDF supersedes Screener data — wipe and re-index
        col.delete(ids=col.get()["ids"])

    text = _extract_text(pdf_path)
    chunks = _chunk_text(text)
    col.add(
        documents=chunks,
        ids=[f"chunk_{i:04d}" for i in range(len(chunks))],
    )
    return {"ticker": ticker, "year": year, "n_chunks": len(chunks), "cached": False}


def query_chunks(ticker: str, year: int, query: str, n: int = 8) -> list[str]:
    """Return top-n relevant text chunks for the given query."""
    col = _get_collection(ticker, year)
    results = col.query(query_texts=[query], n_results=min(n, col.count()))
    return results["documents"][0]
