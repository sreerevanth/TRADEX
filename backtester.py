from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yfinance as yf


@dataclass
class BacktestResult:
    total_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    trade_log: list[dict[str, Any]] = field(default_factory=list)


def run_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    sl_pct: float = 0.5,
    tp_pct: float = 1.0,
) -> BacktestResult:
    df = yf.download(
        ticker,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )

    if df.empty or len(df) < 3:
        return BacktestResult()

    df = df.copy()
    trade_log: list[dict[str, Any]] = []

    # ORB strategy: use first candle's high/low as the opening range
    # Entry on breakout above ORB high (BUY) or below ORB low (SELL)
    orb_high = float(df["High"].iloc[0])
    orb_low  = float(df["Low"].iloc[0])

    for i in range(1, len(df)):
        row = df.iloc[i]
        day_open  = float(row["Open"])
        day_high  = float(row["High"])
        day_low   = float(row["Low"])
        day_close = float(row["Close"])
        date_str  = str(df.index[i].date())

        side: str | None = None
        entry: float | None = None

        # Determine breakout direction
        if day_open > orb_high:
            side, entry = "BUY", day_open
        elif day_open < orb_low:
            side, entry = "SELL", day_open

        if side is None or entry is None:
            # Update ORB with previous day
            orb_high = max(orb_high, day_high)
            orb_low  = min(orb_low, day_low)
            continue

        if side == "BUY":
            sl_price = entry * (1 - sl_pct / 100)
            tp_price = entry * (1 + tp_pct / 100)
        else:
            sl_price = entry * (1 + sl_pct / 100)
            tp_price = entry * (1 - tp_pct / 100)

        # Simulate intraday exit using day's high/low
        exit_price: float
        exit_reason: str

        if side == "BUY":
            if day_low <= sl_price:
                exit_price, exit_reason = sl_price, "STOP_LOSS"
            elif day_high >= tp_price:
                exit_price, exit_reason = tp_price, "TAKE_PROFIT"
            else:
                exit_price, exit_reason = day_close, "EOD"
        else:
            if day_high >= sl_price:
                exit_price, exit_reason = sl_price, "STOP_LOSS"
            elif day_low <= tp_price:
                exit_price, exit_reason = tp_price, "TAKE_PROFIT"
            else:
                exit_price, exit_reason = day_close, "EOD"

        pnl = (exit_price - entry) * (1 if side == "BUY" else -1)
        pnl_pct = (pnl / entry) * 100

        trade_log.append({
            "date": date_str,
            "side": side,
            "entry": round(entry, 4),
            "exit": round(exit_price, 4),
            "stop_loss": round(sl_price, 4),
            "take_profit": round(tp_price, 4),
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 4),
            "exit_reason": exit_reason,
        })

        orb_high = day_high
        orb_low  = day_low

    if not trade_log:
        return BacktestResult()

    wins = [t for t in trade_log if t["pnl"] > 0]
    total_return = sum(t["pnl"] for t in trade_log)
    total_return_pct = sum(t["pnl_pct"] for t in trade_log)
    win_rate = round(len(wins) / len(trade_log) * 100, 1)

    # Max drawdown from equity curve
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trade_log:
        equity += t["pnl"]
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return BacktestResult(
        total_trades=len(trade_log),
        win_rate=win_rate,
        total_return=round(total_return, 2),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown=round(max_dd, 2),
        trade_log=trade_log,
    )