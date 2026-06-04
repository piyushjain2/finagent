# app/agents/pdf_fetcher.py
"""
Downloads annual report PDFs via Screener.in Documents section → BSE direct links.
Works for all NSE-listed companies without needing company-specific IR URLs.
"""
import json
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

PDF_DIR = Path("data/pdfs")
URLS_FILE = Path("data/company_urls.json")
URL_CACHE = Path("data/pdf_url_cache.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _get_with_retry(url: str, timeout: int = 60, retries: int = 3) -> requests.Response:
    """
    GET with exponential backoff. Survives transient DNS failures / network blips
    (e.g. 'Failed to resolve www.bseindia.com') that would otherwise kill a batch run.
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)   # 2s, 4s
    raise last_err  # type: ignore[misc]


def _cached_url(ticker: str, year: int) -> str | None:
    """Return pre-discovered URL from cache file if available."""
    if not URL_CACHE.exists():
        return None
    cache = json.loads(URL_CACHE.read_text())
    return cache.get(ticker, {}).get(str(year))


def _save_to_cache(ticker: str, year: int, url: str) -> None:
    """Persist a discovered URL to cache so it's reused on next run."""
    cache: dict = {}
    if URL_CACHE.exists():
        cache = json.loads(URL_CACHE.read_text())
    cache.setdefault(ticker, {})[str(year)] = url
    URL_CACHE.write_text(json.dumps(cache, indent=2))


# Some companies use a different ticker on Screener.in than their NSE symbol
_SCREENER_TICKER_MAP = {
    "REC": "RECLTD",
}

def _screener_annual_report_url(ticker: str, year: int) -> str | None:
    """
    Scrape Screener.in Documents section to find the BSE annual report PDF
    for the given financial year (year = FY ending, e.g. 2021 = FY2020-21).
    Tries both the NSE ticker and any known Screener.in alias.
    """
    year_str = str(year)
    candidates = [ticker]
    if ticker in _SCREENER_TICKER_MAP:
        candidates = [_SCREENER_TICKER_MAP[ticker], ticker]

    for candidate in candidates:
        url = f"https://www.screener.in/company/{candidate}/"
        try:
            resp = _get_with_retry(url, timeout=20)
        except Exception:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for section in soup.find_all("section"):
            h2 = section.find("h2")
            if not h2 or "Document" not in h2.get_text():
                continue
            for a in section.find_all("a", href=True):
                text = a.get_text(strip=True)
                href = a["href"]
                if year_str in text and "Financial Year" in text and href.lower().endswith(".pdf"):
                    return href
            break

    return None


def _company_ir_url(ticker: str, year: int) -> str | None:
    """
    Fallback: try the IR URL from company_urls.json using BeautifulSoup scraping.
    """
    if not URLS_FILE.exists():
        return None
    company_urls = json.loads(URLS_FILE.read_text())
    if ticker not in company_urls:
        return None
    ir_url = company_urls[ticker]["ir_url"]
    try:
        resp = requests.get(ir_url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        year_str = str(year)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if (year_str in text or year_str in href) and href.lower().endswith(".pdf"):
                if href.startswith("http"):
                    return href
                return ir_url.rstrip("/") + "/" + href.lstrip("/")
    except Exception:
        pass
    return None


def fetch_pdf(ticker: str, year: int) -> Path:
    """
    Download annual report PDF for (ticker, year). Returns local path.
    Skips download if file already exists (checkpoint).

    Strategy:
    1. Screener.in Documents section → BSE direct link (works for all NSE companies)
    2. Company IR page scraping (fallback)
    3. Raises RuntimeError with helpful message if neither works
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"{ticker}_{year}.pdf"
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest

    # Strategy 1: URL cache (pre-seeded + previously discovered)
    pdf_url = _cached_url(ticker, year)

    # Strategy 2: Screener.in → BSE direct link (live discovery)
    if not pdf_url:
        pdf_url = _screener_annual_report_url(ticker, year)
        if pdf_url:
            _save_to_cache(ticker, year, pdf_url)

    # Strategy 3: Company IR page scraping
    if not pdf_url:
        pdf_url = _company_ir_url(ticker, year)

    if not pdf_url:
        raise RuntimeError(
            f"Could not find {year} annual report PDF for {ticker}. "
            f"Place it manually at {dest}"
        )

    resp = _get_with_retry(pdf_url, timeout=120)

    if b"%PDF" not in resp.content[:8]:
        raise RuntimeError(
            f"Downloaded content for {ticker} {year} is not a valid PDF (url: {pdf_url})"
        )

    dest.write_bytes(resp.content)
    return dest
