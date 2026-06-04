"""
Run this to see which PDFs are present and which still need downloading.
Usage: python check_pdfs.py
"""
from pathlib import Path

TICKERS = [
    # Large-cap
    "RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK",
    "SBIN", "ITC", "LT", "NTPC", "ONGC",
    # Mid-cap
    "REC", "PFC", "HUDCO", "IREDA", "IFCI",
    # Small-cap
    "KEC", "TEXRAIL", "POWERMECH", "VINDHYATEL", "SKIPPER",
]

PRIORITY_YEARS = [2021, 2022, 2023, 2024, 2025]   # all needed; 2025=FY2024-25
OPTIONAL_YEARS = []   # all years are now priority

pdf_dir = Path("data/pdfs")
pdf_dir.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PDF STATUS REPORT")
print("=" * 60)

missing_priority = []
present = []

for ticker in TICKERS:
    row = f"{ticker:12s} "
    for year in PRIORITY_YEARS + OPTIONAL_YEARS:
        path = pdf_dir / f"{ticker}_{year}.pdf"
        if path.exists():
            size_mb = path.stat().st_size / 1_048_576
            row += f"  {year}:✅({size_mb:.1f}MB)"
            present.append(f"{ticker}_{year}")
        else:
            row += f"  {year}:❌"
            if year in PRIORITY_YEARS:
                missing_priority.append(f"{ticker}_{year}.pdf")
    print(row)

print()
print(f"Present: {len(present)} PDFs")
print(f"Missing (priority): {len(missing_priority)}")
if missing_priority:
    print("\nNeeded (drop in data/pdfs/):")
    for f in missing_priority:
        print(f"  {f}")
else:
    print("\n✅ All priority PDFs present — ready to run!")
