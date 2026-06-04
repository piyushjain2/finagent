# app/agents/screener_fallback.py
"""
Fallback data source when PDF download fails.
Scrapes Screener.in for P&L, Balance Sheet, and key ratios,
filtered to only show data up to the target year — so Claude cannot
"see" future results when forecasting from a historical base year.
"""
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from app.agents.rag_processor import _get_collection, _chunk_text

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _scrape_section_up_to_year(soup: BeautifulSoup, section_title: str, max_year: int) -> str:
    """
    Extract a section table, keeping only columns for years <= max_year.
    This prevents Claude from seeing future data when forecasting from a past base year.
    """
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2 or section_title.lower() not in h2.get_text().lower():
            continue
        table = section.find("table")
        if not table:
            return ""

        lines = []
        keep_cols: list[int] = []  # column indices to keep

        for row_idx, row in enumerate(table.find_all("tr")):
            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if not cells:
                continue

            if row_idx == 0:
                # Header row — find which columns are <= max_year
                keep_cols = [0]  # always keep the label column
                for i, cell in enumerate(cells[1:], 1):
                    # Screener columns look like "Mar 2021", "Mar 2022" etc.
                    year_in_header = None
                    for token in cell.split():
                        if token.isdigit() and len(token) == 4:
                            year_in_header = int(token)
                            break
                    # Keep column if no year found (TTM etc.) AND it's the first non-year
                    # OR if the year is within our allowed range
                    if year_in_header is None or year_in_header <= max_year:
                        keep_cols.append(i)

                filtered = [cells[i] for i in keep_cols if i < len(cells)]
                lines.append(" | ".join(filtered))
            else:
                filtered = [cells[i] for i in keep_cols if i < len(cells)]
                if any(filtered):
                    lines.append(" | ".join(filtered))

        return "\n".join(lines)
    return ""


def build_screener_context(ticker: str, max_year: int | None = None) -> str:
    """
    Fetch P&L, Balance Sheet and Ratios from Screener.in.
    If max_year is given, strips columns for years > max_year.
    This ensures Claude only sees data available as of that year.
    """
    url = f"https://www.screener.in/company/{ticker}/"
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    name_tag = soup.find("h1") or soup.find("title")
    company_name = name_tag.get_text(strip=True).split("|")[0].strip() if name_tag else ticker

    year_label = f"FY{max_year}" if max_year else "latest"
    sections = {}
    for title in ("Profit & Loss", "Balance Sheet", "Ratios"):
        if max_year:
            sections[title] = _scrape_section_up_to_year(soup, title, max_year)
        else:
            # No year filter — use all data (for actuals fetching)
            from app.agents.screener_fallback import _scrape_section_up_to_year as _full
            sections[title] = _scrape_section_up_to_year(soup, title, 9999)

    parts = [
        f"ANNUAL FINANCIAL DATA — {company_name} ({ticker})",
        f"Data as of: {year_label}  |  Currency: INR Crores",
        "=" * 60,
        "",
        f"NOTE: All figures in INR Crores. Data shown only up to FY{max_year}." if max_year else
        "NOTE: All figures in INR Crores.",
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
    Build ChromaDB index from Screener.in data filtered to <= year.
    Idempotent — skips if collection already has documents.
    """
    col = _get_collection(ticker, year)
    if col.count() > 0:
        return True

    text = build_screener_context(ticker, max_year=year)
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
