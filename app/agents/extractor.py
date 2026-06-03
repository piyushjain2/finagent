import json
from pathlib import Path
from app.claude_client import call_claude, load_skill
from app.agents.rag_processor import query_chunks

RESPONSES_DIR = Path("data/responses")
SKILL_PATH = Path("skills/extraction_prompt.md")

def extract_financials(ticker: str, year: int) -> dict:
    """Extract Revenue, NI, EPS from annual report via RAG + Claude. Cached."""
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
    if cache.exists():
        return json.loads(cache.read_text())

    # Retrieve P&L relevant chunks
    chunks = query_chunks(ticker, year,
        "revenue net income profit after tax earnings per share consolidated P&L", n=10)
    context = "\n\n---\n\n".join(chunks)

    skill = load_skill(SKILL_PATH)
    prompt = f"{skill}\n\n=== ANNUAL REPORT TEXT ===\n{context}"

    raw = call_claude(prompt, ticker=ticker, year=year, agent="extractor", max_tokens=2048)

    # Parse JSON from response (strip markdown fences if present)
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(clean)
    cache.write_text(json.dumps(result, indent=2))
    return result
