import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

TICKERS = {
    "^N225": "Nikkei",
    "^HSI": "HangSeng",
    "^KS11": "KOSPI",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
}
START = "2000-01-01"
END = str(date.today())
COST_BPS = 5
VOL_LOOKBACK = 63
TARGET_VOL = 0.15

def get_data(tkr):
    df = yf.download(tkr, start=START, end=END, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

raw = {name: get_data(tkr) for tkr, name in TICKERS.items()}
all_bd = pd.date_range(start=min(df.index.min() for df in raw.values()),
                       end=max(df.index.max() for df in raw.values()),
                       freq="B")
data = {}
for name, df in raw.items():
    df = df.reindex(all_bd).ffill()
    df["Date"] = df.index.date
    data[name] = df

def sma_signal(df, fast=5, slow=20):
    mf = df["Close"].rolling(fast).mean()
    ms = df["Close"].rolling(slow).mean()
    return pd.Series(np.where(mf > ms, 1.0, -1.0), index=df.index).fillna(0.0)

def strategy_ret(df, sig, cost_bps=COST_BPS):
    intra = df["Close"] / df["Open"] - 1.0
    gross = sig * intra
    turnover = sig.diff().abs().fillna(0.0)
    cost = (cost_bps / 10_000.0) * turnover
    return (gross - cost).fillna(0.0)

# compute returns per asset
returns = {n: strategy_ret(data[n], sma_signal(data[n])) for n in data}
ret_df = pd.DataFrame(returns)

# walk-forward: annual rebalance of weights (equal weight for simplicity)
# we'll compute rolling 252-day windows, generate weights, apply to next day returns
def walk_forward_returns(ret_df, window=252):
    # equal weight each period (simple)
    weights = pd.DataFrame(1.0/ret_df.shape[1], index=ret_df.index, columns=ret_df.columns)
    port_ret = (weights * ret_df).sum(axis=1)
    return port_ret

port_ret = walk_forward_returns(ret_df)

# performance metrics
def perf(series):
    sr = series.fillna(0)
    cum = (1 + sr).cumprod()
    total = cum.iloc[-1] / cum.iloc[0] - 1
    years = (ret_df.index[-1] - ret_df.index[0]).days / 365.25
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol_ann = sr.std() * np.sqrt(252)
    sharpe = sr.mean() / sr.std() * np.sqrt(252) if sr.std() != 0 else np.nan
    dd = (cum / cum.cummax() - 1).min()
    return cagr, vol_ann, sharpe, dd

cagr, vol, sharpe, dd = perf(port_ret)
print(f"SMA CAGR: {cagr:6.2%}")
print(f"SMA Vol:  {vol:6.2%}")
print(f"SMA Sharpe: {sharpe:5.2f}")
print(f"SMA MaxDD: {dd:6.2%}")
print(f"Average daily turnover: {sma_signal(data[list(data.keys())[0]]).diff().abs().mean():.4f}")