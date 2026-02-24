import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.set_page_config(layout="wide")
st.title("🚀 Swing Trade PRO Scanner + Backtest")

# ==========================================
# LISTAS DE AÇÕES
# ==========================================

@st.cache_data
def get_sp500():
    table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    return table[0]['Symbol'].tolist()

@st.cache_data
def get_nasdaq():
    table = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')
    return table[4]['Ticker'].tolist()

market = st.selectbox("Mercado", ["S&P500", "NASDAQ 100"])

tickers = get_sp500() if market == "S&P500" else get_nasdaq()

# ==========================================
# FORÇA RELATIVA
# ==========================================

def relative_strength(stock_df, spy_df):
    stock_return = stock_df["Close"].pct_change(30).iloc[-1]
    spy_return = spy_df["Close"].pct_change(30).iloc[-1]
    return (stock_return - spy_return) * 100

# ==========================================
# SCORE
# ==========================================

def calculate_score(df, df4h, rs):
    score = 0
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["Close"] > last["EMA20"]:
        score += 20

    if abs(last["Low"] - last["EMA20"]) / last["EMA20"] < 0.01:
        score += 15

    if prev["RSI"] < 50 and last["RSI"] > prev["RSI"]:
        score += 15

    if last["Volume"] > df["VOL_MA20"].iloc[-1]:
        score += 10

    if rs > 0:
        score += 10

    last4h = df4h.iloc[-1]
    if last4h["Close"] > last4h["EMA20"] and last4h["RSI"] > 50:
        score += 20

    return score

# ==========================================
# BACKTEST DO SETUP
# ==========================================

def backtest(df):

    wins = 0
    losses = 0
    results = []

    for i in range(50, len(df)-10):

        row = df.iloc[i]
        prev = df.iloc[i-1]

        # condições da estratégia
        trend = row["Close"] > row["EMA20"]
        pullback = abs(row["Low"] - row["EMA20"]) / row["EMA20"] < 0.01
        rsi_cond = prev["RSI"] < 50 and row["RSI"] > prev["RSI"]
        volume = row["Volume"] > df["VOL_MA20"].iloc[i]

        if trend and pullback and rsi_cond and volume:

            entry = row["Close"]
            stop = min(row["Low"], row["EMA20"])
            target = row["BB_upper"]

            for j in range(i+1, min(i+10, len(df))):

                future = df.iloc[j]

                if future["Low"] <= stop:
                    losses += 1
                    results.append(-1)
                    break

                if future["High"] >= target:
                    wins += 1
                    results.append(1)
                    break

    total = wins + losses
    if total == 0:
        return 0, 0, 0

    winrate = wins / total * 100
    expectancy = (winrate/100 * 2) - ((1 - winrate/100) * 1)

    return round(winrate,2), round(expectancy,2), total

# ==========================================
# ANÁLISE PRINCIPAL
# ==========================================

def analyze_stock(ticker, spy_df):

    df = yf.download(ticker, period="2y", interval="1d", progress=False)

    if len(df) < 200:
        return None

    df["EMA20"] = ta.trend.ema_indicator(df["Close"], 20)
    df["RSI"] = ta.momentum.rsi(df["Close"], 14)
    df["VOL_MA20"] = df["Volume"].rolling(20).mean()

    bb = ta.volatility.BollingerBands(df["Close"], 20, 2)
    df["BB_upper"] = bb.bollinger_hband()

    spy_return = relative_strength(df, spy_df)

    # Multi timeframe
    df4h = yf.download(ticker, period="1mo", interval="4h", progress=False)
    if len(df4h) < 50:
        return None

    df4h["EMA20"] = ta.trend.ema_indicator(df4h["Close"], 20)
    df4h["RSI"] = ta.momentum.rsi(df4h["Close"], 14)

    score = calculate_score(df, df4h, spy_return)

    winrate, expectancy, total_trades = backtest(df)

    last = df.iloc[-1]

    signal_now = (
        last["Close"] > last["EMA20"]
        and abs(last["Low"] - last["EMA20"]) / last["EMA20"] < 0.01
        and last["RSI"] > df.iloc[-2]["RSI"]
        and last["Volume"] > df["VOL_MA20"].iloc[-1]
    )

    return {
        "Ticker": ticker,
        "Score": score,
        "RS (%)": round(spy_return,2),
        "Win Rate (%)": winrate,
        "Expectancy": expectancy,
        "Trades Históricos": total_trades,
        "Sinal Hoje": "SIM" if signal_now else "Não"
    }

# ==========================================
# EXECUÇÃO
# ==========================================

if st.button("🔎 Escanear Mercado Completo"):

    spy_df = yf.download("SPY", period="2y", interval="1d", progress=False)

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers[:100]):
        data = analyze_stock(ticker, spy_df)
        if data:
            results.append(data)
        progress.progress((i+1)/100)

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(["Score","Win Rate (%)"], ascending=False)
        st.success("Scan finalizado!")
        st.dataframe(df_results)
    else:
        st.warning("Nenhum dado encontrado.")
