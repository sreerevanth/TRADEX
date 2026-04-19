from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import time
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf


RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.6


@dataclass(frozen=True)
class FetchResult:
    symbol: str
    data: pd.DataFrame
    latest_price: Optional[float] = None
    timestamp: Optional[str] = None
    source: str = "none"
    error: Optional[str] = None


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def fetch_intraday_data(symbol: str, period: str = "5d", interval: str = "5m") -> FetchResult:
    cleaned = normalize_symbol(symbol)
    if not cleaned:
        return _failed(cleaned, "Empty symbol")

    failures: list[str] = []
    yfinance_attempts = _unique_attempts(
        [
            (period, interval),
            ("5d", "15m"),
            ("5d", "5m"),
        ]
    )

    for attempt_period, attempt_interval in yfinance_attempts:
        frame, error = _download_yfinance(cleaned, attempt_period, attempt_interval)
        if error:
            failures.append(error)
            continue

        prepared = _prepare_price_frame(frame)
        if prepared.empty:
            failures.append(f"yfinance {attempt_interval}/{attempt_period} returned no valid OHLCV rows")
            continue

        latest_session = prepared.index.normalize().max()
        prepared = prepared[prepared.index.normalize() == latest_session]
        if prepared.empty:
            failures.append(f"yfinance {attempt_interval}/{attempt_period} latest session filter produced no rows")
            continue

        warning = None
        if attempt_interval != interval or attempt_period != period:
            warning = f"Primary yfinance {interval}/{period} failed; using yfinance {attempt_interval}/{attempt_period}"
            _log_warning(cleaned, warning)

        return FetchResult(
            symbol=cleaned,
            data=prepared,
            latest_price=latest_price(prepared),
            timestamp=market_timestamp(prepared),
            source=f"yfinance:{attempt_interval}",
            error=warning,
        )

    return _fetch_quote_fallback(cleaned, "; ".join(failures) or "yfinance returned no intraday candles")


def fetch_quote_price(symbol: str, timeout: int = 10) -> FetchResult:
    cleaned = normalize_symbol(symbol)
    if not cleaned:
        return FetchResult(symbol=cleaned, data=pd.DataFrame(), error="Empty symbol")

    params = urlencode({"symbols": cleaned})
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?{params}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Tradex/1.0",
            "Accept": "application/json",
        },
    )

    payload, error = _request_json(request, timeout)
    if error:
        return _failed(cleaned, f"Yahoo quote API failed: {error}", source="yahoo_quote")

    quotes = payload.get("quoteResponse", {}).get("result", [])
    if not quotes:
        return _failed(cleaned, "Yahoo quote API returned no quote result", source="yahoo_quote")

    quote = quotes[0]
    price = quote.get("regularMarketPrice") or quote.get("postMarketPrice") or quote.get("preMarketPrice")
    if price is None:
        return _failed(cleaned, "Yahoo quote API returned no usable price field", source="yahoo_quote")

    timestamp = _quote_timestamp(quote)
    data = pd.DataFrame(
        {
            "Open": [float(price)],
            "High": [float(price)],
            "Low": [float(price)],
            "Close": [float(price)],
            "Volume": [float(quote.get("regularMarketVolume") or 0)],
        },
        index=[pd.to_datetime(timestamp)],
    )

    return FetchResult(
        symbol=cleaned,
        data=data,
        latest_price=float(price),
        timestamp=timestamp,
        source="yahoo_quote",
    )


def fetch_direct_chart_data(symbol: str, range_: str = "5d", interval: str = "5m", timeout: int = 10) -> FetchResult:
    cleaned = normalize_symbol(symbol)
    if not cleaned:
        return FetchResult(symbol=cleaned, data=pd.DataFrame(), error="Empty symbol")

    params = urlencode({"range": range_, "interval": interval})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{cleaned}?{params}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Tradex/1.0",
            "Accept": "application/json",
        },
    )

    payload, error = _request_json(request, timeout)
    if error:
        return _failed(cleaned, f"Yahoo chart API failed: {error}", source="yahoo_chart")

    chart = payload.get("chart", {})
    chart_error = chart.get("error")
    if chart_error:
        return _failed(cleaned, f"Yahoo chart API returned error: {chart_error}", source="yahoo_chart")

    results = chart.get("result") or []
    if not results:
        return _failed(cleaned, "Yahoo chart API returned no chart result", source="yahoo_chart")

    result = results[0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp") or []
    quote_rows = (result.get("indicators", {}).get("quote") or [{}])[0]

    frame = _chart_payload_to_frame(timestamps, quote_rows)
    if not frame.empty:
        latest_session = frame.index.normalize().max()
        frame = frame[frame.index.normalize() == latest_session]

    price = latest_price(frame) if not frame.empty else meta.get("regularMarketPrice")
    if price is None:
        return _failed(cleaned, "Yahoo chart API returned no usable price", source="yahoo_chart")

    timestamp = market_timestamp(frame) if not frame.empty else datetime.now().isoformat(timespec="seconds")
    if frame.empty:
        frame = pd.DataFrame(
            {
                "Open": [float(price)],
                "High": [float(price)],
                "Low": [float(price)],
                "Close": [float(price)],
                "Volume": [0.0],
            },
            index=[pd.to_datetime(timestamp)],
        )

    return FetchResult(
        symbol=cleaned,
        data=frame,
        latest_price=float(price),
        timestamp=timestamp,
        source="yahoo_chart",
    )


def latest_price(data: pd.DataFrame) -> Optional[float]:
    if data.empty or "Close" not in data:
        return None
    value = data["Close"].dropna().iloc[-1]
    return float(value)


def market_timestamp(data: pd.DataFrame) -> str:
    if data.empty:
        return datetime.now().isoformat(timespec="seconds")
    latest = pd.to_datetime(data.index[-1])
    if latest.tzinfo is not None:
        latest = latest.tz_convert(None)
    return latest.isoformat(timespec="seconds")


def _download_yfinance(symbol: str, period: str, interval: str) -> tuple[pd.DataFrame, Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            frame = yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:
            last_error = f"yfinance {interval}/{period} attempt {attempt} failed: {exc}"
            _log_warning(symbol, last_error)
        else:
            if not frame.empty:
                return frame, None
            last_error = f"yfinance {interval}/{period} attempt {attempt} returned no rows"
            _log_warning(symbol, last_error)

        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    return pd.DataFrame(), last_error


def _prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    prepared = _flatten_yfinance_columns(frame)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(column not in prepared.columns for column in required):
        return pd.DataFrame()

    prepared = prepared.dropna(subset=required)
    prepared.index = pd.to_datetime(prepared.index)
    return prepared


def _request_json(request: Request, timeout: int) -> tuple[dict, Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8")), None
        except Exception as exc:
            last_error = f"attempt {attempt}: {exc}"
            logging.warning("Direct Yahoo request failed: %s", last_error)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    return {}, last_error


def _fetch_quote_fallback(symbol: str, yfinance_error: str) -> FetchResult:
    _log_warning(symbol, yfinance_error)
    quote = fetch_quote_price(symbol)
    if not quote.error:
        warning = f"{yfinance_error}; using Yahoo quote API latest price only"
        _log_warning(symbol, warning)
        return FetchResult(
            symbol=symbol,
            data=quote.data,
            latest_price=quote.latest_price,
            timestamp=quote.timestamp,
            source=quote.source,
            error=warning,
        )

    chart = fetch_direct_chart_data(symbol)
    if chart.error:
        return _failed(
            symbol,
            f"{yfinance_error}; quote fallback failed: {quote.error}; chart fallback failed: {chart.error}",
        )

    warning = f"{yfinance_error}; quote fallback failed: {quote.error}; using Yahoo chart API"
    _log_warning(symbol, warning)
    return FetchResult(
        symbol=symbol,
        data=chart.data,
        latest_price=chart.latest_price,
        timestamp=chart.timestamp,
        source=chart.source,
        error=warning,
    )


def _quote_timestamp(quote: dict) -> str:
    raw_timestamp = quote.get("regularMarketTime") or quote.get("postMarketTime") or quote.get("preMarketTime")
    if raw_timestamp:
        return datetime.fromtimestamp(raw_timestamp).isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def _chart_payload_to_frame(timestamps: list[int], quote_rows: dict) -> pd.DataFrame:
    if not timestamps or not quote_rows:
        return pd.DataFrame()

    frame = pd.DataFrame(
        {
            "Open": quote_rows.get("open", []),
            "High": quote_rows.get("high", []),
            "Low": quote_rows.get("low", []),
            "Close": quote_rows.get("close", []),
            "Volume": quote_rows.get("volume", []),
        },
        index=[datetime.fromtimestamp(value) for value in timestamps],
    )
    return frame.dropna(subset=["Open", "High", "Low", "Close"])


def _failed(symbol: str, error: str, source: str = "none") -> FetchResult:
    _log_warning(symbol, error)
    return FetchResult(symbol=symbol, data=pd.DataFrame(), source=source, error=error)


def _log_warning(symbol: str, message: str) -> None:
    logging.warning("%s: %s", symbol, message)


def _unique_attempts(attempts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for attempt in attempts:
        if attempt not in seen:
            seen.add(attempt)
            unique.append(attempt)
    return unique


def _flatten_yfinance_columns(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data.columns, pd.MultiIndex):
        return data

    flattened = data.copy()
    flattened.columns = [
        column[0] if column[0] in {"Open", "High", "Low", "Close", "Adj Close", "Volume"} else column[-1]
        for column in flattened.columns
    ]
    return flattened
