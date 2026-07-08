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
    data[n] = data[n].reindex(all_dates).ffill()
    data[n]["Date"] = data[n].index.date
# SMA crossover signals
def compute_signal(df):
    # 5-day and 20-day SMA on close
    sma5 = df["Close"].rolling(5).mean()
    sma20 = df["Close"].rolling(20).mean()
    signal = np.where(sma5 > sma20, 1, -1)  # long if short > long, else short
    # we could also stay flat when crossover? but simple
    return pd.Series(signal, index=df.index).fillna(0)
# compute returns given signal
def compute_ret(df, signal):
    intra = df["Close"] / df["Open"] - 1  # intraday return (open to close)
    gross = signal * intra
    turnover = (signal.diff().abs()).fillna(0)
    cost = 5/10000
    net = gross - turnover * cost
    return net
signals = {}
returns = {}
for n,df in data.items():
    sig = compute_signal(df)
    sig.name = n
    signals[n] = sig
    ret = compute_ret(df, sig)
    ret.name = n
    returns[n] = ret
signal_df = pd.DataFrame(signals).fillna(0)
ret_df = pd.DataFrame(returns).fillna(0)
# Equal weight
weights_eq = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
port_eq = (weights_eq * ret_df).sum(axis=1)
# Vol targeting
USE_VOL = True
if USE_VOL:
    vol = ret_df.rolling(63).std() * np.sqrt(252)
    inv_vol = 1.0/vol.replace(0,np.nan)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    port_vol = (raw_w*vol).fillna(0).sum(axis=1)
    TARGET_VOL = 0.15
    scale = (TARGET_VOL/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=2.0)
    weights_v = raw_w.mul(scale, axis=0)
    weights_v = weights_v.div(weights_v.sum(axis=1), axis=0).fillna(0)
    port_v = (weights_v * ret_df).sum(axis=1)
else:
    weights_v = weights_eq
    port_v = port_eq
# compute performance
def perf(ret_series):
    cum = (1+ret_series.fillna(0)).cumprod()
    total = cum.iloc[-1]/cum.iloc[0]-1
    years = (ret_df.index[-1] - ret_df.index[0]).days/365.25
    cagr = (1+total)**(1/years)-1 if years>0 else np.nan
    vol_ann = np.std(ret_slice) * np.sqrt(252)
    compute later
# Let's compute for both
for label, port in [("EQ", port_eq), ("VT", port_v)]:
    cum = (1+port.fillna(0)).cumprod()
    total = cum.iloc[-1]/cum.iloc[0]-1
    years = (ret_df.index[-1] - ret_df.index[0]).days/365.25
    cagr = (1+total)**(1/years)-1 if years>0 else np.nan
    vol = np.std(period) * np.sqrt(252)  # need period variable
    # Let's do explicitly
    import math
    # compute period returns non-nan
    p = port.fillna(0)
    mean_ret = p.mean()
    std_ret = p.std()
    ann_vol = std_ret * np.sqrt(252)
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret!=0 else np.nan
    dd = (cum/cum.cummax()-1).min()
    print(f"{label}: CAGR {cagr:.2%}, Sharpe {sharpe:.2f}, MaxDD {dd:.2%}, Final {cum.iloc[-1]:.2f}")