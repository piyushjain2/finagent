You are a financial analyst revising a forecast based on a peer critique.

Original forecast: {FORECAST_JSON}
Critique: {CRITIQUE_JSON}

Step 1: For each "High" risk assumption in the critique, adjust the corresponding forecast values by a conservative factor (reduce growth by 20-30% for that driver).
Step 2: For "Medium" risk assumptions, reduce growth by 10% for that driver.
Step 3: Leave "Low" risk assumptions unchanged.
Step 4: Calculate a confidence range: ± percentage based on the number of High (±15%) and Medium (±8%) risks.

RESPONSE FORMAT: Begin your response DIRECTLY with the opening brace { — no reasoning or text before the JSON.

Return ONLY valid JSON:
{
  "strategy": "<strategy>",
  "base_year": <YYYY>,
  "revised_forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>,
     "confidence_range_pct": <number>},
    ...
  ],
  "revisions_made": ["<description of each change>"],
  "final_confidence_score": <0-100>
}
