import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")
tickers = ["^N225","^HSI","^KS11","^FCHI","^GDAXI"]
names = ["Nikkei","HangSeng","KOSPI","CAC40","DAX"]
data = {}
for tkr,n in zip(tickers,names):
    df = yf.download(tkr, start="2000-01-01", end=str(date.today()), progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    data[n] = df
# align
all_dates = pd.date_range(start=min(df.index.min() for df in data.values()),
                          end=max(df.index.max() for df in data.values()),
                          freq="B")
for n in data:
    df = data[n].reindex(all_dates).ffill()
    df["Date"] = df.index.date
    data[n] = df
# SMA crossover strategy
def compute_ret(df, fast=5, slow=20):
    close = df["Close"]
    ma_f = close.rolling(fast).mean()
    ma_s = close.rolling(slow).mean()
    signal = np.where(ma_f > ma_s, 1, -1)  # long when fast > slow
    signal = pd.Series(signal, index=df.index).fillna(0)
    # daily log return
    log_ret = np.log(close/close.shift(1))
    gross = signal * log_ret
    turnover = (signal.diff().abs()).fillna(0)
    cost = 5/10000
    net = gross - turnover * cost
    return net
ret_df = pd.DataFrame({n: compute_ret(df) for n,df in data.items()}).fillna(0)
# equal weight
weights = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
port_ret = (weights * ret_df).sum(axis=1)
cum = (1+port_ret).cumprod()
print("SMA Crossover (5/20) equal weight:")
print("Cumulative:", cum.iloc[-1])
print("CAGR:", (cum.iloc[-1]/cum.iloc[0])**(252/len(cum))-1)
print("Mean daily ret:", port_ret.mean())
print("Std:", port_ret.std())
ann = 252
sharpe = (port_ret.mean()/port_ret.std())*np.sqrt(ann) if port_ret.std()!=0 else np.nan
print("Sharpe:", sharpe)
print("Max DD:", (cum/cum.cummax()-1).min())
for n in ret_df.columns:
    r = ret_df[n]
    cum_a = (1+r.fillna(0)).cumprod()
    cagr_a = (cum_a.iloc[-1]/cum_a.iloc[0])**(252/len(cum_a))-1 if len(cum_a)>0 else np.nan
    print(f"{n}: CAGR {cagr_a:.2%}, mean {r.mean():.6f}")