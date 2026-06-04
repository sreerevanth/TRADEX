# paper_trader.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from strategy import TradeSignal

DATA_DIR = Path("data")
PAPER_TRADES_FILE = DATA_DIR / "paper_trades.json"


def log_paper_trade(signal: TradeSignal, sl_pct: float = 0.5, tp_pct: float = 1.0) -> None:
    """Log a simulated paper trade to data/paper_trades.json."""
    if signal.signal not in {"BUY", "SELL"} or signal.entry_price is None:
        return

    DATA_DIR.mkdir(exist_ok=True)

    entry = signal.entry_price
    if signal.signal == "BUY":
        stop_loss = round(entry * (1 - sl_pct / 100), 2)
        take_profit = round(entry * (1 + tp_pct / 100), 2)
    else:
        stop_loss = round(entry * (1 + sl_pct / 100), 2)
        take_profit = round(entry * (1 - tp_pct / 100), 2)

    trade = {
        "id": f"{signal.symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "symbol": signal.symbol,
        "side": signal.signal,
        "entry_price": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "status": "OPEN",
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": signal.timestamp,
        "exit_price": None,
        "exit_time": None,
        "exit_reason": None,
    }

    existing = _load_trades()

    # Auto-close any existing OPEN trade for same symbol
    for t in existing:
        if t["symbol"] == signal.symbol and t["status"] == "OPEN":
            current_price = signal.last_price or entry
            t["status"] = "CLOSED"
            t["exit_price"] = current_price
            t["exit_time"] = datetime.now().isoformat(timespec="seconds")
            t["exit_reason"] = "New signal"
            if t["side"] == "BUY":
                t["pnl"] = round(current_price - t["entry_price"], 2)
                t["pnl_pct"] = round((current_price - t["entry_price"]) / t["entry_price"] * 100, 2)
            else:
                t["pnl"] = round(t["entry_price"] - current_price, 2)
                t["pnl_pct"] = round((t["entry_price"] - current_price) / t["entry_price"] * 100, 2)

    existing.append(trade)

    with PAPER_TRADES_FILE.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def get_paper_trades() -> list[dict]:
    """Return all paper trades from the JSON file."""
    return _load_trades()


def get_paper_stats() -> dict:
    """Return summary stats for paper trades."""
    trades = _load_trades()
    closed = [t for t in trades if t["status"] == "CLOSED"]
    open_trades = [t for t in trades if t["status"] == "OPEN"]

    if not closed:
        return {
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "total_trades": len(trades),
            "open_trades": len(open_trades),
            "closed_trades": 0,
        }

    winners = [t for t in closed if t["pnl"] > 0]
    total_pnl = round(sum(t["pnl"] for t in closed), 2)
    win_rate = round(len(winners) / len(closed) * 100, 1)

    return {
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "total_trades": len(trades),
        "open_trades": len(open_trades),
        "closed_trades": len(closed),
    }


def clear_paper_trades() -> None:
    """Wipe all paper trades."""
    if PAPER_TRADES_FILE.exists():
        PAPER_TRADES_FILE.write_text("[]", encoding="utf-8")


def _load_trades() -> list[dict]:
    if not PAPER_TRADES_FILE.exists():
        return []
    try:
        with PAPER_TRADES_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []