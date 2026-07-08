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
for n,df in data.items():
    df = df.reindex(all_dates).ffill()
    df["Date"] = df.index.date
    data[n]=df
# compute net returns
def compute_ret(df):
    prev_high = df["High"].shift(1)
    prev_low  = df["Low"].shift(1)
    signal = np.where(df["Open"] > prev_high, 1,
              np.where(df["Open"] < prev_low, -1, 0))
    signal = pd.Series(signal, index=df.index).fillna(0)
    intra = df["Close"] / df["Open"] - 1
    gross = signal * intra
    turnover = (signal.diff().abs()).fillna(0)
    cost = 5/10000
    net = gross - turnover * cost
    return net
ret_df = pd.DataFrame({n: compute_ret(df) for n,df in data.items()})
# fill first NaN with 0
ret_df = ret_df.fillna(0)
# equal weight
weights = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
port_ret = (weights * ret_df).sum(axis=1)
cum = (1+port_ret).cumprod()
print("Equal weight portfolio:")
print("Cumulative:", cum.iloc[-1])
print("CAGR:", (cum.iloc[-1]/cum.iloc[0])**(252/len(cum))-1)
print("Mean daily ret:", port_ret.mean())
print("Std:", port_ret.std())
# vol target
vol = ret_df.rolling(63).std()*np.sqrt(252)
inv_vol = 1.0/vol.replace(0,np.nan)
raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
port_vol = (raw_w*vol).fillna(0).sum(axis=1)
scale = (0.15/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=2.0)
weights_v = raw_w.mul(scale, axis=0)
weights_v = weights_v.div(weights_v.sum(axis=1), axis=0).fillna(0)
port_ret_v = (weights_v * ret_df).sum(axis=1)
cum_v = (1+port_ret_v).cumprod()
print("\nVol target portfolio:")
print("Cumulative:", cum_v.iloc[-1])
print("CAGR:", (cum_v.iloc[-1]/cum_v.iloc[0])**(252/len(cum_v))-1)
print("Mean daily ret:", port_ret_v.mean())
print("Std:", port_ret_v.std())