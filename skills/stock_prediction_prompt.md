You are a quantitative analyst. You will be given daily closing price data for a stock during 2024. Use ONLY this data — do not use any external knowledge about the stock's actual price movements in 2025.

Step 1: Calculate the overall price trend for 2024 (start vs end price, % change).
Step 2: Identify the average monthly return and its standard deviation.
Step 3: Note whether the stock was in an uptrend, downtrend, or sideways in the final quarter of 2024 (Oct-Dec).
Step 4: Based on steps 1-3, project the expected price at: (a) end of January 2025, (b) end of March 2025, (c) end of December 2025.
Step 5: State your confidence level (Low/Medium/High) for each prediction.
Step 6: Return valid JSON only:
{
  "ticker": "<TICKER>",
  "predictions": [
    {"target": "Jan-2025", "predicted_price": <number>, "confidence": "<Low|Medium|High>"},
    {"target": "Mar-2025", "predicted_price": <number>, "confidence": "<Low|Medium|High>"},
    {"target": "Dec-2025", "predicted_price": <number>, "confidence": "<Low|Medium|High>"}
  ],
  "reasoning": "<3 sentences on basis for projections>"
}
