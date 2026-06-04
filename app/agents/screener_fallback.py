# app/agents/screener_fallback.py
"""
Fallback data source when PDF download fails.
Scrapes Screener.in for P&L, Balance Sheet, and key ratios,
then indexes the text into ChromaDB so downstream agents work unchanged.
"""
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from app.agents.rag_processor import _get_collection, _chunk_text

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _scrape_section(soup: BeautifulSoup, section_title: str) -> str:
    """Extract a named section table from Screener.in as formatted text."""
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if h2 and section_title.lower() in h2.get_text().lower():
            table = section.find("table")
            if not table:
                return ""
            lines = []
            for row in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if any(cells):
                    lines.append(" | ".join(cells))
            return "\n".join(lines)
    return ""


def build_screener_context(ticker: str) -> str:
    """
    Fetch P&L, Balance Sheet and Ratios from Screener.in.
    Returns a formatted text document suitable for Claude context.
    """
    url = f"https://www.screener.in/company/{ticker}/"
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Company name
    name_tag = soup.find("h1") or soup.find("title")
    company_name = name_tag.get_text(strip=True).split("|")[0].strip() if name_tag else ticker

    sections = {
        "Profit & Loss": _scrape_section(soup, "Profit & Loss"),
        "Balance Sheet":  _scrape_section(soup, "Balance Sheet"),
        "Ratios":         _scrape_section(soup, "Ratios"),
    }

    parts = [
        f"ANNUAL FINANCIAL DATA — {company_name} ({ticker})",
        f"Source: Screener.in  |  Currency: INR Crores",
        "=" * 60,
        "",
        "NOTE: All figures in INR Crores. Columns represent financial years ending March.",
        "",
    ]
    for title, content in sections.items():
        if content:
            parts.append(f"{'=' * 20} {title.upper()} {'=' * 20}")
            parts.append(content)
            parts.append("")

    return "\n".join(parts)


def populate_chromadb_from_screener(ticker: str, year: int) -> bool:
    """
    Build ChromaDB index from Screener.in data when no PDF is available.
    Idempotent — skips if collection already has documents.
    Returns True if collection now has documents.
    """
    col = _get_collection(ticker, year)
    if col.count() > 0:
        return True

    text = build_screener_context(ticker)
    if not text or len(text) < 100:
        return False

    chunks = _chunk_text(text)
    if not chunks:
        return False

    col.add(
        documents=chunks,
        ids=[f"screener_{i:04d}" for i in range(len(chunks))],
    )
    return col.count() > 0
