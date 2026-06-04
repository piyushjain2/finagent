"""
Batch annual report downloader for Group 11 companies.
Discovers PDF URLs via Screener.in → BSE, then downloads them all.

Usage:
    python download_reports.py           # discover + download all
    python download_reports.py --dry-run # discover URLs only, don't download
"""
import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TICKERS = [
    # Large-cap
    "RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK",
    "SBIN", "ITC", "LT", "NTPC", "ONGC",
    # Mid-cap
    "REC", "PFC", "HUDCO", "IREDA", "IFCI",
    # Small-cap
    "KEC", "TEXRAIL", "POWERMECH", "VINDHYATEL", "SKIPPER",
]
YEARS = [2021, 2022, 2023, 2024, 2025]

PDF_DIR = Path("data/pdfs")
URL_CACHE = Path("data/pdf_url_cache.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Companies whose Screener.in ticker differs from NSE ticker
SCREENER_ALIAS = {"REC": "RECLTD"}


# ── URL discovery ──────────────────────────────────────────────────────────────

def _find_on_screener(ticker: str, years: list[int]) -> dict[int, str]:
    """Return {year: pdf_url} for all discoverable years on Screener.in."""
    candidate = SCREENER_ALIAS.get(ticker, ticker)
    url = f"https://www.screener.in/company/{candidate}/"
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    ⚠ Screener.in fetch failed for {ticker}: {e}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    found: dict[int, str] = {}

    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2 or "Document" not in h2.get_text():
            continue
        for a in section.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            for year in years:
                if str(year) in text and "Financial Year" in text and href.lower().endswith(".pdf"):
                    found[year] = href
        break

    return found


def discover_all_urls(years: list[int]) -> dict:
    """
    Discover PDF URLs for all tickers. Uses cached results where available.
    Rate-limited to avoid Screener.in throttling.
    """
    cache: dict = {}
    if URL_CACHE.exists():
        cache = json.loads(URL_CACHE.read_text())
        print(f"Loaded {sum(len(v) for v in cache.values())} cached URLs")

    for i, ticker in enumerate(TICKERS):
        # Check which years still need discovery
        cached_years = set(int(y) for y in cache.get(ticker, {}).keys())
        needed = [y for y in years if y not in cached_years]

        if not needed:
            print(f"  {ticker:12s} all years cached ✓")
            continue

        print(f"  {ticker:12s} discovering {needed}...")
        found = _find_on_screener(ticker, needed)

        if ticker not in cache:
            cache[ticker] = {}
        for year, url in found.items():
            cache[ticker][str(year)] = url

        missing = [y for y in needed if y not in found]
        if missing:
            print(f"    ❌ Not found on Screener.in: {missing}")

        # Rate limiting — be polite to Screener.in
        if i < len(TICKERS) - 1:
            time.sleep(1.5)

    # Save updated cache
    URL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    URL_CACHE.write_text(json.dumps(cache, indent=2))
    return cache


# ── Download ──────────────────────────────────────────────────────────────────

def download_pdf(ticker: str, year: int, url: str) -> bool:
    """Download one PDF. Returns True on success."""
    dest = PDF_DIR / f"{ticker}_{year}.pdf"
    if dest.exists() and dest.stat().st_size > 10_000:
        print(f"    ✓ {dest.name} already exists ({dest.stat().st_size // 1024}KB)")
        return True

    print(f"    ⬇ {ticker}_{year}.pdf ... ", end="", flush=True)
    try:
        resp = requests.get(url, timeout=120, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()
        if b"%PDF" not in resp.content[:8]:
            print(f"❌ not a PDF")
            return False
        dest.write_bytes(resp.content)
        print(f"✅ {len(resp.content) // 1024}KB")
        return True
    except Exception as e:
        print(f"❌ {e}")
        return False


def download_all(url_cache: dict, dry_run: bool = False) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    total = found = downloaded = skipped = failed = 0

    for ticker in TICKERS:
        print(f"\n{ticker}:")
        urls = url_cache.get(ticker, {})
        for year in YEARS:
            total += 1
            url = urls.get(str(year))
            if not url:
                dest = PDF_DIR / f"{ticker}_{year}.pdf"
                if dest.exists() and dest.stat().st_size > 10_000:
                    print(f"    ✓ {dest.name} already exists (manual)")
                    found += 1
                else:
                    print(f"    ❌ {ticker}_{year}.pdf — no URL found (manual download needed)")
                    failed += 1
                continue

            found += 1
            if dry_run:
                print(f"    📎 {ticker}_{year}.pdf → {url[:70]}...")
                skipped += 1
            else:
                ok = download_pdf(ticker, year, url)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
            time.sleep(0.3)  # brief pause between downloads

    print(f"\n{'=' * 60}")
    print(f"Total: {total} | Discoverable: {found} | ", end="")
    if dry_run:
        print(f"Dry run (not downloaded): {skipped}")
    else:
        print(f"Downloaded: {downloaded} | Failed: {failed}")

    if failed > 0:
        print(f"\n⚠ {failed} PDFs could not be auto-downloaded.")
        print("  For these, download manually and place in data/pdfs/ as {TICKER}_{YEAR}.pdf")
        print("  The Screener.in financial data fallback will cover them in the pipeline.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("FinAgent — Annual Report Batch Downloader")
    print("=" * 60)
    print(f"\nStep 1: Discovering PDF URLs (with rate limiting)...")
    url_cache = discover_all_urls(YEARS)

    total_found = sum(len(v) for v in url_cache.values())
    print(f"\nDiscovered {total_found} URLs across {len(url_cache)} companies")

    print(f"\nStep 2: {'Dry run — showing URLs' if dry_run else 'Downloading PDFs'}...")
    download_all(url_cache, dry_run=dry_run)
