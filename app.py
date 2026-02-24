import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.set_page_config(layout="wide")
st.title("🚀 Swing Trade PRO Scanner + Backtest")

@st.cache_data
def get_sp500():
    # Traduzindo símbolos para formato yfinance (. para -)
    table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    return table[0]['Symbol'].str.replace('.', '-', regex=True).tolist()

market = st.selectbox("Mercado", ["S&P500"])
tickers = get_sp500()

# ==========================================
# FUNÇÕES DE APOIO
# ==========================================

def fix_col_names(df):
    """Remove multi-index das colunas do yfinance"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def calculate_indicators(df):
    df["EMA20"] = ta.trend.ema_indicator(df["Close"], 20)
    df["RSI"] = ta.momentum.rsi(df["Close"], 14)
    df["VOL_MA20"] = df["Volume"].rolling(20).mean()
    bb = ta.volatility.BollingerBands(df["Close"], 20, 2)
    df["BB_upper"] = bb.bollinger_hband()
    return df

# ==========================================
# EXECUÇÃO REFORMULADA
# ==========================================

if st.button("🔎 Escanear Mercado (Top 30 para teste)"):
    # Limitando a 30 para não ser bloqueado pelo Yahoo durante o teste
    search_tickers = tickers[:30]
    
    with st.spinner("Baixando dados do SPY e Ações..."):
        spy_df = yf.download("SPY", period="2y", interval="1d", progress=False)
        spy_df = fix_col_names(spy_df)
        spy_ret = spy_df["Close"].pct_change(30).iloc[-1]

        results = []
        prog_bar = st.progress(0)

        for i, ticker in enumerate(search_tickers):
            try:
                # Download único por ticker
                df = yf.download(ticker, period="2y", interval="1d", progress=False)
                if df.empty or len(df) < 50: continue
                
                df = fix_col_names(df)
                df = calculate_indicators(df)
                
                # Força Relativa
                stock_ret = df["Close"].pct_change(30).iloc[-1]
                rs = (stock_ret - spy_ret) * 100

                # Score Simples (Removi o 4h para ganhar velocidade no scanner)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                score = 0
                if last["Close"] > last["EMA20"]: score += 30
                if abs(last["Low"] - last["EMA20"]) / last["EMA20"] < 0.01: score += 20
                if last["RSI"] > prev["RSI"]: score += 20
                if rs > 0: score += 30

                # Sinal Hoje
                signal = "SIM" if (score > 70 and last["Volume"] > last["VOL_MA20"]) else "Não"

                results.append({
                    "Ticker": ticker,
                    "Score": score,
                    "RS (%)": round(rs, 2),
                    "Preço": round(last["Close"], 2),
                    "Sinal Hoje": signal
                })
            except Exception as e:
                continue
            prog_bar.progress((i + 1) / len(search_tickers))

    if results:
        df_res = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(df_res, use_container_width=True)
    else:
        st.error("Nenhum resultado processado.")
