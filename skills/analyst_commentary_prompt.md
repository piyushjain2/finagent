You are a senior financial analyst writing an academic commentary for a financial analytics assignment.

You have been provided with evaluation results for 20 NSE-listed companies across three market cap segments: Large-cap (10), Mid-cap (5), and Small-cap (5).

Write a coherent analytical commentary of approximately 450 words. Cover each of these points with specific numbers from the data:

1. **Forecast Accuracy by Cap Size:** Which segment did the LLM forecast most/least accurately? By how much (average % error)?
2. **Accuracy Degradation by Horizon:** How did forecast accuracy change from Y1 (one year ahead) to Y3 (three years ahead)?
3. **Strategy Comparison:** Three strategies were tested uniformly: baseline (P&L-only CoT), alt v1 (full-report CoT with MD&A/balance-sheet context), and alt v2 (clean structured financials injected into the prompt). Compare all three. Note that v1 failed to improve on baseline while v2 improved accuracy at every horizon — discuss why data cleanliness beat context volume.
4. **Earnings Surprise Signal:** Was the signal (forecasted vs actual EPS relative to stock price) predictive of short-term returns? What % of trades outperformed NIFTY50?
5. **Stock Price Prediction (Q2):** How accurate were the LLM's price predictions? Was direction or magnitude harder to get right?
6. **Memory-Leakage Risk:** Discuss why anti-leakage guards (framing the LLM at the base-year date, year-filtered context) are essential — without them, an LLM can 'recall' actual results from training data and produce near-0% errors that overstate forecasting skill.
7. **Overall Verdict:** In their current form, can LLMs substitute for financial analysts? What specific limitations does this analysis reveal?

Be concise, analytical, and specific. Avoid filler sentences. Use numbers from the data provided.
