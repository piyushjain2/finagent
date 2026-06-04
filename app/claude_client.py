import os
import json
from datetime import datetime, timezone
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
PROMPTS_DIR = Path("data/prompts")

# Cost strategy: Sonnet runs the forecasting EXPERIMENT (the subject of the study);
# Haiku handles mechanical data plumbing (extraction) at ~1/3 the price.
MODEL = "claude-sonnet-4-6"          # forecasting, critique, revise, stock prediction, commentary
HAIKU_MODEL = "claude-haiku-4-5"     # extraction (mechanical table-reading)


def call_claude(
    prompt: str,
    ticker: str,
    year: int,
    agent: str,
    system: str | None = None,
    max_tokens: int = 4096,
    model: str | None = None,
) -> str:
    """Call Claude API and log the interaction to the Prompt Vault.

    Args:
        prompt: The user prompt to send to Claude
        ticker: Stock ticker symbol for logging
        year: Year for logging context
        agent: Agent name for logging
        system: Optional system message
        max_tokens: Maximum tokens in response
        model: Override model (default: Sonnet). Use HAIKU_MODEL for mechanical tasks.

    Returns:
        The text response from Claude
    """
    use_model = model or MODEL
    kwargs: dict = {
        "model": use_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = _client.messages.create(**kwargs)
    text = response.content[0].text

    # Log to Prompt Vault
    log_dir = PROMPTS_DIR / ticker
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir.parent / f"{ticker}_{year}_{agent}.jsonl"
    with open(log_file, "a") as f:
        f.write(
            json.dumps(
                {
                    "ticker": ticker,
                    "year": year,
                    "agent": agent,
                    "model": use_model,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "response": text,
                }
            )
            + "\n"
        )
    return text


def load_skill(path: Path | str) -> str:
    """Load a skill file (typically a .md file).

    Args:
        path: Path to the skill file

    Returns:
        The content of the skill file
    """
    return Path(path).read_text()
