import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

# ===== PARAMETERS =====
TICKERS = {
    "^N225": "Nikkei",
    "^HSI": "HangSeng",
    "^KS11": "KOSPI",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
}
START_DATE = "2000-01-01"
END_DATE = str(date.today())
COST_BPS = 5          # round‑trip cost per trade (bps)
USE_VOL_TARGET = True
TARGET_VOL_ANN = 0.15 # 15 % annualised vol target
VOL_LOOKBACK = 63     # days for vol estimation

# ===== DATA =====
def get_data(ticker):
    df = yf.download(ticker, start=START_DATE, end=END_DATE,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

raw = {name: get_data(tkr) for tkr, name in TICKERS.items()}
# align to common business‑day calendar
all_bd = pd.date_range(start=min(df.index.min() for df in raw.values()),
                       end=max(df.index.max() for df in raw.values()),
                       freq="B")
data = {}
for name, df in raw.items():
    df = df.reindex(all_bd).ffill()
    df["Date"] = df.index.date
    data[name] = df

# ===== SIGNAL: SMA 5/20 Crossover on Close =====
def sma_signal(df):
    fast = df["Close"].rolling(5).mean()
    slow = df["Close"].rolling(20).mean()
    sig = np.where(fast > slow, 1, -1)   # long when fast > slow
    return pd.Series(sig, index=df.index).fillna(0)

# ===== RETURN: intraday Open‑Close, with transaction cost =====
def strategy_ret(df, sig):
    intra = df["Close"] / df["Open"] - 1          # return from open to close
    gross = sig * intra
    turnover = (sig.diff().abs()).fillna(0)       # |signal_t – signal_{t-1}|
    cost = (COST_BPS / 10_000) * turnover
    net = gross - cost
    return net

signals = {n: sma_signal(df) for n,df in data.items()}
returns = {n: strategy_ret(data[n], sig) for n,sig in signals.items()}

sig_df = pd.DataFrame(signals)
ret_df = pd.DataFrame(returns)

# ===== WEIGHTS =====
# Equal weight baseline
w_eq = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index,
                    columns=ret_df.columns)

# Volatility‑targeted weights (inverse‑vol scaled to target vol)
if USE_VOL_TARGET:
    # Use min_periods=1 to avoid all‑NaN early periods
    vol = ret_df.rolling(VOL_LOOKBACK, min_periods=1).std() * np.sqrt(252)   # annualised vol
    # Avoid division by zero
    vol_adj = vol.replace(0, np.nan)
    inv_vol = 1.0 / vol_adj
    # Replace any remaining inf/ nan with 0 for weighting
    inv_vol = inv_vol.fillna(0)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    # If all weights zero (sum zero), fall back to equal weight for that row
    row_sum = raw_w.sum(axis=1)
    # Replace zero-sum rows with equal weight
    equal_w = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
    # Where row_sum==0, use equal weight
    mask_eq = (row_sum == 0)
    if mask_eq.any():
        raw_w.loc[mask_eq] = equal_w.loc[mask_eq]
    # Normalise
    weights = raw_w.div(weights.sum(axis=1), axis=0).fillna(0)
    # Scale to target vol
    port_vol = (weights * vol).fillna(0).sum(axis=1)
    scale = (TARGET_VOL_ANN / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=2.0)
    weights = weights.mul(scale, axis=0)
    # Renormalise after scaling (optional)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
else:
    weights = w_eq

# Portfolio returns
port_eq = (w_eq * ret_df).sum(axis=1)
port_vt = (weights * ret_df).sum(axis=1) if USE_VOL_TARGET else port_eq

# ===== PERFORMANCE METRICS =====
def perf(series, label):
    sr = series.fillna(0)
    cum = (1 + sr).cumprod()
    total = cum.iloc[-1] / cmum = iloc[0] - 1  # Oops typo

Let's correct: we need compute total.
We'll rewrite perf
<tool_call>
<function=Write>
<parameter=content>
import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

# ===== PARAMETERS =====
TICKERS = {
    "^N225": "Nikkei",
    "^HSI": "HangSeng",
    "^KS11": "KOSPI",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
}
START_DATE = "2000-01-01"
END_DATE = str(date.today())
COST_BPS = 5          # round‑trip cost per trade (bps)
USE_VOL_TARGET = True
TARGET_VOL_ANN = 0.15 # 15 % annualised vol target
VOL_LOOKBACK = 63     # days for vol estimation

# ===== DATA =====
def get_data(ticker):
    df = yf.download(ticker, start=START_DATE, end=END_DATE,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

raw = {name: get_data(tkr) for tkr, name in TICKERS.items()}
# align to common business‑day calendar
all_bd = pd.date_range(start=min(df.index.min() for df in raw.values()),
                       end=max(df.index.max() for df in raw.values()),
                       freq="B")
data = {}
for name, df in raw.items():
    df = df.reindex(all_bd).ffill()
    df["Date"] = df.index.date
    data[name] = df

# ===== SIGNAL: SMA 5/20 Crossover on Close =====
def sma_signal(df):
    fast = df["Close"].rolling(5).mean()
    slow = df["Close"].rolling(20).mean()
    sig = np.where(fast > slow, 1, -1)   # long when fast > slow
    return pd.Series(sig, index=df.index).fillna(0)

# ===== RETURN: intraday Open‑Close, with transaction cost =====
def strategy_ret(df, sig):
    intra = df["Close"] / df["Open"] - 1          # return from open to close
    gross = sig * intra
    turnover = (sig.diff().abs()).fillna(0)       # |signal_t – signal_{t-1}|
    cost = (COST_BPS / 10_000) * turnover
    net = gross - cost
    return net

signals = {n: sma_signal(df) for n,df in data.items()}
returns = {n: strategy_ret(data[n], sig) for n,sig in signals.items()}

sig_df = pd.DataFrame(signals)
ret_df = pd.DataFrame(returns)

# ===== WEIGHTS =====
# Equal weight baseline
w_eq = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index,
                    columns=ret_df.columns)

# Volatility‑targeted weights (inverse‑vol scaled to target vol)
if USE_VOL_TARGET:
    # Use min_periods=1 to avoid all‑NaN early periods
    vol = ret_df.rolling(VOL_LOOKBACK, min_periods=1).std() * np.sqrt(252)   # annualised vol
    # Replace zeros with small number to avoid division by zero
    vol_adj = vol.replace(0, np.nan)
    inv_vol = 1.0 / vol_adj
    # Fill any resulting NaN/Inf with 0
    inv_vol = inv_vol.fillna(0)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    # For rows where sum is zero (all zero), use equal weight
    row_sum = raw_w.sum(axis=1)
    equal_w = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
    mask_zero = (row_sum == 0)
    if mask_zero.any():
        raw_w.loc[mask_zero] = equal_w.loc[mask_zero]
    # Normalise to sum 1
    weights = raw_w.div(weights.sum(axis=1), axis=0).fillna(0)
    # Scale to target vol
    port_vol = (weights * vol).fillna(0).sum(axis=1)
    scale = (TARGET_VOL_ANN / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=2.0)
    weights = (weights.mul(scale, axis=0))
    # Renormalise after scaling
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
else:
    weights = w_eq

# Portfolio returns
port_eq = (w_eq * ret_df).sum(axis=1)
port_vt = (weights * ret_df).sum(axis=1) if USE_VOL_TARGET else port_eq

# ===== PERFORMANCE METRICS =====
def perf(series, label):
    sr = series.fillna(0)
    cum = (1 + sr).cumprod()
    total = cum.iloc[-1] / cum.iloc[0] - 1
    years = (ret_df.index[-1] - ret_df.index[0]).days / 365.25
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol_ann = sr.std() * np.sqrt(252)
    sharpe = sr.mean() / sr.std() * np.sqrt(252) if sr.std() != 0 else np.nan
    dd = (cum / cum.cummax() - 1).min()
    print(f"{label:12} | CAGR: {cagr:6.2%} | Vol: {vol_an:5.2%} | Sharpe: {sharpe:5.2f} | MaxDD: {dd:6.2%}")

print("\n=== Performance ===")
print("Strategy   | CAGR   | Vol   | Sharpe | MaxDD")
print("-"*55)
perf(port_eq, "EqualW")
if USE_VOL_TARGET:
    perf("VolTgt")  # missing argument

We need to fix the last call.
Let's just write final correct script now and run.


<tool_call>
<function=Write>
<parameter=content>
import warnings, yfinance as yf, numpy as np, pandas as pd
from datetime import date
warnings.filterwarnings("ignore")

# ===== PARAMETERS =====
TICKERS = {
    "^N225": "Nikkei",
    "^HSI": "HangSeng",
    "^KS11": "KOSPI",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
}
START_DATE = "2000-01-01"
END_DATE = str(date.today())
COST_BPS = 5          # round‑trip cost per trade (bps)
USE_VOL_TARGET = True
TARGET_VOL_ANN = 0.15 # 15 % annualised vol target
VOL_LOOKBACK = 63     # days for vol estimation

# ===== DATA =====
def get_data(ticker):
    df = yf.download(ticker, start=START_DATE, end=END_DATE,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

raw = {name: get_data(tkr) for tkr, name in TICKERS.items()}
# align to common business‑day calendar
all_bd = pd.date_range(start=min(df.index.min() for df in raw.values()),
                       end=max(df.index.max() for df in raw.values()),
                       freq="B")
data = {}
for name, df in raw.items():
    df = df.reindex(all_bd).ffill()
    df["Date"] = df.index.date
    data[name] = df

# ===== SIGNAL: SMA 5/20 Crossover on Close =====
def sma_signal(df):
    fast = df["Close"].rolling(5).mean()
    slow = df["Close"].rolling(20).mean()
    sig = np.where(fast > slow, 1, -1)   # long when fast > slow
    return pd.Series(sig, index=df.index).fillna(0)

# ===== RETURN: intraday Open‑Close, with transaction cost =====
def strategy_ret(df, sig):
    intra = df["Close"] / df["Open"] - 1          # return from open to close
    gross = sig * intra
    turnover = (sig.diff().abs()).fillna(0)       # |signal_t – signal_{t-1}|
    cost = (COST_BPS / 10_000) * turnover
    net = gross - cost
    return net

signals = {n: sma_signal(df) for n,df in data.items()}
returns = {n: strategy_ret(data[n], sig) for n,sig in signals.items()}

sig_df = pd.DataFrame(signals)
ret_df = pd.DataFrame(returns)

# ===== WEIGHTS =====
# Equal weight baseline
w_eq = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index,
                    columns=ret_df.columns)

# Volatility‑targeted weights (inverse‑vol scaled to target vol)
if USE_VOL_TARGET:
    # Use min_periods=1 to avoid all‑NaN early periods
    vol = ret_df.rolling(VOL_LOOKBACK, min_periods=1).std() * np.sqrt(252)   # annualised vol
    # Replace zeros with small number to avoid division by zero
    vol_adj = vol.replace(0, np.nan)
    inv_vol = 1.0 / vol_adj
    # Fill any resulting NaN/Inf with 0
    inv_vol = inv_vol.fillna(0)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    # For rows where sum is zero (all zero), use equal weight
    row_sum = raw_w.sum(axis=1)
    equal_w = pd.DataFrame(1.0/len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)
    mask_zero = (row_sum == 0)
    if mask_zero.any():
        raw_w.loc[mask_zero] = equal_w.loc[mask_zero]
    # Normalise to sum 1
    weights = raw_w.div(weights.sum(axis=1), axis=0).fillna(0)
    # Scale to target vol
    port_vol = (weights * vol).fillna(0).sum(axis=1)
    scale = (TARGET_VOL_ANN / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=2.0)
    weights = weights.mul(scale, axis=0)
    # Renormalise after scaling
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
else:
    weights = w_eq

# Portfolio returns
port_eq = (w_eq * ret_df).sum(axis=1)
port_vt = (weights * ret_df).sum(axis=1) if USE_VOL_TARGET else None

# ===== PERFORMANCE METRICS =====
def perf(series, label):
    sr = series.fillna(0)
    cum = (1 + sr).cumprod()
    total = cum.iloc[-1] / cum.iloc[0] - 1
    years = (ret_df.index[-1] - ret_df.index[0]).days / 365.25
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    vol_ann = sr.std() * np.sqrt(252)
    sharpe = sr.mean() / sr.std() * np.sqrt(252) if sr.std() != 0 else np.nan
    dd = (cum / cum.cummax() - 1).min()
    print(f"{label:12} | CAGR: {cagr:6.2%} | Vol: {vol_an:5.2%} | Sharpe: {sharpe:5.2f} | MaxDD: {dd:6.2%}")

print("\n=== Performance ===")
print("Strategy   | CAGR   | Vol   | Sharpe | MaxDD")
print("-"*55)
perf(port_eq, "EqualW")
if USE_VOL_TARGET:
    perf(port_vt, "VolTgt")

# Show signal stats
print("\nSignal stats (average over assets):")
avg_trade = (sig_df.diff().abs()).mean().mean()
print(f"Average absolute signal change per day ( turnover proxy ): {avg_trade:.4f}")