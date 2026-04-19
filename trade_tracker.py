from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

import pandas as pd

from strategy import TradeSignal


DATA_DIR = Path("data")
TRADE_STORE = DATA_DIR / "trades.json"


@dataclass
class TrackedTrade:
    id: str
    symbol: str
    side: str
    entry_price: float
    target: float
    stop_loss: float
    entry_timestamp: str
    current_price: float
    status: str = "OPEN"
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0


def process_signals(signals: list[TradeSignal]) -> tuple[pd.DataFrame, dict[str, float]]:
    trades = load_trades()

    for signal in signals:
        if signal.signal in {"BUY", "SELL"}:
            trades = open_trade_if_needed(trades, signal)

        if signal.last_price is not None:
            trades = update_open_trades(trades, signal.symbol, signal.last_price, signal.timestamp)

    save_trades(trades)
    return trades_to_frame(trades), calculate_stats(trades)


def load_trades() -> list[TrackedTrade]:
    if not TRADE_STORE.exists():
        return []

    try:
        raw_trades = json.loads(TRADE_STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    return [TrackedTrade(**trade) for trade in raw_trades]


def save_trades(trades: list[TrackedTrade]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    payload = [asdict(trade) for trade in trades]
    TRADE_STORE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def open_trade_if_needed(trades: list[TrackedTrade], signal: TradeSignal) -> list[TrackedTrade]:
    if signal.entry_price is None or signal.target is None or signal.stop_loss is None:
        return trades

    already_open = any(trade.status == "OPEN" and trade.symbol == signal.symbol for trade in trades)
    if already_open:
        return trades

    trades.append(
        TrackedTrade(
            id=uuid4().hex[:12],
            symbol=signal.symbol,
            side=signal.signal,
            entry_price=float(signal.entry_price),
            target=float(signal.target),
            stop_loss=float(signal.stop_loss),
            entry_timestamp=signal.timestamp,
            current_price=float(signal.last_price or signal.entry_price),
        )
    )
    return trades


def update_open_trades(
    trades: list[TrackedTrade],
    symbol: str,
    latest_price: float,
    timestamp: str,
) -> list[TrackedTrade]:
    for trade in trades:
        if trade.status != "OPEN" or trade.symbol != symbol:
            continue

        trade.current_price = round(float(latest_price), 2)
        trade.pnl = round(_calculate_pnl(trade.side, trade.entry_price, trade.current_price), 2)
        trade.pnl_percent = round(trade.pnl / trade.entry_price * 100, 2)

        exit_reason = _exit_reason(trade, trade.current_price)
        if exit_reason:
            trade.status = "CLOSED"
            trade.exit_price = trade.current_price
            trade.exit_timestamp = timestamp
            trade.exit_reason = exit_reason

    return trades


def trades_to_frame(trades: list[TrackedTrade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(
            columns=[
                "symbol",
                "side",
                "status",
                "entry_price",
                "current_price",
                "target",
                "stop_loss",
                "pnl",
                "pnl_percent",
                "entry_timestamp",
                "exit_price",
                "exit_timestamp",
                "exit_reason",
            ]
        )

    frame = pd.DataFrame([asdict(trade) for trade in trades])
    frame = frame.sort_values(["status", "entry_timestamp"], ascending=[False, False])
    return frame[
        [
            "symbol",
            "side",
            "status",
            "entry_price",
            "current_price",
            "target",
            "stop_loss",
            "pnl",
            "pnl_percent",
            "entry_timestamp",
            "exit_price",
            "exit_timestamp",
            "exit_reason",
        ]
    ]


def calculate_stats(trades: list[TrackedTrade]) -> dict[str, float]:
    closed = [trade for trade in trades if trade.status == "CLOSED"]
    total_pnl = round(sum(trade.pnl for trade in trades), 2)
    wins = sum(1 for trade in closed if trade.pnl > 0)
    win_rate = round((wins / len(closed) * 100), 2) if closed else 0.0

    return {
        "total_pnl": total_pnl,
        "open_trades": float(sum(1 for trade in trades if trade.status == "OPEN")),
        "closed_trades": float(len(closed)),
        "wins": float(wins),
        "losses": float(sum(1 for trade in closed if trade.pnl <= 0)),
        "win_rate": win_rate,
    }


def _calculate_pnl(side: str, entry_price: float, current_price: float) -> float:
    if side == "BUY":
        return current_price - entry_price
    return entry_price - current_price


def _exit_reason(trade: TrackedTrade, latest_price: float) -> Optional[str]:
    if trade.side == "BUY":
        if latest_price >= trade.target:
            return "TARGET"
        if latest_price <= trade.stop_loss:
            return "STOP_LOSS"
    else:
        if latest_price <= trade.target:
            return "TARGET"
        if latest_price >= trade.stop_loss:
            return "STOP_LOSS"

    return None
