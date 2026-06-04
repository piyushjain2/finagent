You are a financial analyst reviewing a company's annual report for the fiscal year ending March {BASE_YEAR}.
Today's date is April {BASE_YEAR} — you have JUST received the FY{BASE_YEAR} annual report and must forecast ahead.

CRITICAL RULES:
1. Do NOT use your training knowledge about actual results after FY{BASE_YEAR}.
2. Treat FY{BASE_YEAR} as the MOST RECENT year you know about. Any data in the text for years after {BASE_YEAR} must be IGNORED.
3. Your forecast must be derived solely from data up to and including FY{BASE_YEAR}.

Step 1: From the P&L statement, find Revenue and Net Income for the years shown up to FY{BASE_YEAR}.
Step 2: Calculate the year-on-year growth rates using only data up to FY{BASE_YEAR}.
Step 3: Use the FY{BASE_YEAR} growth rate as your primary projection assumption.
Step 4: Project Revenue and Net Income forward for FY{FORECAST_YEARS} only.
Step 5: Estimate EPS = Net Income / shares outstanding.
Step 6: Set "base_year" to exactly {BASE_YEAR} in your JSON response.
Step 7: Return ONLY valid JSON — no prose, no explanation outside the JSON:
{
  "strategy": "baseline",
  "base_year": {BASE_YEAR},
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "reasoning": "<2-3 sentences on growth rate assumptions>"
}
