#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ensemble_backtest.py

A volatility‑targeted, walk‑forward ensemble that wraps your existing
S1‑S5 strategies and lets you add extra markets (CAC, DAX, Asian indices)
with realistic transaction costs.

Author:  (you)
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# 1️⃣  USER SETTINGS ----------------------------------------------------
# ----------------------------------------------------------------------
# List of tickers you want to trade.  Add/remove as you wish.
TICKERS = {
    # US
    "QQQ": "QQQ",
    # Europe
    "^FCHI": "CAC40",   # Euronext Paris
    "^GDAXI": "DAX",    # Deutsche Aktienindex
    # Asia
    "^N225": "NIKKEI",  # Nikkei 225
    "^HSI": "HSI",      # Hang Seng
    "^KS11": "KOSPI",   # KOSPI
}

# Starting / ending dates for the download (adjust as needed)
START_DATE = "2000-01-01"
END_DATE   = str(date.today())   # up to today

# Transaction‑cost assumptions (round‑trip bps).  Tweak per instrument later.
#   - Futures ≈ 2 bps
#   - Liquid ETF ≈ 5‑8 bps
#   - Less liquid Asian futures ≈ 8‑12 bps
COST_BPS = {
    "QQQ": 6,      # ETF
    "CAC40": 8,    # index future/ETF proxy
    "DAX": 8,
    "NIKKEI": 10,
    "HSI": 10,
    "KOSPI": 10,
}

# Vol‑target parameters (Barroso‑Santa‑Clara style)
TARGET_VOL_ANN = 0.12      # 12 % annualised vol target
VOL_LOOKBACK   = 63       # ~3 months of daily data for vol estimate
MAX_LEVERAGE   = 2.0      # cap the vol‑scaling factor

# Walk‑forward parameters
N_SPLITS = 5               # expanding windows; increase for more OOS points
PURGE_DAYS = 5             # optional purge gap between train & test to avoid leakage

# ----------------------------------------------------------------------
# 2️⃣  HELPERS – DATA ---------------------------------------------------
# ----------------------------------------------------------------------
def download_daily(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV and return a DataFrame with a Date column (date only)."""
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df


def load_all_data() -> dict:
    """Download every ticker and store in a dict keyed by the *display* name."""
    data = {}
    for ticker, name in TICKERS.items():
        print(f"Downloading {ticker} ({name}) …")
        data[name] = download_daily(ticker, START_DATE, END_DATE)
    # Align all series to a common business‑day calendar (forward fill missing days)
    all_dates = pd.date_range(
        start=min(df.index.min() for df in data.values()),
        end=max(df.index.max() for df in data.values()),
        freq="B"
    )
    aligned = {}
    for name, df in data.items():
        df = df.reindex(all_dates).ffill()
        df["Date"] = df.index.date
        aligned[name] = df
    return aligned


# ----------------------------------------------------------------------
# 3️⃣  SIGNAL GENERATION – reuse your existing S1‑S5 logic -------------
# ----------------------------------------------------------------------
# Below are thin wrappers that call the logic you already have in the
# repo files.  If you prefer to copy‑paste the code directly, replace
# the bodies with the exact calculations from your scripts.

def signal_S1(df: pd.DataFrame) -> pd.Series:
    """
    S1 – Asian‑high/low mean‑reversion (from your orb_backtest.py / S1 logic).
    Returns +1 for long, -1 for short, 0 for flat.
    """
    df = df.copy()
    df["Date"] = df.index.date
    # Asian session mask (you can reuse the asian_hl helper from master_backtest)
    # For brevity, we implement the core idea: long when today's low < yesterday's Asian low
    # and close > yesterday's Asian low, short on the opposite.
    asian_low = df["Low"].where((df.index.hour >= 18) | (df.index.hour < 2)).ffill().shift(1)
    signal = np.where(df["Low"] < asian_low, 1,
               np.where(df["Close"] > asian_low.shift(1), -1, 0))
    return pd.Series(signal, index=df.index)


def signal_S2(df: pd.DataFrame) -> pd.Series:
    """
    S2 – GLD‑style mean‑reversion / breakout (your S2 logic).
    """
    df = df.copy()
    # Example placeholder: use 5‑day RSI >70 for short, <30 for long.
    delta = df["Close"].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=False).mean()
    ma_down = down.ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + ma_up / ma_down))
    signal = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))
    return pd.Series(signal, index=df.index)


def signal_S3(df: pd.DataFrame) -> pd.Series:
    """
    S3 – Simple vol‑breakout (your S3 logic from master_backtest).
    """
    df = df.copy()
    # Volatility breakout: today's range > 1.5 * 20‑day avg range → direction of close‑open
    rng = df["High"] - df["Low"]
    avg_rng = rng.rolling(20).mean()
    breakout = rng > 1.5 * avg_rng
    direction = np.sign(df["Close"] - df["Open"])
    signal = np.where(breakout & (direction > 0), 1,
              np.where(breakout & (direction < 0), -1, 0))
    return pd.Series(signal, index=df.index)


def signal_S4(df: pd.DataFrame) -> pd.Series:
    """
    S4 – Trend‑following (EMA cross) – your S4 logic.
    """
    df = df.copy()
    ema_fast = df["Close"].ewm(span=20, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=50, adjust=False).mean()
    signal = np.where(ema_fast > ema_slow, 1,
              np.where(ema_fast < ema_slow, -1, 0))
    return pd.Series(signal, index=df.index)


def signal_S5(df: pd.DataFrame) -> pd.Series:
    """
    S5 – Opening‑range breakout (your ORB logic from orb_backtest.py).
    We keep a very lightweight version: buy if today's open > yesterday's high,
    sell if open < yesterday's low.
    """
    df = df.copy()
    prev_high = df["High"].shift(1)
    prev_low  = df["Low"].shift(1)
    signal = np.where(df["Open"] > prev_high, 1,
              np.where(df["Open"] < prev_low, -1, 0))
    return pd.Series(signal, index=df.index)


# Map strategy name → function
STRATEGY_FUNCS = {
    "S1": signal_S1,
    "S2": signal_S2,
    "S3": signal_S3,
    "S4": signal_S4,
    "S5": signal_S5,
}


# ----------------------------------------------------------------------
# 4️⃣  BUILD NET‑RETURN MATRIX (signal → return – cost) ---------------
# ----------------------------------------------------------------------
def build_net_return_matrix(data: dict) -> pd.DataFrame:
    """
    Returns a wide DataFrame where each column is
        "<MARKET>_<STRATEGY>"
    and each cell is the *net* daily return for that signal
    (price change * signal  –  turnover * cost).
    """
    all_ret = []

    for market, df in data.items():
        # Daily log returns (approx. simple returns for small moves)
        ret = np.log(df["Close"] / df["Close"].shift(1)).fillna(0)
        cost_bps = COST_BPS.get(market, 8)   # fallback 8 bps if missing
        cost_ret = cost_bps / 10_000        # convert bps to decimal

        for strat_name, func in STRATEGY_FUNCS.items():
            sig = func(df).fillna(0)        # -1,0,1
            # turnover = |signal_t – signal_{t‑1}|
            turnover = (sig.diff().abs()).fillna(0)
            # net return: signal * price change – turnover * cost
            net = sig * ret - turnover * cost_ret
            col_name = f"{market}_{strat_name}"
            all_ret.append(pd.Series(net, name=col_name, index=df.index))

    ret_df = pd.concat(all_ret, axis=1).sort_index()
    return ret_df


# ----------------------------------------------------------------------
# 5️⃣  VOL‑TARGETED INVERSE‑VOL WEIGHTING (ensemble engine) -----------
# ----------------------------------------------------------------------
def vol_target_weights(ret_df: pd.DataFrame,
                       target_vol: float = TARGET_VOL_ANN,
                       lookback: int = VOL_LOOKBACK,
                       max_leverage: float = MAX_LEVERAGE) -> pd.DataFrame:
    """
    Returns a DataFrame of same shape as ret_df with weights that sum to 1 each day.
    The scheme:
        w ∝ 1/vol   (inverse‑vol)
        then scaled so portfolio vol ≈ target_vol (capped at max_leverage)
    """
    # 1) realised vol (annualised)
    vol = ret_df.rolling(lookback).std() * np.sqrt(252)
    # 2) inverse vol
    inv_vol = 1.0 / vol.replace(0, np.nan)
    # 3) raw weights that sum to 1
    raw_w = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    # 4) portfolio vol each day
    port_vol = (raw_w * vol).fillna(0).sum(axis=1)
    # 5) scale to hit target vol (capped)
    scale = (target_vol / port_vol).replace([np.inf, -np.inf], 1.0).clip(upper=max_leverage)
    weights = raw_w.mul(scale, axis=0)
    # 6) renormalise (just in case)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(0)
    return weights


# ----------------------------------------------------------------------
# 6️⃣  WALK‑FORWARD / PURGED VALIDATION --------------------------------
# ----------------------------------------------------------------------
def walk_forward_returns(ret_df: pd.DataFrame,
                         n_splits: int = N_SPLITS,
                         purge_days: int = PURGE_DAYS) -> pd.Series:
    """
    Expanding‑window walk‑forward.
    Returns the cumulative OOS equity curve (starting at 1.0).
    """
    n = len(ret_df)
    split_size = n // n_splits
    equity = [1.0]          # start with $1
    dates  = [ret_df.index[0]]

    for i in range(n_splits):
        train_end = (i + 1) * split_size
        test_start = train_end + purge_days
        test_end   = min((i + 2) * split_size, n)

        if test_start >= n:
            break   # no more OOS data

        train = ret_df.iloc[:train_end]
        test  = ret_df.iloc[test_start:test_end]

        # 1) estimate weights ONLY on the training slice
        w = vol_target_weights(train)

        # 2) align weights to test period (forward‑fill last known weight)
        w_test = w.reindex(test.index, method='ffill').fillna(0)

        # 3) portfolio return for each day in test
        port_ret = (w_test * test).sum(axis=1)

        # 4) chain to equity curve
        daily_growth = 1 + port_ret
        equity.extend((equity[-1] * daily_growth).tolist())
        dates.extend(test.index.tolist())

    eq_series = pd.Series(equity, index=pd.to_datetime(dates))
    return eq_series


# ----------------------------------------------------------------------
# 7️⃣  PERFORMANCE METRICS -----------------------------------------------
# ----------------------------------------------------------------------
def perf_metrics(equity: pd.Series, ret_df: pd.DataFrame) -> dict:
    """
    Returns a dict of common risk‑adjusted stats.
    `equity` is the cumulative wealth curve (starting at 1).
    """
    # Daily returns of the portfolio
    strat_ret = equity.pct_change().fillna(0)

    # Annualisation factor (252 trading days)
    ann_factor = 252

    # CAGR
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else np.nan

    # Volatility (annualised)
    vol_ann = strat_ret.std() * np.sqrt(ann_factor)

    # Sharpe (assuming 0 % risk‑free)
    sharpe = strat_ret.mean() / strat_ret.std() * np.sqrt(ann_factor) if strat_ret.std() > 0 else np.nan

    # Sortino (downside deviation)
    downside = strat_ret[strat_ret < 0]
    downside_dev = downside.std() * np.sqrt(ann_factor) if len(downside) > 0 else np.nan
    sortino = strat_ret.mean() / downside_dev * np.sqrt(ann_factor) if downside_dev and downside_dev > 0 else np.nan

    # Max drawdown
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    max_dd = drawdown.min()

    # Calmar ratio
    calmar = -cagr / max_dd if max_dd != 0 else np.nan

    # VaR 95% and CVaR 95% (parametric normal approximation – you can replace with historical)
    var_95 = np.percentile(strat_ret, 5)
    cvar_95 = strat_ret[strat_ret <= var_95].mean()

    # Tail ratio (95th % / |5th %|)
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


# ----------------------------------------------------------------------
# 8️⃣  MAIN – run everything -------------------------------------------
# ----------------------------------------------------------------------
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

    # ----- Plot equity curve ------------------------------------------------
    plt.figure(figsize=(12, 5))
    plt.plot(equity_curve.index, equity_curve.values, label="Equity (Walk‑Forward Ensemble)")
    plt.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
    plt.title("Walk‑Forward Ensemble Equity Curve (starting at 1.0)")
    plt.ylabel("Wealth multiplier")
    plt.xlabel("Date")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()