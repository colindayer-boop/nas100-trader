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

# Signal: SMA 5/20 crossover on close
def get_signal(df):
    ma5 = df["Close"].rolling(5).mean()
    ma20 = df["Close"].rolling(20).mean()
    sig = np.where(ma5 > ma20, 1, -1)   # long when fast > slow
    return pd.Series(sig, index=df.index).fillna(0)

# Return given signal: intraday open-to-close
def get_ret(df, sig):
    intra = df["Close"] / df["Open"] - 1
    gross = sig * intra
    turnover = (sig.diff().abs()).fillna(0)
    cost = 5/10000
    net = gross - turnover * cost
    return net

signal_df = pd.DataFrame({n: get_signal(df) for n,df in data.items()}).fillna(0)
ret_df = pd.DataFrame({n: get_ret(data[n], signal_df[n]) for n in data.keys()}).fillna(0)

# Equal weight portfolio
w_eq = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
port_eq = (w_eq * ret_df).sum(axis=1)

# Volatility targeting (target 15% annual)
USE_VOL = True
if USE_VOL:
    vol = ret_df.rolling(63).std() * np.sqrt(252)         # annualized vol estimate
    inv_vol = 1.0 / vol.replace(0, np.nan)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    port_vol = (raw_w * vol).fillna(0).sum(axis=1)
    target_vol = 0.15
    scale = (target_vol / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=2.0)
    weights = (raw_w * mul(scale, axis=0))
    # Oops: need *. Actually elementwise mul
    weights = raw_w.mul(scale, axis=0)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
else:
    weights = w_eq

port_vol = (weights * ret_df).sum(axis=1)

# Performance function
def perf(port, label):
    cum = (1+port.fillna(0)).cumprod()
    total = cum.iloc[-1]/cum.iloc[0] - 1
    years = (ret_df.index[-1] - ret_df.index[0]).days / 365.25
    cagr = (1+total)**(1/years)-1 if years>0 else np.nan
    # daily returns
    ret = potl = port.fillna(0)
    mean_ret = ret.mean()
    std_ret = ret.std()
    ann_vol = std_ret * np.sqrt(252) if not np.isnan(std_ret) else np.nan
    sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret and std_ret!=0 else np.nan
    dd = (cum/cum.cummax()-1).min()
    print(f"{label}: CAGR {cagr:.2%}, Ann Vol {ann_vol:.2%}, Sharpe {sharpe:.2f}, MaxDD {dd:.2%}")

print("=== Results ===")
perf(port_eq, "Equal Weight")
perf(port_vol, "Vol Target (15%)")