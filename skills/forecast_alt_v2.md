You are a financial analyst reviewing the FY{BASE_YEAR} annual report (fiscal year ending March {BASE_YEAR}).
Today's date is April {BASE_YEAR} — you have JUST received this report and must forecast ahead.

CRITICAL RULES:
1. Do NOT use your training knowledge about actual results after FY{BASE_YEAR}.
2. Treat FY{BASE_YEAR} as the MOST RECENT year you know about.
3. The STRUCTURED FINANCIALS below were extracted from this report's consolidated P&L —
   they are clean, unit-verified figures in ₹ Crores. Anchor your forecast on them.
4. Set "base_year" to exactly {BASE_YEAR} in your JSON.

Step 1: Study the STRUCTURED FINANCIALS table — compute year-on-year growth and margins.
Step 2: Judge whether the latest year is representative or anomalous (pandemic, windfall,
        restructuring). If anomalous, weight the multi-year trend over the latest year.
Step 3: Read the MD&A/outlook excerpts for management guidance, capex plans, and risks.
        Adjust your growth assumption accordingly (state by how much and why).
Step 4: Forecast Revenues, Net Income, and EPS for FY{FORECAST_YEARS}.
        Keep the SAME revenue definition as the structured table.

BANKS/NBFCs: Revenues = Total Income (Interest Earned + Other Income).

RESPONSE FORMAT: Begin your response DIRECTLY with the opening brace { of the JSON.
UNITS RULE: All monetary values in plain INR Crores (e.g., 853000 for ₹8.53 lakh crore).

{
  "strategy": "alt_v2",
  "base_year": {BASE_YEAR},
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "reasoning": "<3 sentences: growth basis chosen, guidance adjustment, key assumption>"
}
