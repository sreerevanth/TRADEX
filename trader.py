from __future__ import annotations

import csv
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import pandas as pd

from data_fetcher import fetch_intraday_data, market_timestamp
from strategy import TradeSignal, calculate_orb_signal
from trade_tracker import process_signals


LOG_DIR = Path("logs")
TRADE_LOG = LOG_DIR / "trades.csv"
APP_LOG = LOG_DIR / "tradex.log"


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=APP_LOG,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_symbols(raw_symbols: str) -> list[str]:
    symbols = [part.strip() for part in raw_symbols.replace("\n", ",").split(",")]
    return [symbol for symbol in symbols if symbol]


def analyze_symbols(
    symbols: Iterable[str],
) -> tuple[list[TradeSignal], dict[str, pd.DataFrame], dict[str, str], pd.DataFrame, dict[str, float]]:
    configure_logging()
    signals: list[TradeSignal] = []
    charts: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    for symbol in symbols:
        result = fetch_intraday_data(symbol)
        timestamp = result.timestamp or (
            market_timestamp(result.data) if not result.data.empty else pd.Timestamp.now().isoformat(timespec="seconds")
        )

        if result.error:
            errors[result.symbol or symbol] = result.error

        signal = calculate_orb_signal(result.symbol or symbol, result.data, timestamp)
        signals.append(signal)

        if not result.data.empty:
            charts[result.symbol or symbol] = result.data

        if signal.signal in {"BUY", "SELL"}:
            log_trade(signal)

    trades, stats = process_signals(signals)
    return signals, charts, errors, trades, stats


def signals_to_frame(signals: list[TradeSignal]) -> pd.DataFrame:
    rows = []
    for signal in signals:
        row = asdict(signal)
        row["profit_tracking"] = calculate_profit_text(signal)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    return frame[
        [
            "symbol",
            "signal",
            "entry_price",
            "target",
            "stop_loss",
            "last_price",
            "profit_tracking",
            "timestamp",
            "opening_range_high",
            "opening_range_low",
            "volume_confirmed",
            "reason",
        ]
    ]


def calculate_profit_text(signal: TradeSignal) -> str:
    if signal.entry_price is None or signal.last_price is None:
        return "-"

    if signal.signal == "BUY":
        pnl_percent = (signal.last_price - signal.entry_price) / signal.entry_price * 100
    elif signal.signal == "SELL":
        pnl_percent = (signal.entry_price - signal.last_price) / signal.entry_price * 100
    else:
        return "-"

    return f"{pnl_percent:.2f}%"


def log_trade(signal: TradeSignal) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    exists = TRADE_LOG.exists()
    fields = [
        "timestamp",
        "symbol",
        "signal",
        "entry_price",
        "target",
        "stop_loss",
        "last_price",
        "reason",
    ]

    with TRADE_LOG.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: getattr(signal, field) for field in fields})
