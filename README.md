# ⚡ TRADEX — Real-Time Trading Dashboard

A hacker-style intraday trading simulation dashboard that generates live BUY/SELL signals, tracks trades, and visualizes market data with interactive charts.

---
##DEMO 
https://github.com/user-attachments/assets/f2789874-dcdd-4239-9b01-6c53bc63a9db
---


## 🚀 Overview

Tradex is a real-time trading system built to simulate how intraday strategies behave in live market conditions.

It scans stocks, applies the **Opening Range Breakout (ORB)** strategy, generates actionable signals, and tracks trades with live P&L — all inside a clean terminal-style UI.

---

## ✨ Features

- 📊 **ORB Strategy Engine**
  - Detects breakouts from the first 15-minute range
  - Generates BUY / SELL / HOLD signals

- 🔁 **Real-Time Data Pipeline**
  - Uses yfinance for intraday data
  - Multi-level fallback system (Yahoo APIs)
  - Never silently fails

- 🧠 **Smart Symbol Resolution**
  - Handles typos and natural names
  - Auto-resolves to valid tickers

- 💰 **Trade Tracking System**
  - Auto opens/closes trades
  - Tracks:
    - Entry / Exit
    - Target & Stop-loss
    - Live P&L
    - Win rate

- 📈 **Interactive Charts**
  - Plotly candlestick charts
  - Entry / Exit markers
  - Session high / low tracking

- 💻 **Hacker-Style UI**
  - Built with Streamlit
  - Neon terminal-inspired design
  - Real-time system log

---

## 🧠 Strategy Logic

Tradex uses a refined version of **Opening Range Breakout (ORB)**:

- Uses first **15-minute high/low**
- BUY → breakout above high  
- SELL → breakdown below low  

Additional filters:
- Volume confirmation  
- Trend filter (SMA)  
- Breakout buffer to reduce noise  

---

## 🛠 Tech Stack

- **Python**
- **Streamlit**
- **Plotly**
- **Pandas


- **yfinance + Yahoo Finance APIs**

---

## ▶️ Run Locally

```bash
git clone https://github.com/sreerevanth/TRADEX.git
cd TRADEX
pip install -r requirements.txt
streamlit run app.py
