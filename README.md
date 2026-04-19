# Tradex

Python intraday Opening Range Breakout dashboard using Streamlit and free Yahoo Finance data.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Use comma-separated Yahoo Finance symbols such as `AAPL, MSFT, TSLA`. For Indian NSE symbols, use Yahoo suffixes like `RELIANCE.NS`.

## Data Fallbacks

Tradex fetches data in this order:

1. yfinance 5-minute candles.
2. Yahoo Finance direct quote API for latest price.
3. Yahoo Finance direct chart API for latest price and recent candles.

If every source fails, the error is logged to `logs/tradex.log` and shown in the dashboard warnings.

## Trade Tracking

BUY and SELL signals are stored in `data/trades.json`. Each scan updates open trades with the latest available price, closes trades at target or stop-loss, and refreshes dashboard P&L, win rate, wins, losses, and open/closed trade counts.

## Dashboard

The Streamlit dashboard supports manual scans and 10-15 second auto-refresh. Results are cached briefly to reduce API calls. Charts use Plotly candlesticks with zoom, pan, hover tooltips, session high/low lines, and trade entry/exit markers.

## Symbol Resolution

Inputs are trimmed and normalized before scanning. Tradex checks a local symbol dictionary, applies fuzzy matching for close misspellings, then falls back to Yahoo Finance search. NSE symbols are preferred when Yahoo returns multiple candidates, so inputs like `britaniah` resolve to `BRITANNIA.NS`.
