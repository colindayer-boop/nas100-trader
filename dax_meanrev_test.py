import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

ticker = "^GDAXI"
df = yf.download(ticker, start="2000-01-01", end=str(date.today()), progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
df = df[["Open","High","Low","Close","Volume"]].dropna()
df.index = pd.to_datetime(df.index)
df["Date"] = df.index.date
# compute log returns
df["log_ret"] = np.log(df["Close"]/df["Close"].shift(1))
# signal: -lag1 if |lag1|>thr
thr = 0.005
df["signal_raw"] = -df["log_ret"].shift(1)
df["signal"] = np.where(df["signal_raw"].abs() > thr, np.sign(df["signal_raw"]), 0)
# shift signal to avoid lookahead: signal at t-1 used for t return? Actually we used lag1 already
# We'll compute next day return using signal at t-1 (already lag1)
df["strategy_ret"] = df["signal"] * df["log_ret"]  # signal * today's log return
# cost: each time signal changes (including zero to nonzero) we incur cost
turnover = df["signal"].diff().abs().fillna(0)
cost_bps = 8  # roundtrip
cost = cost_bps / 10000
df["net_ret"] = df["strategy_ret"] - turnover * cost
# compute cumulative
df["cum"] = (1+df["net_ret"].fillna(0)).cumprod()
# performance metrics
ret = df["net_ret"].dropna()
ann_factor = 252
total_ret = df["cum"].iloc[-1] - 1
years = (df.index[-1] - df.index[0]).days / 365.25
cagr = (1+total_ret)**(1/years)-1 if years>0 else np.nan
vol = ret.std()*np.sqrt(ann_factor)
sharpe = ret.mean()/ret.std()*np.sqrt(ann_factor) if ret.std()!=0 else np.nan
downside = ret[ret<0]
downside_vol = downside.std()*np.sqrt(ann_factor) if len(downside)>0 else np.nan
sortino = ret.mean()/downside_vol*np.sqrt(ann_factor) if downside_vol and downside_vol>0 else np.nan
roll_max = df["cum"].cummax()
dd = (df["cum"]/roll_max - 1).min()
calmar = -cagr/dd if dd!=0 else np.nan
print(f"DAX lag-1 mean-rev (thr={thr*100:.1f}%)")
print(f"CAGR: {cagr:.2%}")
print(f"Ann Vol: {vol:.2%}")
print(f"Sharpe: {sharpe:.2f}")
print(f"Sortino: {sortino:.2f}")
print(f"Max DD: {dd:.2%}")
print(f"Calmar: {calmar:.2f}")
print(f"Total return: {total_ret:.2%}")
print(f"Number of signals: {(df['signal']!=0).sum()}")
print(f"Average turnover per day: {turnover.mean():.4f}")