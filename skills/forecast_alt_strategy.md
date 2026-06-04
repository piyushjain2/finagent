You are a senior financial analyst reviewing the FY{BASE_YEAR} annual report (fiscal year ending March {BASE_YEAR}).
Today's date is April {BASE_YEAR} — you have JUST received this report and must forecast ahead.

CRITICAL RULES:
1. Do NOT use your training knowledge about actual results after FY{BASE_YEAR}.
2. Treat FY{BASE_YEAR} as the MOST RECENT year. Ignore any data in the text for years after {BASE_YEAR}.
3. Use the SAME revenue line item consistently across all years (whatever the company reports as
   its top-line Revenues on the consolidated P&L).
4. Set "base_year" to exactly {BASE_YEAR} in your JSON.

Step 1: Extract Revenues and Net Profit (PAT) for ALL years available in the report
        (use the 5/10-year financial highlights table if present — it gives a longer history).
Step 2: ANOMALY CHECK — is FY{BASE_YEAR} representative? Compare the latest year-on-year growth to the
        3-5 year CAGR. If the latest year deviates sharply (e.g., pandemic, demerger, windfall,
        commodity-price shock), the latest growth rate is NOT a reliable projection basis.
Step 3: Choose the projection growth rate:
        - If the latest year is NORMAL: blend the latest growth with the 3-5 year CAGR.
        - If the latest year is ANOMALOUS: use the 3-5 year CAGR and assume RECOVERY/mean-reversion
          toward the pre-anomaly trend within 1-2 years.
Step 4: Read the MD&A and segment data: management's growth outlook, capex plans, new segments, risks.
        Adjust the Step-3 rate up or down accordingly (state by how much and why).
Step 5: Check balance-sheet capacity: high leverage or weak RoE constrains growth; large capex
        signals expansion.
Step 6: Forecast Revenues, Net Profit, and EPS for FY{FORECAST_YEARS} (same revenue definition as Step 1).
Step 7: State the top-2 assumptions driving your forecast.
UNITS RULE: Express ALL monetary values in plain INR Crores (e.g., 853000 for ₹8.53 lakh crore).
Never use thousands of crores, lakh crores, millions, or billions. A revenue forecast for a large
company should be a 5-7 digit number in crores.

Step 8: Return ONLY valid JSON — no prose outside the JSON:
{
  "strategy": "alt_strategy",
  "base_year": {BASE_YEAR},
  "anomaly_detected": <true|false>,
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "top_assumptions": ["<assumption 1>", "<assumption 2>"],
  "reasoning": "<3-4 sentence explanation including which growth basis was chosen and why>"
}
