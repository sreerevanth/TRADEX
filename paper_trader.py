from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

TRADES_FILE = "data/paper_trades.json"


def _load_trades() -> list[dict]:
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, "r") as f:
        return json.load(f)


def _save_trades(trades: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def log_paper_trade(signal, sl_pct: float = 0.5, tp_pct: float = 1.0) -> None:
    trades = _load_trades()

    # Auto-close any open trade for the same symbol on new signal
    for trade in trades:
        if trade["symbol"] == signal.symbol and trade["status"] == "OPEN":
            current = signal.last_price or signal.entry_price
            trade["status"] = "CLOSED"
            trade["exit_price"] = current
            trade["exit_time"] = datetime.now().strftime("%H:%M:%S")
            trade["exit_reason"] = "NEW_SIGNAL"
            pnl = (current - trade["entry_price"]) * (1 if trade["side"] == "BUY" else -1)
            trade["pnl"] = round(pnl, 4)
            trade["pnl_pct"] = round((pnl / trade["entry_price"]) * 100, 4)

    entry = signal.entry_price
    if signal.signal == "BUY":
        sl = entry * (1 - sl_pct / 100)
        tp = entry * (1 + tp_pct / 100)
    else:
        sl = entry * (1 + sl_pct / 100)
        tp = entry * (1 - tp_pct / 100)

    new_trade: dict[str, Any] = {
        "symbol": signal.symbol,
        "side": signal.signal,
        "status": "OPEN",
        "entry_price": round(entry, 4),
        "stop_loss": round(sl, 4),
        "take_profit": round(tp, 4),
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": datetime.now().strftime("%H:%M:%S"),
        "exit_price": None,
        "exit_time": None,
        "exit_reason": None,
    }
    trades.append(new_trade)
    _save_trades(trades)


def get_paper_trades() -> list[dict]:
    return _load_trades()


def get_paper_stats() -> dict:
    trades = _load_trades()
    closed = [t for t in trades if t["status"] == "CLOSED"]
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    wins = [t for t in closed if t["pnl"] > 0]
    total_pnl = sum(t["pnl"] for t in closed)
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0
    return {
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 1),
        "open_trades": len(open_trades),
        "closed_trades": len(closed),
    }


def clear_paper_trades() -> None:
    _save_trades([])