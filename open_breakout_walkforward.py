#!/usr/bin/env python
# -*- coding: utf-8 -*-
import warnings, numpy as np, pandas as pd, yfinance as yf
from datetime import date, timedelta
warnings.filterwarnings("ignore")

# Parameters
TICKERS = {
    "^N225": "Nikkei",
    "^HSI": "HangSeng",
    "^KS11": "KOSPI",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
}
START_DATE = "2000-01-01"
END_DATE   = str(date.today())
COST_BPS = 5   # round-trip cost in bps per trade (adjustable)
# Lookback for vol targeting (optional)
USE_VOL_TARGET = True
TARGET_VOL = 0.15
VOL_LB = 63

def fetch(ticker):
    df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

data = {name: fetch(tkr) for tkr, name in TICKERS.items()}
# align on business days
all_dates = pd.date_range(start=min(df.index.min() for df in data.values()),
                          end=max(df.index.max() for df in data.values()),
                          freq="B")
for name, df in data.items():
    df = df.reindex(all_dates).ffill()
    df["Date"] = df.index.date
    data[name] = df

# compute signals and returns
def compute_ret(df):
    # signal: long if open > prev high, short if open < prev low
    prev_high = df["High"].shift(1)
    prev_low  = df["Low"].shift(1)
    signal = np.where(df["Open"] > prev_high, 1,
              np.where(df["Open"] < prev_low, -1, 0))
    signal = pd.Series(signal, index=df.index).fillna(0)
    # intraday return: close/open - 1
    intra_ret = df["Close"] / df["Open"] - 1
    gross = signal * intra_ret
    turnover = (signal.diff().abs()).fillna(0)
    cost = turnover * (COST_BPS / 10000)
    net = gross - cost
    return net, signal, turnover

returns = {}
signals = {}
turnovers = {}
for name, df in data.items():
    net, sig, turn = compute_ret(df)
    returns[name] = net
    signals[name] = sig
    turnovers[name] = turn

# Build DataFrame
ret_df = pd.DataFrame(returns)
signal_df = pd.DataFrame(signals)
turnover_df = pd.DataFrame(turnovers)

# Optional volatility targeting weights
if USE_VOL_TARGET:
    vol = ret_df.rolling(VOL_LB).std() * np.sqrt(252)
    inv_vol = 1.0 / vol.replace(0, np.nan)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=1)
    port_vol = (raw_w * vol).fillna(0).sum(axis=1)
    scale = (TARGET_VOL / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=2.0)
    weights = raw_w.mul(scale, axis=0)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
else:
    # equal weight
    weights = pd.DataFrame(1.0 / len(ret_df.columns), index=ret_df.index, columns=ret_df.columns)

# Portfolio returns
port_ret = (weights * ret_df).sum(axis=1)

# Performance
cum = (1 + port_ret).cumprod()
total_return = cum.iloc[-1] / cum.iloc[0] - 1
years = (ret_df.index[-1] - ret_df.index[0]).days / 365.25
cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else np.nan
vol_ann = np.std(port_ret) * np.sqrt(252)
sharpe = np.mean(port_ret) / np.std(port_ret) * np.sqrt(252) if np.std(port_ret) != 0 else np.nan
downside = port_ret[port_ret < 0]
downside_dev = np.std(downside) * np.sqrt(252) if len(downside) > 0 else np.nan
sortino = np.mean(port_ret) / downside_dev * np.sqrt(252) if downside_dev and downside_dev > 0 else np.nan
roll_max = cum.cummax()
max_dd = (cum / roll_max - 1).min()
calmar = -cagr / max_dd if max_dd != 0 else np.nan

print("=== Walk‑forward equal‑weight (or vol‑target) Open‑Breakout Strategy ===")
print(f"Markets: {list(TICKERS.values())}")
print(f"Cost per trade: {COST_BPS} bps")
print(f"Vol targeting: {USE_VOL_TARGET} (target vol={TARGET_VOL if USE_VOL_TARGET else 'N/A'})")
print(f"CAGR: {cagr:.2%}")
print(f"Annualized Vol: {vol_ann:.2%}")
print(f"Sharpe: {sharpe:.2f}")
print(f"Sortino: {sortino:.2f}")
print(f"Max Drawdown: {max_dd:.2%}")
print(f"Calmar: {calmar:.2f}")
print(f"Total Return: {total_return:.2%}")
print(f"Number of trading days: {len(ret_df)}")
print(f"Average daily turnover (abs signal change): {turnover_df.values.mean():.4f}")