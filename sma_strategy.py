import pandas as pd
import numpy as np

def sma_signal(df, fast=5, slow=20):
    """
    Returns a Series (+1 long, -1 short) indexed like df.
    Signal based on SMA of Close.
    """
    ma_fast = df["Close"].rolling(fast).mean()
    ma_slow = df["Close"].rolling(slow).mean()
    sig = np.where(ma_fast > ma_slow, 1.0, -1.0)
    return pd.Series(sig, index=df.index).fillna(0.0)

def strategy_return(df, sig, cost_bps=5):
    """
    Compute net return (open-to-close) minus transaction cost.
    df: OHLCV DataFrame
    sig: signal series (+1/-1)
    cost_bps: round‑trip cost in basis points
    """
    intra = df["Close"] / df["Open"] - 1.0          # return from open to close
    gross = sig * intra
    turnover = sig.diff().abs().fillna(0.0)        # |signal_t - signal_{t-1}|
    cost = (cost_bps / 10_000.0) * turnover
    return (gross - cost).fillna(0.0)

def generate_signals_and_returns(data_dict, cost_bps=5, fast=5, slow=20):
    """
    data_dict: dict of {asset_name: DataFrame with OHLCV}
    Returns:
        signals_df: DataFrame of signals (assets as columns)
        returns_df: DataFrame of net returns (assets as columns)
    """
    signals = {}
    returns = {}
    for name, df in data_dict.items():
        sig = sma_signal(df, fast=fast, slow=slow)
        ret = strategy_return(df, sig, cost_bps=cost_bps)
        signals[name] = sig
        returns[name] = ret
    signals_df = pd.DataFrame(signals)
    returns_df = pd.DataFrame(returns)
    return signals_df, returns_df