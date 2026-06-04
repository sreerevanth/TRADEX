# backtester.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass
class BacktestResult:
    ticker: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float          # percentage
    total_return: float      # dollar P&L (per share)
    total_return_pct: float  # percentage return
    max_drawdown: float      # percentage
    avg_trade_pnl: float
    trade_log: list[dict]


def run_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    sl_pct: float = 0.5,
    tp_pct: float = 1.0,
    orb_minutes: int = 15,
) -> BacktestResult:
    """
    Fetch historical 1-minute intraday data and replay the ORB strategy
    day-by-day. Returns a BacktestResult with full trade log and metrics.
    """
    # yfinance caps 1m data at 7 days; use 5m for longer ranges
    delta_days = (end_date - start_date).days
    interval = "1m" if delta_days <= 7 else "5m"

    raw = yf.download(
        ticker,
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        interval=interval,
        progress=False,
        auto_adjust=True,
    )

    if raw.empty:
        return BacktestResult(
            ticker=ticker,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return=0.0,
            total_return_pct=0.0,
            max_drawdown=0.0,
            avg_trade_pnl=0.0,
            trade_log=[],
        )

    # Flatten MultiIndex columns if present
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw.index = pd.to_datetime(raw.index)
    # Group by calendar date
    trade_log = []
    equity_curve = [0.0]
    running_pnl = 0.0

    for day, day_data in raw.groupby(raw.index.date):
        day_data = day_data.sort_index()
        if len(day_data) < 2:
            continue

        # Opening range = first orb_minutes of the session
        session_start = day_data.index[0]
        orb_end = session_start + pd.Timedelta(minutes=orb_minutes)
        orb_data = day_data[day_data.index < orb_end]

        if orb_data.empty:
            continue

        orb_high = float(orb_data["High"].max())
        orb_low = float(orb_data["Low"].min())

        # Signal candles = everything after ORB window
        post_orb = day_data[day_data.index >= orb_end]
        if post_orb.empty:
            continue

        signal_generated = False
        for ts, candle in post_orb.iterrows():
            close = float(candle["Close"])

            if close > orb_high and not signal_generated:
                side = "BUY"
                entry = close
                take_profit = round(entry * (1 + tp_pct / 100), 2)
                stop_loss = round(entry * (1 - sl_pct / 100), 2)
                signal_generated = True

            elif close < orb_low and not signal_generated:
                side = "SELL"
                entry = close
                take_profit = round(entry * (1 - tp_pct / 100), 2)
                stop_loss = round(entry * (1 + sl_pct / 100), 2)
                signal_generated = True

            else:
                continue

            # Simulate trade: scan remaining candles of the day for exit
            remaining = post_orb[post_orb.index > ts]
            exit_price = None
            exit_reason = "EOD"

            for _, future in remaining.iterrows():
                hi = float(future["High"])
                lo = float(future["Low"])

                if side == "BUY":
                    if lo <= stop_loss:
                        exit_price = stop_loss
                        exit_reason = "Stop Loss"
                        break
                    if hi >= take_profit:
                        exit_price = take_profit
                        exit_reason = "Take Profit"
                        break
                else:  # SELL
                    if hi >= stop_loss:
                        exit_price = stop_loss
                        exit_reason = "Stop Loss"
                        break
                    if lo <= take_profit:
                        exit_price = take_profit
                        exit_reason = "Take Profit"
                        break

            if exit_price is None:
                # Close at end of day
                exit_price = float(day_data["Close"].iloc[-1])

            if side == "BUY":
                pnl = round(exit_price - entry, 2)
            else:
                pnl = round(entry - exit_price, 2)

            pnl_pct = round(pnl / entry * 100, 2)
            running_pnl += pnl
            equity_curve.append(running_pnl)

            trade_log.append({
                "date": str(day),
                "side": side,
                "entry": round(entry, 2),
                "exit": round(exit_price, 2),
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
            })

            break  # one trade per day

    if not trade_log:
        return BacktestResult(
            ticker=ticker,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return=0.0,
            total_return_pct=0.0,
            max_drawdown=0.0,
            avg_trade_pnl=0.0,
            trade_log=[],
        )

    winners = [t for t in trade_log if t["pnl"] > 0]
    losers = [t for t in trade_log if t["pnl"] <= 0]
    total_return = round(sum(t["pnl"] for t in trade_log), 2)
    first_entry = trade_log[0]["entry"]
    total_return_pct = round(total_return / first_entry * 100, 2) if first_entry else 0.0
    avg_trade_pnl = round(total_return / len(trade_log), 2)

    # Max drawdown from equity curve
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val)
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = round(max_dd / first_entry * 100, 2) if first_entry else 0.0

    return BacktestResult(
        ticker=ticker,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_trades=len(trade_log),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=round(len(winners) / len(trade_log) * 100, 1),
        total_return=total_return,
        total_return_pct=total_return_pct,
        max_drawdown=max_dd_pct,
        avg_trade_pnl=avg_trade_pnl,
        trade_log=trade_log,
    )