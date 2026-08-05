import pytest
from unittest.mock import patch
from symbol_resolver import resolve_symbol, resolve_symbols, normalize_query, ResolutionResult

def test_normalize_query():
    assert normalize_query("   APPLE   INC  ") == "APPLE INC"
    assert normalize_query("") == ""

def test_exact_dictionary_match():
    res = resolve_symbol("APPLE")
    assert res.resolved == "AAPL"
    assert res.method == "dictionary"

def test_fuzzy_match():
    # "BRITANIA" should fuzzy match to "BRITANNIA"
    res = resolve_symbol("BRITANIA")
    assert res.resolved == "BRITANNIA.NS"
    assert res.method == "fuzzy"

def test_empty_string():
    res = resolve_symbol("   ")
    assert res.resolved is None
    assert res.method == "empty"

@patch('symbol_resolver._search_yahoo')
def test_yahoo_search_fallback(mock_search_yahoo):
    mock_search_yahoo.return_value = "UNKNOWN.NS"
    res = resolve_symbol("UNKNOWN_COMPANY")
    
    assert res.resolved == "UNKNOWN.NS"
    assert res.method == "yahoo_search"
    mock_search_yahoo.assert_called_once_with("UNKNOWN_COMPANY")

@patch('symbol_resolver._search_yahoo')
def test_unresolved_symbol(mock_search_yahoo):
    mock_search_yahoo.return_value = None
    res = resolve_symbol("TOTALLY_UNKNOWN_123")
    
    assert res.resolved is None
    assert res.method == "unresolved"

def test_resolve_symbols_multiple():
    resolved_list, results = resolve_symbols(["APPLE", "MSFT", "  "])
    
    assert len(resolved_list) == 2
    assert "AAPL" in resolved_list
    assert "MSFT" in resolved_list
    
    assert len(results) == 3
    assert results[0].resolved == "AAPL"
    assert results[1].resolved == "MSFT"
    assert results[2].resolved is None
