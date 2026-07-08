import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")
ticker = "^N225"
df = yf.download(ticker, start="2000-01-01", end=str(date.today()), progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df[["Open","High","Low","Close","Volume"]].dropna()
df.index = pd.to_datetime(df.index)
df["Date"] = df.index.date
prev_high = df["High"].shift(1)
prev_low  = df["Low"].shift(1)
signal = np.where(df["Open"] > prev_high, 1,
          np.where(df["Open"] < prev_low, -1, 0))
signal = pd.Series(signal, index=df.index).fillna(0)
intra = df["Close"] / df["Open"] - 1
gross = signal * intra
turnover = (signal.diff().abs()).fillna(0)
cost = 5/10000  # 5 bps
net = gross - turnover * cost
print("Net return stats:")
print("Mean:", net.mean())
print("Std:", net.std())
print("Cumulative:", (1+net.fillna(0)).cumprod().iloc[-1])
print("Number of non-zero signals:", (signal!=0).sum())