from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
import logging
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
FUZZY_CUTOFF = 0.72


SYMBOL_DICTIONARY = {
    "AAPL": "AAPL",
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "MSFT": "MSFT",
    "MICROSOFT": "MSFT",
    "MICROSOFT CORP": "MSFT",
    "TSLA": "TSLA",
    "TESLA": "TSLA",
    "AMZN": "AMZN",
    "AMAZON": "AMZN",
    "GOOG": "GOOG",
    "GOOGL": "GOOGL",
    "ALPHABET": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "NVDA": "NVDA",
    "NVIDIA": "NVDA",
    "NFLX": "NFLX",
    "NETFLIX": "NFLX",
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY SERVICES": "TCS.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "SBI": "SBIN.NS",
    "STATE BANK OF INDIA": "SBIN.NS",
    "ITC": "ITC.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "BHARTI AIRTEL": "BHARTIARTL.NS",
    "AIRTEL": "BHARTIARTL.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "HINDUSTAN UNILEVER": "HINDUNILVR.NS",
    "LT": "LT.NS",
    "LARSEN TOUBRO": "LT.NS",
    "BRITANNIA": "BRITANNIA.NS",
    "BRITANNIA INDUSTRIES": "BRITANNIA.NS",
    "BRITANIA": "BRITANNIA.NS",
    "BRITANIAH": "BRITANNIA.NS",
}


@dataclass(frozen=True)
class ResolutionResult:
    original: str
    normalized: str
    resolved: Optional[str]
    method: str
    message: str


def normalize_query(value: str) -> str:
    return " ".join(value.strip().upper().split())


def resolve_symbols(raw_symbols: list[str]) -> tuple[list[str], list[ResolutionResult]]:
    resolved_symbols: list[str] = []
    results: list[ResolutionResult] = []

    for raw_symbol in raw_symbols:
        result = resolve_symbol(raw_symbol)
        results.append(result)
        if result.resolved and result.resolved not in resolved_symbols:
            resolved_symbols.append(result.resolved)

    return resolved_symbols, results


def resolve_symbol(raw_symbol: str) -> ResolutionResult:
    normalized = normalize_query(raw_symbol)
    if not normalized:
        return ResolutionResult(raw_symbol, normalized, None, "empty", "No matching stock found")

    dictionary_match = SYMBOL_DICTIONARY.get(normalized)
    if dictionary_match:
        return _resolved(raw_symbol, normalized, dictionary_match, "dictionary")

    if normalized in SYMBOL_DICTIONARY.values():
        return _resolved(raw_symbol, normalized, normalized, "dictionary")

    fuzzy_match = difflib.get_close_matches(normalized, SYMBOL_DICTIONARY.keys(), n=1, cutoff=FUZZY_CUTOFF)
    if fuzzy_match:
        return _resolved(raw_symbol, normalized, SYMBOL_DICTIONARY[fuzzy_match[0]], "fuzzy")

    yahoo_match = _search_yahoo(normalized)
    if yahoo_match:
        return _resolved(raw_symbol, normalized, yahoo_match, "yahoo_search")

    logging.warning("No matching stock found for %s", raw_symbol)
    return ResolutionResult(raw_symbol, normalized, None, "unresolved", "No matching stock found")


def _search_yahoo(query: str) -> Optional[str]:
    params = urlencode({"q": query, "quotesCount": 10, "newsCount": 0})
    request = Request(
        f"{SEARCH_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 Tradex/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logging.warning("Yahoo search failed for %s: %s", query, exc)
        return None

    quotes = payload.get("quotes") or []
    equity_quotes = [
        quote for quote in quotes if quote.get("symbol") and quote.get("quoteType") in {None, "EQUITY", "ETF"}
    ]
    if not equity_quotes:
        return None

    nse_match = next((quote["symbol"] for quote in equity_quotes if quote["symbol"].upper().endswith(".NS")), None)
    if nse_match:
        return nse_match.upper()

    return str(equity_quotes[0]["symbol"]).upper()


def _resolved(raw_symbol: str, normalized: str, resolved: str, method: str) -> ResolutionResult:
    display = raw_symbol.strip()
    message = f"Resolved '{display}' -> {resolved}"
    return ResolutionResult(raw_symbol, normalized, resolved, method, message)
