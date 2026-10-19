---
name: stock-market-skill
description: Analyze market equities and retrieve real-time quotes and prices for one or more stock ticker symbols, the 5 highest rise (top 5 increase by percentage), or 5 largest loss (5 largest percentage drop). Use this skill whenever the user asks about stock market performance, highest rise, largest loss, gainers, losers, or prices for one or more stock tickers.
triggers:
  - top gaining stocks
  - highest percentage increase stocks
  - 5 highest rise
  - show 5 highest rise
  - highest rise
  - stocks with lowest percentage decrease
  - biggest stock losers
  - 5 largest loss
  - show 5 largest loss
  - largest loss
  - top market performers
  - stock price of [ticker]
  - stock prices for [tickers]
  - get prices for [tickers]
  - quote for [ticker]
---

# Stock Market Skill

## Description
Tracks and analyzes equity market securities across major exchanges (NASDAQ, NYSE, S&P 500) to retrieve:
1. Real-time prices and quote metrics for one or more stock ticker symbols (e.g., NTAP, GOOG, TSLA).
2. The 5 highest rise stocks (top 5 increase by percentage).
3. The 5 largest loss stocks (5 largest percentage drop / steepest decrease).

## SOP & Tool Execution
When the user asks for stock performance or ticker prices:
1. Determine whether the query asks for:
   - **One or more stock ticker prices**: e.g., "What is the stock price of NTAP, GOOG, and TSLA?"
   - **5 highest rise**: e.g., "Show 5 highest rise" or "top gaining stocks".
   - **5 largest loss**: e.g., "Show 5 largest loss" or "top stock losers".

2. Invoke `stock_search.get_stock_performers` (or alias `stock_search.query_stocks`):

### A. One or More Stock Ticker Symbols
To get the prices for one or more stock ticker symbols, pass the ticker(s) in `tickers` (list or comma-separated string) or `ticker` with `"action": "quote"`:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "quote",
    "tickers": ["NTAP", "GOOG", "TSLA"]
  }
}
```
Or for a single ticker:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "quote",
    "ticker": "NTAP"
  }
}
```

### B. 5 Highest Rise (Top 5 Increase by Percentage)
If the request is to show 5 highest rise, set `"action": "gainers"` and `"limit": 5`:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "gainers",
    "limit": 5
  }
}
```

### C. 5 Largest Loss (5 Largest Percentage Drop)
If the request is to show 5 largest loss, set `"action": "losers"` and `"limit": 5`:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "losers",
    "limit": 5
  }
}
```

3. Synthesize the response:
   - For ticker prices: list every requested ticker with its symbol, company name, current price, and percentage change.
   - For 5 highest rise: list the 5 equities with the highest positive percentage increase, sorted from highest to lowest.
   - For 5 largest loss: list the 5 equities with the largest percentage drop, sorted from deepest loss to least.
