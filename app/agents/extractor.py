import json
from pathlib import Path
from app.claude_client import call_claude, load_skill
from app.agents.rag_processor import query_chunks
from app.agents.forecaster import _extract_json

RESPONSES_DIR = Path("data/responses")
SKILL_PATH = Path("skills/extraction_prompt.md")


def extract_financials(ticker: str, year: int) -> dict:
    """Extract Revenue, NI, EPS from annual report via RAG + Claude. Cached."""
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    cache = RESPONSES_DIR / f"{ticker}_{year}_extract.json"
    if cache.exists():
        return json.loads(cache.read_text())

    chunks = query_chunks(ticker, year,
        "revenues net profit attributable to owners earnings per share "
        "consolidated statement of profit and loss", n=10)
    context = "\n\n---\n\n".join(chunks)

    skill = load_skill(SKILL_PATH)
    prompt = f"{skill}\n\n=== ANNUAL REPORT TEXT ===\n{context}"

    raw = call_claude(prompt, ticker=ticker, year=year, agent="extractor", max_tokens=2048)
    result = _extract_json(raw)
    cache.write_text(json.dumps(result, indent=2))
    return result
