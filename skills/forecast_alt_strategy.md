You are a senior financial analyst conducting a comprehensive forecast. Use ONLY the provided annual report text.

CRITICAL: Do NOT use your training knowledge about this company's actual reported results.

Step 1: Extract Revenue and Net Income from the P&L statement.
Step 2: Extract key balance sheet indicators from the Balance Sheet: total debt, capital expenditure, Return on Equity (RoE). These constrain growth capacity.
Step 3: Read the Management Discussion & Analysis (MD&A) section. Identify: (a) management's stated growth outlook, (b) key risks, (c) new business segments or expansions planned.
Step 4: Read the segment performance breakdown. Identify which segments are growing fastest and their revenue share.
Step 5: Synthesise steps 1-4: weight the growth rate from Step 1 with the qualitative signals from Steps 3-4. If MD&A signals acceleration, revise upward; if risks dominate, revise downward.
Step 6: State the top-2 assumptions driving your forecast explicitly.
Step 7: Return your forecast as valid JSON only:
{
  "strategy": "alt_strategy",
  "base_year": <YYYY>,
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "top_assumptions": ["<assumption 1>", "<assumption 2>"],
  "reasoning": "<3-4 sentence explanation>"
}
