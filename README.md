# finagent: multi-agent financial forecasting from annual reports

A FastAPI app that runs a 9-stage Claude pipeline over 20 NSE-listed companies (10 large, 5 mid, 5 small cap):
it downloads each company's annual-report PDFs, indexes them for retrieval, extracts revenue / net income / EPS,
forecasts three years ahead with two strategies, critiques and revises each forecast, and scores the forecasts
against the actuals that were later reported.

Built in June 2026 for a group assignment in a financial analytics course (Group 11). I wrote the code in this
repository (all commits), using Claude Code as a pair programmer, as the co-author lines show.

## Pipeline

```
PDF fetcher ─► RAG processor ─► Extractor ─► Forecaster (baseline, alt strategy) ─► Critique ─► Revise
 (annual       (chunk, embed,    (Haiku 4.5,    (Sonnet 4.6, prompts in skills/)      (Sonnet 4.6, confidence
  reports)      ChromaDB)         JSON out)                                            ranges)
                                       │
                                       ▼
                           Scale guard (unit-slip tripwire)
                                       │
Market data (actuals, prices) ─► Metrics (forecast error, earnings surprise, trading returns) ─► Commentary ─► Report
```

- `app/orchestrator.py` runs the stages per company, with per-company error isolation.
- `app/hooks.py` is an async event bus; the UI follows each stage over Server-Sent Events, and late or
  reconnecting clients replay the event history.
- `app/claude_client.py` logs every prompt and response (the "prompt vault"), so every number in the report can
  be traced back to the model call that produced it.
- Prompts are versioned files in `skills/`, not strings in code.

## The guardrail that mattered: unit slips

Annual reports mix ₹ million, lakh and crore, and the extraction model occasionally converted a figure by a power
of 10. Forecasts and actuals then sat on different scales and the percentage errors were meaningless (mean
forecast error 182%).

`app/agents/scale_guard.py` uses Screener.in's consolidated P&L only as a magnitude tripwire. The PDF value stays the
source of truth; it is corrected only by an exact power of 10, and only when the corrected value lands within ±45%
of the reference, so genuine forecast error is never altered. Every correction is written to
`data/evals/scale_corrections.csv` for audit. With it, 17 of 20 companies came out clean and the mean error fell
from 182% to 59%. Interpolated references, documented manual overrides and an "n.m." (not meaningful) convention for
off-basis values took the final dataset to a mean error of 28.8% (median 20.3%).

Other fixes that came out of real failures (see the commit history): a strict PDF-only policy for financials
(re-indexing from the real PDF instead of a Screener fallback cut errors from about 60% to 2–21%), a consistent
single revenue line per company (bank-aware), unit sanity checks with automatic retry, tolerant JSON parsing for
concatenated model output, NaN sanitisation, and retries with backoff on downloads.

## Results (20 companies, base years 2021 and 2022)

| | |
|---|---|
| Final forecast error | mean 28.8%, median 20.3% |
| Alternative strategy v2 vs baseline | median error 13.3% vs 19.9% |
| Error by cap size, year 1 | large 20.5%, mid 12.3%, small 27.4% |
| Tests | 37 (pytest) |

Evaluation outputs are in `data/evals/`. Small caps degrade sharply in years 2–3 (55–61% error), and direction
accuracy was 47–53% in every cap band, no better than a coin flip, so it should not be relied on.

## Run it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python run.py                 # http://localhost:8001
python -m pytest              # 37 tests
```

PDFs, vector stores and cached model responses are not committed (`.gitignore`); the first run downloads and
indexes them.
