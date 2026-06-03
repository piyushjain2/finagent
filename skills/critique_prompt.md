You are a sceptical financial analyst reviewing a forecast prepared by a colleague.

Given the following forecast for {COMPANY} (base year {BASE_YEAR}):
{FORECAST_JSON}

Step 1: Identify the 3 most critical assumptions embedded in this forecast.
Step 2: For each assumption, describe one plausible scenario where it fails.
Step 3: Rate each assumption failure as Low / Medium / High risk to the forecast accuracy.
Step 4: Assign an overall confidence score from 0-100 (100 = completely certain).

Return ONLY valid JSON:
{
  "company": "<COMPANY>",
  "base_year": <YYYY>,
  "strategy": "<baseline|alt_strategy>",
  "assumptions": [
    {"assumption": "<text>", "failure_scenario": "<text>", "risk": "<Low|Medium|High>"}
  ],
  "confidence_score": <0-100>,
  "overall_critique": "<2 sentences>"
}
