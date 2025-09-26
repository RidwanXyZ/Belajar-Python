##!pip install pandas yfinance --upgrade

import yfinance as yf
import pandas as pd
import numpy as np

# Contoh list saham syariah (isi sesuai kebutuhan)
saham_syariah = [
    "BBRI.JK", "BRIS.JK", "ADRO.JK", "ANTM.JK", "INCO.JK",
    "MDKA.JK", "TINS.JK", "TLKM.JK", "UNVR.JK", "CPIN.JK"
]

def is_sideways(df, lookback=50, max_range=0.15, slope_tol=0.001):
    """Cek apakah harga sideways"""
    data = df.tail(lookback)
    price_range = (data['Close'].max() - data['Close'].min()) / data['Close'].mean()
    ma50 = data['Close'].rolling(50).mean()
    slope_ma50 = (ma50.iloc[-1] - ma50.iloc[0]) / lookback
    return (price_range <= max_range) and (abs(slope_ma50) < slope_tol)

def is_potential_golden_cross(df, short=20, long=50):
    """Cek apakah MA20 mau golden cross ke MA50"""
    ma_short = df['Close'].rolling(short).mean()
    ma_long = df['Close'].rolling(long).mean()
    
    # kondisi mendekat / sudah cross
    if ma_short.iloc[-1] > ma_long.iloc[-1] and ma_short.iloc[-2] < ma_long.iloc[-2]:
        return "Golden Cross"
    elif ma_short.iloc[-1] < ma_long.iloc[-1] and (ma_short.iloc[-1] - ma_long.iloc[-1]) > -0.01 * ma_long.iloc[-1]:
        return "Potential Golden Cross"
    else:
        return None

results = []

for ticker in saham_syariah:
    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if len(df) < 60:
        continue
    
    sideways = is_sideways(df)
    cross = is_potential_golden_cross(df)
    
    if sideways and cross:
        results.append((ticker, cross))

hasil = pd.DataFrame(results, columns=["Ticker", "Signal"])
print(hasil if not hasil.empty else "Tidak ada kandidat.")