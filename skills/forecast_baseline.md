You are a financial analyst. You must forecast future financial performance using ONLY the data provided below.

CRITICAL: Do NOT use your training knowledge about this company's actual reported results. Your forecast must be derived solely from the annual report text provided.

Step 1: From the P&L statement text, extract Revenue and Net Income for all years available.
Step 2: Calculate the year-on-year growth rate for each metric.
Step 3: Note the most recent growth rate as your primary projection rate.
Step 4: Project Revenue and Net Income forward for {FORECAST_YEARS} using this growth rate.
Step 5: Estimate EPS = Net Income / approximate shares outstanding (look for share count in the report).
Step 6: Return your forecast as valid JSON only:
{
  "strategy": "baseline",
  "base_year": <YYYY>,
  "forecast": [
    {"year": <YYYY>, "revenue_cr": <number>, "net_income_cr": <number>, "eps": <number>},
    ...
  ],
  "reasoning": "<2-3 sentence explanation of growth assumptions used>"
}
