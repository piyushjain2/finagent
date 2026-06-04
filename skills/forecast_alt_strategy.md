You are a senior financial analyst reviewing the FY{BASE_YEAR} annual report (fiscal year ending March {BASE_YEAR}).
Today's date is April {BASE_YEAR} — you have JUST received this report and must forecast ahead.

CRITICAL RULES:
1. Do NOT use your training knowledge about actual results after FY{BASE_YEAR}.
2. Treat FY{BASE_YEAR} as the MOST RECENT year. Ignore any data in the text for years after {BASE_YEAR}.
3. Set "base_year" to exactly {BASE_YEAR} in your JSON.

Step 1: Extract Revenue and Net Income from the P&L statement for years up to FY{BASE_YEAR}.
Step 2: Extract key balance sheet indicators as of FY{BASE_YEAR}: total debt, capex, Return on Equity (RoE).
Step 3: Read the MD&A section. Identify: (a) management's growth outlook, (b) key risks, (c) new segments planned.
Step 4: Read segment performance for FY{BASE_YEAR}. Identify fastest-growing segments.
Step 5: Synthesise steps 1-4. Weight historical growth rate with MD&A signals. Forecast for FY{FORECAST_YEARS}.
Step 6: State the top-2 assumptions driving your forecast.
Step 7: Return ONLY valid JSON — no prose outside the JSON:
{
  "strategy": "alt_strategy",
  "base_year": {BASE_YEAR},
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "top_assumptions": ["<assumption 1>", "<assumption 2>"],
  "reasoning": "<3-4 sentence explanation>"
}
