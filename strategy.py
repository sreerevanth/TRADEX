from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd


Signal = Literal["BUY", "SELL", "HOLD"]
SMA_WINDOW = 5
BREAKOUT_BUFFER_PERCENT = 0.0005


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    signal: Signal
    entry_price: Optional[float]
    target: Optional[float]
    stop_loss: Optional[float]
    timestamp: str
    last_price: Optional[float]
    opening_range_high: Optional[float]
    opening_range_low: Optional[float]
    volume_confirmed: bool
    reason: str


def calculate_orb_signal(symbol: str, data: pd.DataFrame, timestamp: str) -> TradeSignal:
    if data.empty:
        return _hold(symbol, timestamp, "No data available")

    required = {"High", "Low", "Close", "Volume"}
    missing = required.difference(data.columns)
    if missing:
        return _hold(symbol, timestamp, f"Missing columns: {', '.join(sorted(missing))}")

    clean_data = data.sort_index().dropna(subset=["High", "Low", "Close", "Volume"])
    if len(clean_data) < 2:
        last_price = _safe_last_price(data)
        return _hold(
            symbol,
            timestamp,
            "Latest price available, but need more candles for ORB",
            last_price=last_price,
        )

    opening_range = _opening_range_window(clean_data)
    if opening_range.empty:
        return _hold(symbol, timestamp, "Could not identify opening range", last_price=_safe_last_price(clean_data))

    signal_candle = clean_data.iloc[-1]

    range_high = float(opening_range["High"].max())
    range_low = float(opening_range["Low"].min())
    last_price = float(signal_candle["Close"])

    current_volume = float(signal_candle["Volume"])
    average_volume = float(clean_data["Volume"].iloc[:-1].mean()) if len(clean_data) > 1 else 0.0
    volume_confirmed = average_volume > 0 and current_volume > average_volume
    sma = _trend_sma(clean_data)
    buy_trend = last_price > sma
    sell_trend = last_price < sma
    breakout_buffer = max(range_high * BREAKOUT_BUFFER_PERCENT, 0.01)
    buy_breakout = last_price > range_high + breakout_buffer
    sell_breakout = last_price < range_low - breakout_buffer

    if not volume_confirmed:
        return _orb_hold(symbol, timestamp, last_price, range_high, range_low, False, "Volume is not above average")

    if last_price > range_high and not buy_breakout:
        return _orb_hold(symbol, timestamp, last_price, range_high, range_low, True, "Breakout is too small; avoiding false breakout")

    if last_price < range_low and not sell_breakout:
        return _orb_hold(symbol, timestamp, last_price, range_high, range_low, True, "Breakdown is too small; avoiding false breakout")

    if buy_breakout and not buy_trend:
        return _orb_hold(symbol, timestamp, last_price, range_high, range_low, True, "Breakout rejected by SMA trend filter")

    if sell_breakout and not sell_trend:
        return _orb_hold(symbol, timestamp, last_price, range_high, range_low, True, "Breakdown rejected by SMA trend filter")

    if buy_breakout:
        return _action_signal(symbol, "BUY", last_price, timestamp, range_high, range_low, volume_confirmed)

    if sell_breakout:
        return _action_signal(symbol, "SELL", last_price, timestamp, range_high, range_low, volume_confirmed)

    return _orb_hold(symbol, timestamp, last_price, range_high, range_low, True, "Price is inside the opening range")


def _action_signal(
    symbol: str,
    signal: Signal,
    entry_price: float,
    timestamp: str,
    range_high: float,
    range_low: float,
    volume_confirmed: bool,
) -> TradeSignal:
    if signal == "BUY":
        target = entry_price * 1.01
        stop_loss = entry_price * 0.995
        reason = "Price broke above opening range high with volume confirmation"
    else:
        target = entry_price * 0.99
        stop_loss = entry_price * 1.005
        reason = "Price broke below opening range low with volume confirmation"

    return TradeSignal(
        symbol=symbol,
        signal=signal,
        entry_price=round(entry_price, 2),
        target=round(target, 2),
        stop_loss=round(stop_loss, 2),
        timestamp=timestamp,
        last_price=round(entry_price, 2),
        opening_range_high=round(range_high, 2),
        opening_range_low=round(range_low, 2),
        volume_confirmed=volume_confirmed,
        reason=reason,
    )


def _hold(symbol: str, timestamp: str, reason: str, last_price: Optional[float] = None) -> TradeSignal:
    return TradeSignal(
        symbol=symbol,
        signal="HOLD",
        entry_price=None,
        target=None,
        stop_loss=None,
        timestamp=timestamp,
        last_price=round(last_price, 2) if last_price is not None else None,
        opening_range_high=None,
        opening_range_low=None,
        volume_confirmed=False,
        reason=reason,
    )


def _orb_hold(
    symbol: str,
    timestamp: str,
    last_price: float,
    range_high: float,
    range_low: float,
    volume_confirmed: bool,
    reason: str,
) -> TradeSignal:
    return TradeSignal(
        symbol=symbol,
        signal="HOLD",
        entry_price=None,
        target=None,
        stop_loss=None,
        timestamp=timestamp,
        last_price=round(last_price, 2),
        opening_range_high=round(range_high, 2),
        opening_range_low=round(range_low, 2),
        volume_confirmed=volume_confirmed,
        reason=reason,
    )


def _opening_range_window(data: pd.DataFrame) -> pd.DataFrame:
    first_timestamp = pd.to_datetime(data.index[0])
    end_timestamp = first_timestamp + pd.Timedelta(minutes=15)
    opening_range = data[pd.to_datetime(data.index) < end_timestamp]
    if opening_range.empty:
        return data.iloc[:1]
    return opening_range


def _trend_sma(data: pd.DataFrame) -> float:
    close = data["Close"].dropna()
    if close.empty:
        return 0.0
    window = min(SMA_WINDOW, len(close))
    return float(close.tail(window).mean())


def _safe_last_price(data: pd.DataFrame) -> Optional[float]:
    if data.empty or "Close" not in data:
        return None
    close = data["Close"].dropna()
    if close.empty:
        return None
    return float(close.iloc[-1])
