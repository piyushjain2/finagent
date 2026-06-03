import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

PDF_DIR = Path("data/pdfs")
URLS_FILE = Path("data/company_urls.json")


def fetch_pdf(ticker: str, year: int) -> Path:
    """Download annual report PDF. Returns path. Skips if already exists."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"{ticker}_{year}.pdf"
    if dest.exists():
        return dest

    company_urls = json.loads(URLS_FILE.read_text())
    if ticker not in company_urls:
        raise ValueError(f"No IR URL configured for {ticker}")

    ir_url = company_urls[ticker]["ir_url"]
    pdf_url = _find_pdf_url(ir_url, year)
    if not pdf_url:
        raise RuntimeError(f"Could not find {year} annual report PDF for {ticker} at {ir_url}")

    resp = requests.get(pdf_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def _find_pdf_url(ir_url: str, year: int) -> str | None:
    """Scrape IR page to find annual report PDF link for the given year."""
    try:
        resp = requests.get(ir_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        year_str = str(year)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if (year_str in text or year_str in href) and href.lower().endswith(".pdf"):
                return href if href.startswith("http") else ir_url.rstrip("/") + "/" + href.lstrip("/")
    except Exception:
        pass
    return None
