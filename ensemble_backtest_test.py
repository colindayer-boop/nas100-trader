#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test version of ensemble_backtest with debugging prints and limited date range.
"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# USER SETTINGS (shortened for quick test)
# ----------------------------------------------------------------------
TICKERS = {
    "QQQ": "QQQ",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
    "^N225": "NIKKEI",
    "^HSI": "HSI",
    "^KS11": "KOSPI",
}
END_DATE   = str(date.today())
START_DATE = str(date.today() - timedelta(days=2*365))  # ~2 years

COST_BPS = {
    "QQQ": 6,
    "CAC40": 8,
    "DAX": 8,
    "NIKKEI": 10,
    "HSI": 10,
    "KOSPI": 10,
}

TARGET_VOL_ANN = 0.12
VOL_LOOKBACK   = 63
MAX_LEVERAGE   = 2.0
N_SPLITS = 3
PURGE_DAYS = 5

# ----------------------------------------------------------------------
def download_daily(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df

def load_all_data() -> dict:
    data = {}
    for ticker, name in TICKERS.items():
        print(f"Downloading {ticker} ({name}) …")
        data[name] = download_daily(ticker, START_DATE, END_DATE)
    all_dates = pd.date_range(start=min(df.index.min() for df in data.values()),
                              end=max(df.index.max() for df in data.values()),
                              freq="B")
    aligned = {}
    for name, df in data.items():
        df = df.reindex(all_dates).ffill()
        df["Date"] = df.index.date
        aligned[name] = df
    return aligned

def signal_S1(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    asian_low = df["Low"].where((df.index.hour >= 18) | (df.index.hour < 2)).ffill().shift(1)
    signal = np.where(df["Low"] < asian_low, 1,
               np.where(df["Close"] > asian_low.shift(1), -1, 0))
    return pd.Series(signal, index=df.index)

def signal_S2(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    delta = df["Close"].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=False).mean()
    ma_down = down.ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + ma_up / ma_down))
    signal = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))
    return pd.Series(signal, index=df.index)

def signal_S3(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    rng = df["High"] - df["Low"]
    avg_rng = rng.rolling(20).mean()
    breakout = rng > 1.5 * avg_rng
    direction = np.sign(df["Close"] - df["Open"])
    signal = np.where(breakout & (direction > 0), 1,
              np.where(breakout & (direction < 0), -1, 0))
    return pd.Series(signal, index=df.index)

def signal_S4(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    ema_fast = df["Close"].ewm(span=20, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=50, adjust=False).mean()
    signal = np.where(ema_fast > ema_slow, 1,
              np.where(ema_fast < ema_slow, -1, 0))
    return pd.Series(signal, index=df.index)

def signal_S5(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    prev_high = df["High"].shift(1)
    prev_low  = df["Low"].shift(1)
    signal = np.where(df["Open"] > prev_high, 1,
              np.where(df["Open"] < prev_low, -1, 0))
    return pd.Series(signal, index=df.index)

STRATEGY_FUNCS = {
    "S1": signal_S1,
    "S2": signal_S2,
    "S3": signal_S3,
    "S4": signal_S4,
    "S5": signal_S5,
}

def build_net_return_matrix(data: dict) -> pd.DataFrame:
    all_ret = []
    for market, df in data.items():
        ret = np.log(df["Close"] / df["Close"].shift(1)).fillna(0)
        cost_bps = COST_BPS.get(market, 8)
        cost_ret = cost_bps / 10_000
        for strat_name, func in STRATEGY_FUNCS.items():
            sig = func(df).fillna(0)
            turnover = (sig.diff().abs()).fillna(0)
            net = sig * ret - turnover * cost_ret
            col_name = f"{market}_{strat_name}"
            all_ret.append(pd.Series(net, name=col_name, index=df.index))
    return pd.concat(all_ret, axis=1).sort_index()

def vol_target_weights(ret_df: pd.DataFrame,
                       target_vol: float = TARGET_VOL_ANN,
                       lookback: int = VOL_LOOKBACK,
                       max_leverage: float = MAX_LEVERAGE) -> pd.DataFrame:
    vol = ret_df.rolling(lookback).std() * np.sqrt(252)
    inv_vol = 1.0 / vol.replace(0, np.nan)
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    port_vol = (raw_w * vol).fillna(0).sum(axis=1)
    scale = (target_vol / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=max_leverage)
    weights = raw_w.mul(scale, axis=0)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
    return weights

def walk_forward_returns(ret_df: pd.DataFrame,
                         n_splits: int = N_SPLITS,
                         purge_days: int = PURGE_DAYS) -> pd.Series:
    n = len(ret_df)
    split_size = n // n_splits
    equity = [1.0]
    dates = [ret_df.index[0]]
    print(f"Starting walk-forward: n={n}, split_size={split_size}, n_splits={n_splits}")
    for i in range(n_splits):
        train_end = (i + 1) * split_size
        test_start = train_end + purge_days
        test_end   = min((i + 2) * split_size, n)
        if test_start >= n:
            print(f"  Iter {i}: test_start >= n, break")
            break
        print(f"Iter {i}: train [{0}:{train_end}], test [{test_start}:{test_end}]")
        train = ret_df.iloc[:train_end]
        test  = ret_df.iloc[test_start:test_end]
        print(f"  train shape {train.shape}, test shape {test.shape}")
        w = vol_target_weights(train)
        print(f"  weights shape {w.shape}")
        # forward fill weights for test period
        w_test = w.reindex(test.index, method='ffill').fillna(0)
        print(f"  w_test head:\n{w_test.head()}")
        port_ret = (w_test * test).sum(axis=1)
        print(f"  portfolio return mean: {port_ret.mean():.6f}")
        daily_growth = 1 + port_ret
        equity.extend((equity[-1] * daily_growth).tolist())
        dates.extend(test.index.tolist())
        print(f"  equity last: {equity[-1]}")
    eq_series = pd.Series(equity, index=pd.to_datetime(dates))
    print(f"Finishing walk-forward, equity length {len(eq_series)}")
    return eq_series

def perf_metrics(equity: pd.Series, ret_df: pd.DataFrame) -> dict:
    strat_ret = equity.pct_change().fillna(0)
    ann_factor = 252
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else np.nan
    vol_ann = np.sqrt(ann_factor) * strat_ret.std()
    sharpe = (np.sqrt(ann_factor) * strat_ret.mean()) / vol_ann if vol_ann != 0 else np.nan
    downside = strat_ret[strat_ret < 0]
    downside_dev = np.sqrt(ann_factor) * downside.std() if len(downside) > 0 else np.nan
    sortino = (np.sqrt(ann_factor) * strat_ret.mean()) / downside_dev if downside_dev and downside_dev > 0 else np.nan
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    max_dd = drawdown.min()
    calmar = -cagr / max_dd if max_dd != 0 else np.nan
    var_95 = np.percentile(strat_ret, 5)
    cvar_95 = strat_ret[strat_ret <= var_95].mean()
    tail_ratio = np.percentile(strat_ret, 95) / abs(np.percentile(strat_ret, 5)) if np.percentile(strat_ret, 5) != 0 else np.nan
    return {
        "CAGR": f"{cagr:.2%}",
        "Ann. Vol": f"{vol_ann:.2%}",
        "Sharpe": f"{sharpe:.2f}",
        "Sortino": f"{sortino:.2f}",
        "Max DD": f"{max_dd:.2%}",
        "Calmar": f"{calmar:.2f}",
        "VaR 95%": f"{var_95:.4f}",
        "CVaR 95%": f"{cvar_95:.4f}",
        "Tail Ratio": f"{tail_ratio:.2f}" if not np.isnan(tail_ratio) else "NaN",
        "Final Equity": f"{equity.iloc[-1]:.2f} x starting capital",
    }

def main():
    print("=== Loading market data ===")
    data = load_all_data()
    print("=== Building net‑return matrix (signal – cost) ===")
    ret_df = build_net_return_matrix(data)
    print(f"Return matrix shape: {ret_df.shape}")
    print(ret_df.head())
    print("=== Running walk‑forward ensemble ===")
    equity_curve = walk_forward_returns(ret_df)
    print("Equity curve (last 5 values):")
    print(equity_curve.tail())
    print("\n=== Performance Summary ===")
    metrics = perf_metrics(equity_curve, ret_df)
    for k, v in metrics.items():
        print(f"{k:12}: {v}")
    # Optional plot (commented out to avoid GUI issues)
    # plt.figure(figsize=(12,5))
    # plt.plot(equity_curve.index, equity_curve.values, label='Equity')
    # plt.axhline(1.0, color='gray', linestyle='--')
    # plt.title('Equity

    plt.ylabel('Wealth multiplier')
    plt.xlabel('Date')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()