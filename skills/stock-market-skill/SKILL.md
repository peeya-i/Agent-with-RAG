---
name: stock-market-skill
description: Analyze market equities and retrieve the list of stocks with the highest percentage increase (top gainers), lowest percentage decrease / biggest drop (top losers), or detailed quotes for specific tickers. Use this skill whenever the user asks about stock market performance, gainers, losers, ticker prices, or equity percentage changes.
triggers:
  - top gaining stocks
  - highest percentage increase stocks
  - stocks with lowest percentage decrease
  - biggest stock losers
  - top market performers
  - stock price of [ticker]
---

# Stock Market Skill

## Description
Tracks and analyzes equity market securities to identify top gainers (highest percentage increase) and biggest losers (lowest percentage decrease / steepest drops), as well as quote data across major exchanges (NASDAQ, NYSE, S&P 500).

## SOP & Tool Execution
When the user asks for stock gainers, losers, or market performance:
1. Determine whether the query asks for `gainers`, `losers`, or a specific ticker quote.
2. Invoke `stock_search.get_stock_performers`:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "gainers",
    "limit": 5
  }
}
```
Or for losers:
```json
{
  "tool": "stock_search.get_stock_performers",
  "arguments": {
    "action": "losers",
    "limit": 5
  }
}
```
3. Synthesize the ticker symbol, company name, current price, and percentage change.
