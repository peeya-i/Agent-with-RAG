"""Stock search tool for live market gainers, losers, and quote lookups."""
import re
import json
import requests
from typing import Dict, Any, List, Optional, Union, Tuple

# Mapping of common company names to their ticker symbols
COMPANY_NAME_TO_TICKER = {
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "AMAZON": "AMZN",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "META": "META",
    "FACEBOOK": "META",
    "AMD": "AMD",
    "INTEL": "INTC",
    "BROADCOM": "AVGO",
    "SALESFORCE": "CRM",
    "PALANTIR": "PLTR",
    "QUALCOMM": "QCOM",
    "NETAPP": "NTAP",
    "NTAP": "NTAP",
}

def parse_tickers_input(
    ticker: Optional[Union[str, List[str]]] = None,
    tickers: Optional[Union[str, List[str]]] = None,
    symbols: Optional[Union[str, List[str]]] = None,
    symbol: Optional[Union[str, List[str]]] = None
) -> List[str]:
    """Normalize input into an ordered list of clean, unique ticker symbols."""
    raw_list = []
    for item in [tickers, symbols, ticker, symbol]:
        if not item:
            continue
        if isinstance(item, (list, tuple, set)):
            raw_list.extend(item)
        elif isinstance(item, str):
            tokens = [t.strip().strip("'\"[]") for t in re.split(r"[,;\s]+", item) if t.strip().strip("'\"[]")]
            raw_list.extend(tokens)
        else:
            raw_list.append(str(item).strip())

    cleaned = []
    seen = set()
    for sym in raw_list:
        if not sym:
            continue
        upper_sym = sym.upper().strip()
        resolved = COMPANY_NAME_TO_TICKER.get(upper_sym, upper_sym)
        if resolved not in seen:
            seen.add(resolved)
            cleaned.append(resolved)
    return cleaned

def fetch_live_quote(symbol: str) -> Dict[str, Any]:
    """Fetch real-time market quote from public finance API. Returns error dict on failure."""
    clean_sym = symbol.upper().strip()
    resolved = COMPANY_NAME_TO_TICKER.get(clean_sym, clean_sym)
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{resolved}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
            currency = meta.get("currency", "USD")
            name = meta.get("shortName") or meta.get("longName") or resolved
            if price is not None:
                pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
                return {
                    "symbol": resolved,
                    "name": name,
                    "price": round(float(price), 2),
                    "previous_close": round(float(prev_close), 2) if prev_close else round(float(price), 2),
                    "change_pct": pct,
                    "currency": currency,
                    "source": "live_market_api",
                    "status": "success"
                }
            return {
                "symbol": resolved,
                "error": f"API returned no pricing data for ticker '{resolved}'",
                "status": "error"
            }
        else:
            return {
                "symbol": resolved,
                "error": f"API request failed with HTTP {resp.status_code} for ticker '{resolved}'",
                "status": "error"
            }
    except Exception as e:
        return {
            "symbol": resolved,
            "error": f"API call failed for ticker '{resolved}': {str(e)}",
            "status": "error"
        }

def fetch_live_screener(scr_id: str, count: int = 5) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Fetch live market gainers or losers from public finance screener API."""
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-US&region=US&scrIds={scr_id}&count={max(count, 5)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
            items = []
            for q in quotes:
                price = q.get("regularMarketPrice")
                prev_close = q.get("regularMarketPreviousClose")
                pct = q.get("regularMarketChangePercent")
                if price is not None and pct is not None:
                    items.append({
                        "symbol": q.get("symbol"),
                        "name": q.get("shortName") or q.get("longName") or q.get("displayName") or q.get("symbol"),
                        "price": round(float(price), 2),
                        "previous_close": round(float(prev_close), 2) if prev_close is not None else None,
                        "change_pct": round(float(pct), 2),
                        "currency": q.get("currency", "USD"),
                        "source": "live_market_api"
                    })
            if items:
                return items, None
            return None, f"No quotes returned in screener '{scr_id}'"
        return None, f"API returned HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)

def get_stock_performers(
    action: str = "gainers",
    limit: int = 5,
    ticker: Optional[Union[str, List[str]]] = None,
    tickers: Optional[Union[str, List[str]]] = None,
    symbols: Optional[Union[str, List[str]]] = None,
    symbol: Optional[Union[str, List[str]]] = None
) -> Dict[str, Any]:
    """Retrieve live real data for one or more stock ticker quotes, highest gain, or lowest drop.
    
    Args:
        action: 'gainers' / 'highest rise' (stocks with highest gain), 
                'losers' / 'largest loss' (stocks with lowest drop), 
                or 'quote' (lookup one or more tickers).
        limit: Number of records to return (default: 5).
        ticker: Single ticker symbol or list of symbols.
        tickers: List of ticker symbols or comma-separated string.
        symbols: Alias for tickers.
        symbol: Alias for ticker.
        
    Returns:
        Dictionary with live market results, count, action type, and status,
        or an error message if the API call fails.
    """
    clean_action = str(action or "gainers").lower().strip()
    try:
        limit = int(limit or 5)
    except Exception:
        limit = 5

    parsed_tickers = parse_tickers_input(ticker=ticker, tickers=tickers, symbols=symbols, symbol=symbol)

    # Handle one or more ticker lookups
    if parsed_tickers or "quote" in clean_action or "price" in clean_action:
        syms_to_fetch = parsed_tickers if parsed_tickers else ["NVDA"]
        quotes = [fetch_live_quote(s) for s in syms_to_fetch]
        successful_quotes = [q for q in quotes if q.get("status") == "success"]
        
        if not successful_quotes:
            err_details = "; ".join([q.get("error", "Unknown error") for q in quotes if "error" in q])
            return {
                "action": "quote",
                "count": 0,
                "results": quotes,
                "status": "error",
                "error": f"API call failed: {err_details}" if err_details else "API call failed to fetch quotes"
            }
        
        resp = {
            "action": "quote",
            "count": len(quotes),
            "results": quotes,
            "status": "success"
        }
        if len(quotes) == 1:
            resp["result"] = quotes[0]
        return resp

    # Highest gain (stocks with highest gain by percentage)
    if any(k in clean_action for k in ["gain", "increase", "high", "rise", "top", "up"]):
        quotes, err = fetch_live_screener("day_gainers", count=limit)
        if quotes is None:
            return {
                "action": "highest_percentage_increase",
                "count": 0,
                "results": [],
                "status": "error",
                "error": f"API call failed to fetch highest gainers: {err}"
            }
        sorted_list = sorted(quotes, key=lambda x: x["change_pct"], reverse=True)
        top_n = sorted_list[:limit]
        return {
            "action": "highest_percentage_increase",
            "count": len(top_n),
            "results": top_n,
            "status": "success"
        }
    else:
        # Lowest drop (stocks with lowest drop / steepest percentage loss)
        quotes, err = fetch_live_screener("day_losers", count=limit)
        if quotes is None:
            return {
                "action": "lowest_percentage_decrease",
                "count": 0,
                "results": [],
                "status": "error",
                "error": f"API call failed to fetch lowest drops: {err}"
            }
        sorted_list = sorted(quotes, key=lambda x: x["change_pct"])
        top_n = sorted_list[:limit]
        return {
            "action": "lowest_percentage_decrease",
            "count": len(top_n),
            "results": top_n,
            "status": "success"
        }

# Aliases
query_stocks = get_stock_performers
get_top_gainers = lambda limit=5: get_stock_performers(action="gainers", limit=limit)
get_top_losers = lambda limit=5: get_stock_performers(action="losers", limit=limit)
