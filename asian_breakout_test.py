import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

def backtest(ticker, name, start="2000-01-01"):
    df = yf.download(ticker, start=start, end=str(date.today()), progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    # Strategy 1: Asian session high/low breakout (daily approximation)
    # Use previous day's high/low
    df["prev_high"] = df["High"].shift(1)
    df["prev_low"] = df["Low"].shift(1)
    signal = np.where(df["Open"] > df["prev_high"], 1,
              np.where(df["Open"] < df["prev_low"], -1, 0))
    df["signal"] = signal
    # returns
    df["log_ret"] = np.log(df["Close"]/df["Close"].shift(1))
    # apply signal: if long, profit = log_ret; if short, profit = -log_ret
    strat_ret = df["signal"] * df["log_ret"]
    # cost: each time signal changes (including zero to nonzero) we incur cost
    turnover = df["signal"].diff().abs().fillna(0)
    cost_bps = 10  # assume 10bps for less liquid Asian
    cost = cost_bps / 10000
    net_ret = strat_ret - turnover * cost
    # cumulative
    cum = (1+net_ret.fillna(0)).cumprod()
    # metrics
    ret_clean = net_ret.dropna()
    ann = 252
    total_ret = cum.iloc[-1] - 1
    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr = (1+total_ret)**(1/years)-1 if years>0 else np.nan
    vol = ret_clean.std()*np.sqrt(ann)
    sharpe = ret_clean.mean()/ret_clean.std()*np.sqrt(ann) if ret_clean.std()!=0 else np.nan
    down = ret_clean[ret_clean<0]
    down_vol = down.std()*np.sqrt(ann) if len(down)>0 else np.nan
    sortino = ret_clean.mean()/down_vol*np.sqrt(ann) if down_vol and down_vol>0 else np.nan
    roll_max = cum.cummax()
    dd = (cum/roll_max - 1).min()
    calmar = -cagr/dd if dd!=0 else np.nan
    print(f"{name} ({ticker}) - Breakout on Open vs Prev High/Low")
    print(f"  CAGR: {cagr:.2%}")
    print(f"  Ann Vol: {vol:.2%}")
    print(f"  Sharpe: {sharpe:.2f}")
    print(f"  Sortino: {sortino:.2f}")
    print(f"  Max DD: {dd:.2%}")
    print(f"  Calmar: {calmar:.2f}")
    print(f"  Total Return: {total_ret:.2%}")
    print(f"  Signals: {(df['signal']!=0).sum()}")
    print(f"  Avg turnover/day: {turnover.mean():.4f}")
    print()
    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "max_dd": dd,
        "total_ret": total_ret
    }

# Test on Nikkei, HSI, KOSPI, DAX, CAC40
tickers = [
    ("^N225", "Nikkei 225"),
    ("^HSI", "Hang Seng"),
    ("^KS11", "KOSPI"),
    ("^FCHI", "CAC40"),
    ("^GDAXI", "DAX")
]
results = {}
for tkr, name in tickers:
    try:
        res = backtest(tkr, name)
        results[name] = res
    except Exception as e:
        print(f"Failed {name}: {e}")