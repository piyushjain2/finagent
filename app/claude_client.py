import os
import json
from datetime import datetime, timezone
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
PROMPTS_DIR = Path("data/prompts")
MODEL = "claude-sonnet-4-6"


def call_claude(
    prompt: str,
    ticker: str,
    year: int,
    agent: str,
    system: str | None = None,
    max_tokens: int = 4096,
) -> str:
    """Call Claude API and log the interaction to the Prompt Vault.

    Args:
        prompt: The user prompt to send to Claude
        ticker: Stock ticker symbol for logging
        year: Year for logging context
        agent: Agent name for logging
        system: Optional system message
        max_tokens: Maximum tokens in response

    Returns:
        The text response from Claude
    """
    kwargs: dict = {
        "model": MODEL,
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
                    "model": MODEL,
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
