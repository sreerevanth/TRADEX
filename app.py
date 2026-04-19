from __future__ import annotations

from datetime import datetime
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from symbol_resolver import ResolutionResult, resolve_symbols
from trader import analyze_symbols, parse_symbols, signals_to_frame


st.set_page_config(page_title="Tradex", page_icon="TX", layout="wide")
CACHE_TTL_SECONDS = 8


def main() -> None:
    st.markdown(_global_styles(), unsafe_allow_html=True)
    
    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">TRADING TERMINAL</div>
            <h1>TRADEX</h1>
            <p>ORB Scanner • Live Execution • Real P&L</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown('<div class="sidebar-header">CONTROL</div>', unsafe_allow_html=True)
        raw_symbols = st.text_area("Stock symbols", value="AAPL, MSFT, TSLA", height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            auto_refresh = st.toggle("Auto Refresh", value=False)
        with col2:
            if auto_refresh:
                refresh_seconds = st.slider("Interval (s)", min_value=10, max_value=15, value=12, step=1)
            else:
                refresh_seconds = 12
        
        run_scan = st.button("RUN SCAN", type="primary", use_container_width=True)
        st.caption("Yahoo Finance & NSE supported")

    if run_scan:
        st.session_state["tradex_has_run"] = True
        st.session_state["tradex_symbols"] = raw_symbols

    should_run = run_scan or auto_refresh or st.session_state.get("tradex_has_run", False)
    active_symbols = st.session_state.get("tradex_symbols", raw_symbols)

    if not should_run:
        st.markdown(
            """
            <div class="empty-state">
                <h2>Welcome to Tradex</h2>
                <p>Enter symbols and scan to generate signals</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    raw_inputs = parse_symbols(active_symbols)
    if not raw_inputs:
        st.error("Enter at least one symbol")
        return

    with st.spinner("Resolving symbols..."):
        symbols, resolutions = _resolve_cached(tuple(raw_inputs))

    _render_resolutions(resolutions)
    if not symbols:
        st.error("No matching stocks found")
        return

    with st.spinner("Analyzing data..."):
        signals, charts, errors, trades, stats = _analyze_cached(tuple(symbols))

    frame = signals_to_frame(signals)
    if frame.empty:
        st.warning("No signals generated")
        return

    st.markdown(
        f'<div class="timestamp">LIVE • {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True
    )

    _render_performance(stats)
    
    st.markdown('<div class="section-title">SIGNALS</div>', unsafe_allow_html=True)
    cols = st.columns(min(4, len(signals)))
    for index, signal in enumerate(signals):
        with cols[index % len(cols)]:
            st.markdown(_signal_card(signal), unsafe_allow_html=True)

    with st.expander("Signal Matrix"):
        st.dataframe(
            _styled_signal_frame(frame),
            hide_index=True,
            use_container_width=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol"),
                "signal": st.column_config.TextColumn("Signal"),
                "entry_price": st.column_config.NumberColumn("Entry", format="%.2f"),
                "target": st.column_config.NumberColumn("Target", format="%.2f"),
                "stop_loss": st.column_config.NumberColumn("Stop", format="%.2f"),
                "last_price": st.column_config.NumberColumn("Last", format="%.2f"),
                "profit_tracking": st.column_config.TextColumn("P/L"),
                "timestamp": st.column_config.TextColumn("Time"),
                "opening_range_high": st.column_config.NumberColumn("ORB High", format="%.2f"),
                "opening_range_low": st.column_config.NumberColumn("ORB Low", format="%.2f"),
                "volume_confirmed": st.column_config.TextColumn("Vol"),
                "reason": st.column_config.TextColumn("Reason"),
            },
        )

    if errors:
        with st.expander("Warnings"):
            for symbol, error in errors.items():
                st.warning(f"{symbol}: {error}")

    st.markdown('<div class="section-title">TRADES</div>', unsafe_allow_html=True)
    if trades.empty:
        st.info("No trades yet")
    else:
        st.dataframe(
            _styled_trade_frame(trades),
            hide_index=True,
            use_container_width=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol"),
                "side": st.column_config.TextColumn("Side"),
                "status": st.column_config.TextColumn("Status"),
                "entry_price": st.column_config.NumberColumn("Entry", format="%.2f"),
                "current_price": st.column_config.NumberColumn("Current", format="%.2f"),
                "target": st.column_config.NumberColumn("Target", format="%.2f"),
                "stop_loss": st.column_config.NumberColumn("Stop", format="%.2f"),
                "pnl": st.column_config.NumberColumn("P&L", format="%.2f"),
                "pnl_percent": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
                "entry_timestamp": st.column_config.TextColumn("Entry Time"),
                "exit_price": st.column_config.NumberColumn("Exit", format="%.2f"),
                "exit_timestamp": st.column_config.TextColumn("Exit Time"),
                "exit_reason": st.column_config.TextColumn("Reason"),
            },
        )

    _render_system_log(signals, trades)

    st.markdown('<div class="section-title">CHARTS</div>', unsafe_allow_html=True)
    signal_by_symbol = {signal.symbol: signal for signal in signals}
    
    for symbol in symbols:
        data = charts.get(symbol)
        if data is None or data.empty:
            st.warning(f"{symbol}: No data")
            continue

        st.plotly_chart(
            _price_figure(symbol, data, signal_by_symbol.get(symbol), _symbol_trades(trades, symbol)),
            use_container_width=True,
            config={"displayModeBar": True, "scrollZoom": True},
        )

    if auto_refresh:
        time.sleep(refresh_seconds)
        st.rerun()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _analyze_cached(symbols: tuple[str, ...]):
    return analyze_symbols(list(symbols))


@st.cache_data(ttl=300, show_spinner=False)
def _resolve_cached(raw_symbols: tuple[str, ...]):
    return resolve_symbols(list(raw_symbols))


def _render_resolutions(resolutions: list[ResolutionResult]) -> None:
    if not resolutions:
        return
    with st.expander("Symbol Resolution"):
        for result in resolutions:
            if result.resolved:
                st.success(f"✓ {result.message}")
            else:
                st.error(f"✗ {result.original}: Not found")


def _price_figure(symbol: str, data: pd.DataFrame, signal, trades: pd.DataFrame) -> go.Figure:
    chart = data.sort_index().copy()
    latest_price = float(chart["Close"].iloc[-1])
    session_high = float(chart["High"].max())
    session_low = float(chart["Low"].min())

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=chart.index,
            open=chart["Open"],
            high=chart["High"],
            low=chart["Low"],
            close=chart["Close"],
            name=symbol,
            increasing_line_color="#ffd400",
            decreasing_line_color="#ff4d4d",
            increasing_fillcolor="rgba(255,212,0,0.25)",
            decreasing_fillcolor="rgba(255,77,77,0.25)",
            hoverlabel={"bgcolor": "#0f0f0f"},
        )
    )

    fig.add_hline(y=latest_price, line_width=2, line_dash="dot", line_color="#ffd400")
    fig.add_hline(y=session_high, line_width=1.5, line_dash="dash", line_color="#ffd400")
    fig.add_hline(y=session_low, line_width=1.5, line_dash="dash", line_color="#ff4d4d")

    if signal and signal.signal in {"BUY", "SELL"} and signal.entry_price is not None:
        marker_symbol = "triangle-up" if signal.signal == "BUY" else "triangle-down"
        marker_color = "#ffd400" if signal.signal == "BUY" else "#ff4d4d"
        fig.add_trace(
            go.Scatter(
                x=[chart.index[-1]],
                y=[signal.entry_price],
                mode="markers+text",
                marker={"symbol": marker_symbol, "size": 15, "color": marker_color},
                text=[signal.signal],
                textposition="top center",
                name=f"{signal.signal}",
            )
        )

    _add_trade_markers(fig, trades)

    fig.update_layout(
        template="plotly_dark",
        height=480,
        title=f"{symbol}  |  {latest_price:.2f}",
        xaxis_title=None,
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
        paper_bgcolor="#050505",
        plot_bgcolor="#0f0f0f",
        font={"family": "monospace", "color": "#eaeaea", "size": 10},
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(255,212,0,0.1)")
    fig.update_yaxes(gridcolor="rgba(255,212,0,0.1)")
    return fig


def _add_trade_markers(fig: go.Figure, trades: pd.DataFrame) -> None:
    if trades.empty:
        return
    for _, trade in trades.iterrows():
        entry_time = pd.to_datetime(trade["entry_timestamp"], errors="coerce")
        if pd.notna(entry_time):
            fig.add_trace(
                go.Scatter(
                    x=[entry_time],
                    y=[trade["entry_price"]],
                    mode="markers",
                    marker={"symbol": "circle", "size": 10, "color": "#ffd400"},
                    name="Entry",
                    hovertemplate="%{y:.2f}<extra></extra>",
                )
            )
        exit_time = pd.to_datetime(trade["exit_timestamp"], errors="coerce")
        if pd.notna(exit_time) and pd.notna(trade["exit_price"]):
            fig.add_trace(
                go.Scatter(
                    x=[exit_time],
                    y=[trade["exit_price"]],
                    mode="markers",
                    marker={"symbol": "x", "size": 12, "color": "#ff4d4d"},
                    name="Exit",
                    hovertemplate="%{y:.2f}<extra></extra>",
                )
            )


def _symbol_trades(trades: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if trades.empty:
        return trades
    return trades[trades["symbol"] == symbol]


def _render_performance(stats: dict[str, float]) -> None:
    cards = [
        ("TOTAL P&L", f"${stats.get('total_pnl', 0.0):.2f}", "pnl"),
        ("WIN RATE", f"{stats.get('win_rate', 0.0):.1f}%", "stat"),
        ("OPEN", f"{int(stats.get('open_trades', 0))}", "stat"),
        ("CLOSED", f"{int(stats.get('closed_trades', 0))}", "stat"),
    ]
    html = '<div class="metric-grid">'
    for label, value, card_type in cards:
        if card_type == "pnl":
            is_negative = str(value).startswith("-")
            color = "#ff4d4d" if is_negative else "#ffd400"
        else:
            color = "#ffd400"
        html += f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color: {color};">{value}</div>
        </div>
        """
    html += "</div>"
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _render_system_log(signals, trades: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">SYSTEM LOG</div>', unsafe_allow_html=True)
    lines = [f"[{datetime.now().strftime('%H:%M:%S')}] SYSTEM ONLINE"]
    for signal in signals:
        lines.append(f"[{signal.symbol}] {signal.signal} @ {_format_price(signal.last_price)} • {signal.reason}")
    if not trades.empty:
        for _, trade in trades.tail(5).iterrows():
            status = "OPEN" if trade["status"] == "OPEN" else f"CLOSED"
            lines.append(f"[{trade['symbol']}] {trade['side']} {status} • P&L: {_format_price(trade['pnl'])}")
    content = "\n".join(lines)
    st.markdown(f"<pre class='system-log'>{content}</pre>", unsafe_allow_html=True)


def _signal_card(signal) -> str:
    entry = _format_price(signal.entry_price)
    target = _format_price(signal.target)
    stop = _format_price(signal.stop_loss)
    
    border_color = "#ffd400" if signal.signal == "BUY" else "#ff4d4d" if signal.signal == "SELL" else "#444"
    card_class = "buy" if signal.signal == "BUY" else "sell" if signal.signal == "SELL" else "hold"
    
    return f"""
    <div class="signal-card {card_class}" style="border-left: 4px solid {border_color};">
        <div class="signal-symbol">{signal.symbol}</div>
        <div class="signal-type">{signal.signal}</div>
        <div class="signal-reason">{signal.reason}</div>
        <div class="signal-levels">
            <div>ENTRY: {entry}</div>
            <div>TARGET: {target}</div>
            <div>STOP: {stop}</div>
        </div>
    </div>
    """


def _format_price(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}"


def _styled_signal_frame(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    def color_signal(value: str) -> str:
        colors = {
            "BUY": "color: #ffd400; font-weight: bold;",
            "SELL": "color: #ff4d4d; font-weight: bold;",
            "HOLD": "color: #777;",
        }
        return colors.get(value, "")
    styler = frame.style
    if hasattr(styler, "map"):
        return styler.map(color_signal, subset=["signal"])
    return styler.applymap(color_signal, subset=["signal"])


def _styled_trade_frame(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    def color_pnl(value: float) -> str:
        if value > 0:
            return "color: #ffd400; font-weight: bold;"
        if value < 0:
            return "color: #ff4d4d; font-weight: bold;"
        return ""
    styler = frame.style
    if hasattr(styler, "map"):
        return styler.map(color_pnl, subset=["pnl", "pnl_percent"])
    return styler.applymap(color_pnl, subset=["pnl", "pnl_percent"])


def _global_styles() -> str:
    return """
    <style>
    * {
        font-family: "JetBrains Mono", "Courier New", monospace;
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: #050505 !important;
        color: #eaeaea !important;
    }

    [data-testid="stHeader"] {
        background: #050505;
        border-bottom: 1px solid #222;
    }

    [data-testid="stSidebar"] {
        background: #050505 !important;
        border-right: 1px solid #222;
    }

    .sidebar-header {
        color: #ffd400;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 16px;
        letter-spacing: 1px;
    }

    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {
        color: #777 !important;
        font-size: 11px;
    }

    textarea, input {
        background: #0f0f0f !important;
        color: #ffd400 !important;
        border: 1px solid #222 !important;
        border-radius: 4px !important;
    }

    textarea:focus, input:focus {
        border-color: #ffd400 !important;
    }

    .stButton > button {
        background: #111 !important;
        color: #ffd400 !important;
        border: 1px solid #ffd400 !important;
        border-radius: 4px !important;
        text-transform: uppercase;
        font-weight: bold;
        font-size: 11px;
    }

    .stButton > button:hover {
        background: #ffd400 !important;
        color: #000 !important;
    }

    .stButton > button:active {
        transform: scale(0.97);
    }

    .hero {
        border: 1px solid #222;
        background: #0f0f0f;
        border-radius: 8px;
        padding: 32px;
        margin-bottom: 24px;
    }

    .hero-kicker {
        color: #777;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }

    .hero h1 {
        color: #ffd400;
        font-size: 48px;
        font-weight: bold;
        margin: 0;
        line-height: 1;
        letter-spacing: 2px;
    }

    .hero h1::after {
        content: "_";
        animation: blink 1s infinite;
    }

    @keyframes blink {
        0%, 50%, 100% { opacity: 1; }
        25%, 75% { opacity: 0; }
    }

    .hero p {
        color: #777;
        margin: 8px 0 0;
        font-size: 12px;
        text-transform: uppercase;
    }

    .timestamp {
        color: #ffd400;
        border: 1px solid #222;
        display: inline-block;
        padding: 8px 12px;
        border-radius: 4px;
        background: #0f0f0f;
        margin-bottom: 16px;
        font-size: 11px;
        font-weight: bold;
    }

    .section-title {
        color: #eaeaea;
        font-size: 14px;
        font-weight: bold;
        text-transform: uppercase;
        margin: 24px 0 16px;
        padding-left: 0;
        border-left: none;
        letter-spacing: 1px;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 12px 0 20px;
    }

    .metric-card {
        background: #0f0f0f;
        border: 1px solid #222;
        border-radius: 4px;
        padding: 16px;
        text-align: center;
    }

    .metric-label {
        color: #777;
        font-size: 10px;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 20px;
        font-weight: bold;
        text-shadow: 0 0 6px rgba(255,212,0,0.3);
    }

    .system-log {
        max-height: 250px;
        overflow-y: auto;
        background: #000;
        color: #ffd400;
        border: 1px solid #222;
        border-radius: 4px;
        padding: 12px;
        font-size: 11px;
        line-height: 1.6;
        white-space: pre-wrap;
        font-weight: 600;
    }

    .empty-state {
        text-align: center;
        padding: 40px;
        border: 1px dashed #222;
        border-radius: 8px;
        background: #0f0f0f;
    }

    .empty-state h2 {
        color: #eaeaea;
        font-size: 20px;
        margin-bottom: 8px;
    }

    .empty-state p {
        color: #777;
        font-size: 12px;
    }

    .signal-card {
        background: #0f0f0f;
        border: 1px solid #222;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 10px;
        min-height: auto;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: 0.2s ease;
    }

    .signal-card:hover {
        border-color: #ffd400;
        transform: translateY(-2px);
    }

    .signal-symbol {
        color: #ffd400;
        font-size: 14px;
        font-weight: bold;
        margin-bottom: 8px;
        letter-spacing: 1px;
    }

    .signal-type {
        font-size: 26px;
        font-weight: bold;
        margin-bottom: 6px;
        letter-spacing: 1px;
    }

    .signal-card.buy .signal-type {
        color: #ffd400;
    }

    .signal-card.sell .signal-type {
        color: #ff4d4d;
    }

    .signal-reason {
        color: #777;
        font-size: 11px;
        margin-bottom: 12px;
        line-height: 1.4;
    }

    .signal-levels {
        font-size: 11px;
        color: #eaeaea;
        display: grid;
        grid-template-columns: 1fr;
        gap: 4px;
    }

    [data-testid="stExpander"] {
        background: #0f0f0f !important;
        border: 1px solid #222 !important;
        border-radius: 4px !important;
    }

    .stAlert {
        background: #0f0f0f !important;
        border: 1px solid #222 !important;
        color: #eaeaea !important;
        border-radius: 4px !important;
    }

    [data-testid="stDataFrame"] {
        background: #0f0f0f !important;
        border: 1px solid #222 !important;
    }

    [data-testid="stDataFrame"] th {
        background: #111 !important;
        color: #ffd400 !important;
        border-color: #222 !important;
        font-weight: bold;
        font-size: 11px;
    }

    [data-testid="stDataFrame"] td {
        color: #eaeaea !important;
        border-color: #222 !important;
    }

    @media (max-width: 900px) {
        .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hero h1 { font-size: 36px; }
    }

    @media (max-width: 600px) {
        .metric-grid { grid-template-columns: 1fr; }
        .hero { padding: 16px; }
        .hero h1 { font-size: 28px; }
    }
    </style>
    """


if __name__ == "__main__":
    main()
