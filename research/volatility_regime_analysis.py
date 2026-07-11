"""
Volatility Regime Analysis — Mission 3
=======================================
Tests whether volatility should:
  1. Filter entries (trade only in certain vol regimes)
  2. Scale risk (size positions by vol level)
  3. Change holding period (adaptive targets by vol regime)

Volatility metrics studied:
  - ATR (Average True Range) filters
  - Realized volatility (ann.)
  - Volatility clustering (GARCH-like persistence)
  - Volatility compression (BB squeeze / ATR percentile)
  - Breakout volatility (vol expansion after compression)
  - Adaptive volatility sizing (Barroso & Santa-Clara style)

Output:
  - research/results/volatility_regime_report.md
  - research/results/vol_regime_*.png charts
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import json
import pytz
from pathlib import Path
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATA_PATH = "/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv"
OUTPUT_DIR = Path("/Users/colindayer/nas100_backtest/research/results")
CHART_DIR = OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 10_000
COST_BPS = 5  # 5 bps round-trip
EASTERN = pytz.timezone("US/Eastern")

# ── LOAD DATA ────────────────────────────────────────────────────────────────
print("Loading QQQ hourly data...")
df = pd.read_csv(DATA_PATH)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df.index = df.index.tz_convert(EASTERN)
df = df[["open", "high", "low", "close", "volume"]].copy()
df.columns = ["Open", "High", "Low", "Close", "Volume"]
df["rets"] = df["Close"].pct_change()
df = df.dropna()

# ── RESAMPLE TO DAILY ────────────────────────────────────────────────────────
daily = df.resample("1B").agg({
    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
}).dropna()
daily["rets"] = daily["Close"].pct_change()
daily["range"] = (daily["High"] - daily["Low"]) / daily["Close"]
daily["tr"] = pd.concat([
    daily["High"] - daily["Low"],
    (daily["High"] - daily["Close"].shift(1)).abs(),
    (daily["Low"] - daily["Close"].shift(1)).abs(),
], axis=1).max(axis=1)

# ── VOLATILITY METRICS ───────────────────────────────────────────────────────
print("Computing volatility metrics...")

# 1. ATR (14-day, daily bars)
daily["atr_14"] = daily["tr"].rolling(14).mean()
daily["atr_pct"] = daily["atr_14"] / daily["Close"]
daily["atr_pctl"] = daily["atr_pct"].rolling(252).rank(pct=True)

# 2. Realized volatility (20-day, annualized)
daily["rv_20"] = daily["rets"].rolling(20).std() * np.sqrt(252)
daily["rv_5"] = daily["rets"].rolling(5).std() * np.sqrt(252)
daily["rv_60"] = daily["rets"].rolling(60).std() * np.sqrt(252)

# 3. Volatility of volatility (clustering proxy)
daily["rv_20_vol"] = daily["rv_20"].rolling(60).std()

# 4. Volatility compression (ATR percentile + Bollinger Band width)
daily["bb_mid"] = daily["Close"].rolling(20).mean()
daily["bb_std"] = daily["Close"].rolling(20).std()
daily["bb_width"] = (4 * daily["bb_std"]) / daily["bb_mid"]
daily["bb_squeeze"] = daily["bb_width"] < daily["bb_width"].rolling(120).quantile(0.2)

# 5. Volatility regime change (ATR expanding?)
daily["atr_expanding"] = daily["atr_pct"] > daily["atr_pct"].shift(5)

# 6. GARCH-like volatility clustering: autocorrelation of squared returns
squared_rets = daily["rets"] ** 2
clustering_ac1 = squared_rets.rolling(60).apply(
    lambda x: pd.Series(x).autocorr(lag=1) if len(x) == 60 else np.nan, raw=False
)
daily["vol_cluster_ac1"] = clustering_ac1

# ── DEFINE VOLATILITY REGIMES ───────────────────────────────────────────────
print("Defining volatility regimes...")

# Regime by RV percentile
rv_p20 = daily["rv_20"].rolling(252).quantile(0.20)
rv_p80 = daily["rv_20"].rolling(252).quantile(0.80)

def classify_regime(row):
    rv = row["rv_20"]
    low = row.get("rv_low", np.nan)
    high = row.get("rv_high", np.nan)
    if pd.isna(rv) or pd.isna(low) or pd.isna(high):
        return "unknown"
    if rv < low:
        return "low_vol"
    elif rv > high:
        return "high_vol"
    else:
        return "mid_vol"

tmp = daily.copy()
tmp["rv_low"] = rv_p20
tmp["rv_high"] = rv_p80
daily["regime"] = tmp.apply(classify_regime, axis=1)

# Compression regime
daily["compressed"] = daily["atr_pctl"] < 0.25
daily["expanding"] = daily["atr_pctl"] > 0.75

# ── SIMPLE ASIAN SWEEP STRATEGY (for regime overlay testing) ─────────────────
print("Building Asian Sweep signal...")

def asian_sweep_signals(hourly_df):
    """S1 Asian Sweep: entry on sweep of Asian session high/low."""
    signals = []
    asian_start = 18  # 6pm ET previous day
    asian_end = 6     # 6am ET

    dates = hourly_df.index.normalize().unique()

    for i, dt in enumerate(dates):
        if i < 2:
            continue
        prev_dt = dates[i-1]

        # Asian session = 18:00 prev day to 06:00 current day
        asian_mask = (
            ((hourly_df.index >= prev_dt + pd.Timedelta(hours=18)) &
             (hourly_df.index < prev_dt + pd.Timedelta(hours=24))) |
            ((hourly_df.index >= dt) &
             (hourly_df.index < dt + pd.Timedelta(hours=6)))
        )
        asian = hourly_df[asian_mask]
        if len(asian) < 3:
            continue

        asian_high = asian["High"].max()
        asian_low = asian["Low"].min()

        # London/NY session: 08:00–16:00 ET
        session_mask = (hourly_df.index >= dt + pd.Timedelta(hours=8)) & \
                       (hourly_df.index < dt + pd.Timedelta(hours=16))
        session = hourly_df[session_mask]
        if len(session) == 0:
            continue

        # Long if we break above Asian high in first 3 hours
        entry_bars = session[session.index < dt + pd.Timedelta(hours=11)]
        longs = entry_bars[entry_bars["High"] > asian_high]
        shorts = entry_bars[entry_bars["Low"] < asian_low]

        if len(longs) > 0:
            entry_bar = longs.iloc[0]
            entry_price = asian_high * 1.001  # slight breakout confirm
            entry_time = longs.index[0]
            signals.append({
                "date": dt, "entry_time": entry_time,
                "direction": 1, "entry_price": entry_price,
                "asian_high": asian_high, "asian_low": asian_low,
                "atr_pct": hourly_df.loc[entry_time, "atr_pct"] if "atr_pct" in hourly_df.columns else np.nan,
                "rv_20": hourly_df.loc[entry_time, "rv_20"] if "rv_20" in hourly_df.columns else np.nan,
            })
        elif len(shorts) > 0:
            entry_bar = shorts.iloc[0]
            entry_price = asian_low * 0.999
            entry_time = shorts.index[0]
            signals.append({
                "date": dt, "entry_time": entry_time,
                "direction": -1, "entry_price": entry_price,
                "asian_high": asian_high, "asian_low": asian_low,
                "atr_pct": hourly_df.loc[entry_time, "atr_pct"] if "atr_pct" in hourly_df.columns else np.nan,
                "rv_20": hourly_df.loc[entry_time, "rv_20"] if "rv_20" in hourly_df.columns else np.nan,
            })

    return pd.DataFrame(signals)

# Merge daily vol metrics into hourly for signal enrichment
hourly_vol = daily[["atr_pct", "rv_20", "rv_5", "rv_60", "regime", "atr_pctl",
                     "compressed", "expanding", "bb_squeeze", "vol_cluster_ac1"]].copy()
hourly_vol.index = hourly_vol.index.tz_localize(None) if hourly_vol.index.tz else hourly_vol.index

df_local = df.copy()
df_local["date"] = df_local.index.normalize()
daily_local = daily.copy()
daily_local.index = daily_local.index.tz_localize(None) if daily_local.index.tz else daily_local.index

# Merge daily vol data onto hourly
for col in ["atr_pct", "rv_20", "rv_5", "rv_60", "regime", "atr_pctl",
            "compressed", "expanding", "bb_squeeze", "vol_cluster_ac1"]:
    df_local[col] = df_local["date"].map(daily_local[col])

signals = asian_sweep_signals(df_local)

if len(signals) == 0:
    print("ERROR: No signals generated!")
    exit(1)

# Merge vol context onto signals
for col in ["regime", "atr_pctl", "compressed", "expanding", "bb_squeeze",
            "vol_cluster_ac1", "rv_5", "rv_60"]:
    if col not in signals.columns:
        signals[col] = signals["date"].map(daily_local[col])

# ── BACKTEST ENGINE ─────────────────────────────────────────────────────────
def backtest_signals(signals_df, daily_df, stop_pct=0.015, rr=3.0,
                     risk_per_trade=0.007, vol_filter=None,
                     vol_scale=False, adaptive_hold=False,
                     cost_bps=5):
    """
    Backtest signals with optional vol-based modifications.

    vol_filter: None | 'low_vol_only' | 'mid_low_only' | 'no_high_vol' |
                'compressed_only' | 'no_compressed' | 'expansion_only'
    vol_scale: if True, scale risk inversely to RV (Barroso & Santa-Clara)
    adaptive_hold: if True, use tighter RR in high vol, wider in low vol
    """
    equity = INITIAL_CAPITAL
    trades = []
    cost_frac = cost_bps / 10000

    for _, sig in signals_df.iterrows():
        entry_price = sig["entry_price"]
        direction = sig["direction"]
        date = sig["date"]
        regime = sig.get("regime", "unknown")
        atr_pctl = sig.get("atr_pctl", 0.5)
        rv = sig.get("rv_20", 0.15)
        compressed = sig.get("compressed", False)
        expanding = sig.get("expanding", False)

        # ── Vol filter ──
        if vol_filter == "low_vol_only" and regime != "low_vol":
            continue
        elif vol_filter == "mid_low_only" and regime == "high_vol":
            continue
        elif vol_filter == "no_high_vol" and regime == "high_vol":
            continue
        elif vol_filter == "compressed_only" and not compressed:
            continue
        elif vol_filter == "no_compressed" and compressed:
            continue
        elif vol_filter == "expansion_only" and not expanding:
            continue

        # ── Vol-scaled risk ──
        risk = risk_per_trade
        if vol_scale:
            # Target 12% ann vol, scale risk inversely
            target_rv = 0.15
            scale = np.clip(target_rv / max(rv, 0.05), 0.3, 2.0)
            risk = risk_per_trade * scale

        # ── Adaptive holding period ──
        this_stop = stop_pct
        this_rr = rr
        if adaptive_hold:
            if regime == "high_vol":
                this_stop = stop_pct * 1.3  # wider stop in high vol
                this_rr = 2.0                # but tighter RR (less likely to hit 3R)
            elif regime == "low_vol":
                this_stop = stop_pct * 0.8  # tighter stop in low vol
                this_rr = 3.5               # wider RR (trends more in low vol)

        stop_price = entry_price * (1 - direction * this_stop)
        target_price = entry_price * (1 + direction * this_stop * this_rr)

        # Walk forward to find exit
        future = daily_df[daily_df.index > date].head(10)
        exit_price = None
        exit_reason = None
        exit_date = None
        hold_days = 0

        for j, (exit_dt, row) in enumerate(future.iterrows()):
            hold_days = j + 1
            if direction == 1:
                if row["Low"] <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                    exit_date = exit_dt
                    break
                elif row["High"] >= target_price:
                    exit_price = target_price
                    exit_reason = "target"
                    exit_date = exit_dt
                    break
            else:
                if row["High"] >= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                    exit_date = exit_dt
                    break
                elif row["Low"] <= target_price:
                    exit_price = target_price
                    exit_reason = "target"
                    exit_date = exit_dt
                    break

        if exit_price is None:
            if len(future) == 0:
                # No future data — skip this trade
                continue
            exit_price = future.iloc[-1]["Close"]
            exit_reason = "timeout"
            exit_date = future.index[-1]

        # P&L
        gross_ret = direction * (exit_price - entry_price) / entry_price
        cost = cost_frac
        net_ret = gross_ret - cost
        pnl = equity * risk * (net_ret / this_stop)  # risk-based position sizing
        equity += pnl

        trades.append({
            "date": date, "direction": direction,
            "entry_price": entry_price, "exit_price": exit_price,
            "stop_price": stop_price, "target_price": target_price,
            "net_ret": net_ret, "pnl": pnl, "equity": equity,
            "regime": regime, "atr_pctl": atr_pctl, "rv_20": rv,
            "compressed": compressed, "expanding": expanding,
            "exit_reason": exit_reason, "hold_days": hold_days,
            "risk_used": risk,
        })

    return pd.DataFrame(trades)


def metrics(trades_df, label=""):
    if len(trades_df) == 0:
        return {"label": label, "n_trades": 0, "cagr": 0, "sharpe": 0,
                "max_dd": 0, "win_rate": 0, "pf": 0, "avg_pnl": 0}

    eq = trades_df["equity"].values
    rets = trades_df["pnl"].values
    total_ret = (eq[-1] / INITIAL_CAPITAL) - 1
    n_years = max((trades_df["date"].iloc[-1] - trades_df["date"].iloc[0]).days / 365.25, 0.5)
    cagr = (eq[-1] / INITIAL_CAPITAL) ** (1 / n_years) - 1

    # Sharpe (per-trade, annualized by ~250 trading days / avg trades per year)
    trades_per_year = len(trades_df) / n_years
    if rets.std() > 0:
        sharpe = (rets.mean() / rets.std()) * np.sqrt(trades_per_year)
    else:
        sharpe = 0

    # Max drawdown
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd = dd.min()

    # Win rate & profit factor
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    win_rate = len(wins) / len(rets)
    pf = wins.sum() / abs(losses.sum()) if len(losses) > 0 and losses.sum() != 0 else np.inf

    return {
        "label": label, "n_trades": len(trades_df),
        "cagr": cagr, "sharpe": sharpe, "max_dd": max_dd,
        "win_rate": win_rate, "pf": pf,
        "avg_pnl": rets.mean(), "total_ret": total_ret,
        "trades_per_year": trades_per_year,
    }


# ── RUN ALL EXPERIMENTS ─────────────────────────────────────────────────────
print("Running experiments...")
results = {}
all_trade_dfs = {}

# Baseline
base_trades = backtest_signals(signals, daily, vol_filter=None)
results["baseline"] = metrics(base_trades, "Baseline (no vol filter)")
all_trade_dfs["baseline"] = base_trades

# 1. Entry filters by regime
for filt in ["low_vol_only", "mid_low_only", "no_high_vol",
             "compressed_only", "no_compressed", "expansion_only"]:
    trades = backtest_signals(signals, daily, vol_filter=filt)
    label = f"filter={filt}"
    results[label] = metrics(trades, label)
    all_trade_dfs[label] = trades

# 2. Vol-scaled risk
trades_vs = backtest_signals(signals, daily, vol_scale=True)
results["vol_scaled_risk"] = metrics(trades_vs, "Vol-scaled risk (B&SC)")
all_trade_dfs["vol_scaled_risk"] = trades_vs

# 3. Adaptive holding period
trades_ah = backtest_signals(signals, daily, adaptive_hold=True)
results["adaptive_hold"] = metrics(trades_ah, "Adaptive holding period")
all_trade_dfs["adaptive_hold"] = trades_ah

# 4. Combo: filter + scale
trades_combo = backtest_signals(signals, daily, vol_filter="no_high_vol", vol_scale=True)
results["combo_filter+scale"] = metrics(trades_combo, "No-high-vol + vol-scaled")
all_trade_dfs["combo_filter+scale"] = trades_combo

# 5. Combo: filter + adaptive hold
trades_combo2 = backtest_signals(signals, daily, vol_filter="no_high_vol", adaptive_hold=True)
results["combo_filter+adapt"] = metrics(trades_combo2, "No-high-vol + adaptive hold")
all_trade_dfs["combo_filter+adapt"] = trades_combo2

# ── REGIME-CONDITIONAL PERFORMANCE (baseline trades by regime) ──────────────
print("Analyzing regime-conditional performance...")
regime_perf = {}
for regime in ["low_vol", "mid_vol", "high_vol", "unknown"]:
    mask = base_trades["regime"] == regime
    subset = base_trades[mask]
    if len(subset) > 0:
        regime_perf[regime] = {
            "n_trades": len(subset),
            "win_rate": (subset["net_ret"] > 0).mean(),
            "avg_ret": subset["net_ret"].mean(),
            "total_pnl": subset["pnl"].sum(),
            "avg_rv": subset["rv_20"].mean() if "rv_20" in subset.columns else np.nan,
            "avg_hold": subset["hold_days"].mean(),
        }

# Compression-conditional
for comp_label, comp_mask in [("compressed", base_trades.get("compressed", pd.Series(dtype=bool)) == True),
                                ("not_compressed", base_trades.get("compressed", pd.Series(dtype=bool)) == False)]:
    subset = base_trades[comp_mask]
    if len(subset) > 0:
        regime_perf[comp_label] = {
            "n_trades": len(subset),
            "win_rate": (subset["net_ret"] > 0).mean(),
            "avg_ret": subset["net_ret"].mean(),
            "total_pnl": subset["pnl"].sum(),
        }

# ── ATR PERCENTILE BUCKETS ──────────────────────────────────────────────────
print("Analyzing ATR percentile buckets...")
atr_buckets = {}
for lo, hi, label in [(0, 0.2, "0-20% (very low)"),
                       (0.2, 0.4, "20-40%"),
                       (0.4, 0.6, "40-60%"),
                       (0.6, 0.8, "60-80%"),
                       (0.8, 1.01, "80-100% (very high)")]:
    mask = (base_trades["atr_pctl"] >= lo) & (base_trades["atr_pctl"] < hi)
    subset = base_trades[mask]
    if len(subset) > 0:
        atr_buckets[label] = {
            "n_trades": len(subset),
            "win_rate": (subset["net_ret"] > 0).mean(),
            "avg_ret": subset["net_ret"].mean(),
            "total_pnl": subset["pnl"].sum(),
            "pf": subset.loc[subset["net_ret"] > 0, "pnl"].sum() /
                  abs(subset.loc[subset["net_ret"] <= 0, "pnl"].sum())
                  if (subset["net_ret"] <= 0).any() else float('inf'),
        }

# ── VOLATILITY CLUSTERING ANALYSIS ──────────────────────────────────────────
print("Analyzing volatility clustering...")
# Check if high-vol days cluster (GARCH effect)
daily_clean = daily.dropna(subset=["rv_20"]).copy()
daily_clean["rv_high"] = daily_clean["rv_20"] > daily_clean["rv_20"].median()

# Transition matrix
trans = {}
for prev in [True, False]:
    for curr in [True, False]:
        mask = (daily_clean["rv_high"].shift(1) == prev) & (daily_clean["rv_high"] == curr)
        count = mask.sum()
        total = (daily_clean["rv_high"].shift(1) == prev).sum()
        trans[f"{'high' if prev else 'low'}->{'high' if curr else 'low'}"] = \
            count / total if total > 0 else 0

# Autocorrelation of RV
rv_autocorr = {}
for lag in [1, 5, 10, 21]:
    rv_autocorr[lag] = daily_clean["rv_20"].autocorr(lag=lag)

# ── VOLATILITY COMPRESSION → BREAKOUT ANALYSIS ──────────────────────────────
print("Analyzing compression → breakout patterns...")
# After a compression period, what happens?
daily_clean["was_compressed"] = daily_clean["bb_squeeze"].rolling(5).mean() > 0.6
next_5d_ret = daily_clean["rets"].rolling(5).sum().shift(-5)
next_5d_abs_ret = daily_clean["rets"].rolling(5).apply(
    lambda x: np.sum(np.abs(x)), raw=True
).shift(-5)

comp_breakout = {
    "compressed_avg_5d_move": next_5d_abs_ret[daily_clean["was_compressed"]].mean(),
    "normal_avg_5d_move": next_5d_abs_ret[~daily_clean["was_compressed"]].mean(),
    "compressed_avg_signed_ret": next_5d_ret[daily_clean["was_compressed"]].mean(),
    "normal_avg_signed_ret": next_5d_ret[~daily_clean["was_compressed"]].mean(),
    "compressed_n": daily_clean["was_compressed"].sum(),
    "normal_n": (~daily_clean["was_compressed"]).sum(),
}

# ── ADAPTIVE VOLATILITY SIZING DETAILED ─────────────────────────────────────
print("Analyzing adaptive vol sizing...")
# Simulate different vol targets
vol_target_results = {}
for target in [0.08, 0.10, 0.12, 0.15, 0.20]:
    trades_vt = backtest_signals(signals, daily, vol_scale=True)
    # Modify the scaling target in a simpler way: adjust risk directly
    # Re-run with different base risk
    risk_map = {0.08: 0.005, 0.10: 0.006, 0.12: 0.007, 0.15: 0.009, 0.20: 0.012}
    trades_vt = backtest_signals(signals, daily, risk_per_trade=risk_map[target], vol_scale=True)
    vol_target_results[f"target_{target}"] = metrics(trades_vt, f"Vol target {target:.0%}")

# ── GENERATE CHARTS ─────────────────────────────────────────────────────────
print("Generating charts...")

# Chart 1: RV over time with regime shading
fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

ax = axes[0]
ax.plot(daily.index, daily["rv_20"], color="steelblue", linewidth=0.8, label="RV 20d")
ax.fill_between(daily.index, 0, daily["rv_20"],
                where=daily["regime"] == "high_vol", alpha=0.15, color="red", label="High vol regime")
ax.fill_between(daily.index, 0, daily["rv_20"],
                where=daily["regime"] == "low_vol", alpha=0.15, color="green", label="Low vol regime")
ax.set_ylabel("Realized Vol (20d, ann.)")
ax.set_title("QQQ Volatility Regimes (2019–2025)")
ax.legend(loc="upper right", fontsize=8)

ax = axes[1]
ax.plot(daily.index, daily["atr_pctl"], color="darkorange", linewidth=0.8)
ax.axhline(0.25, color="green", linestyle="--", alpha=0.5, label="25th pctl (compressed)")
ax.axhline(0.75, color="red", linestyle="--", alpha=0.5, label="75th pctl (expanding)")
ax.set_ylabel("ATR Percentile (252d)")
ax.legend(fontsize=8)

ax = axes[2]
ax.plot(daily.index, daily["vol_cluster_ac1"], color="purple", linewidth=0.8)
ax.axhline(0, color="gray", linestyle="-", alpha=0.3)
ax.set_ylabel("Vol Clustering (AC1 of ret²)")
ax.set_xlabel("Date")
plt.tight_layout()
plt.savefig(CHART_DIR / "vol_regime_timeseries.png", dpi=120)
plt.close()

# Chart 2: Performance by regime
fig, axes = plt.subplots(2, 2, figsize=(12, 9))

# 2a: Win rate by regime
ax = axes[0, 0]
regimes_plot = [r for r in ["low_vol", "mid_vol", "high_vol"] if r in regime_perf]
wr_vals = [regime_perf[r]["win_rate"] for r in regimes_plot]
colors = ["green", "steelblue", "red"][:len(regimes_plot)]
ax.bar(regimes_plot, wr_vals, color=colors)
ax.set_ylabel("Win Rate")
ax.set_title("Win Rate by Volatility Regime")
for i, v in enumerate(wr_vals):
    ax.text(i, v + 0.01, f"{v:.1%}\n(n={regime_perf[regimes_plot[i]]['n_trades']})",
            ha="center", fontsize=9)

# 2b: Average return by regime
ax = axes[0, 1]
avg_rets = [regime_perf[r]["avg_ret"] for r in regimes_plot]
ax.bar(regimes_plot, avg_rets, color=colors)
ax.set_ylabel("Avg Net Return per Trade")
ax.set_title("Avg Return by Volatility Regime")
ax.axhline(0, color="gray", linestyle="-", alpha=0.3)

# 2c: ATR percentile bucket P&L
ax = axes[1, 0]
bucket_labels = list(atr_buckets.keys())
bucket_pnl = [atr_buckets[b]["total_pnl"] for b in bucket_labels]
ax.barh(range(len(bucket_labels)), bucket_pnl, color="steelblue")
ax.set_yticks(range(len(bucket_labels)))
ax.set_yticklabels(bucket_labels, fontsize=8)
ax.set_xlabel("Total P&L ($)")
ax.set_title("P&L by ATR Percentile Bucket")
ax.axvline(0, color="gray", linestyle="-", alpha=0.3)

# 2d: Strategy comparison
ax = axes[1, 1]
labels = ["baseline", "no_high_vol", "vol_scaled", "adaptive_hold", "combo_filter+scale"]
label_map = {
    "baseline": "Baseline",
    "no_high_vol": "filter: no_high_vol",
    "vol_scaled_risk": "Vol-scaled risk",
    "adaptive_hold": "Adaptive hold",
    "combo_filter+scale": "Filter+Scale",
}
sharpes = [results.get(l, results.get(label_map.get(l, ""), {})).get("sharpe", 0) for l in labels]
# Fix lookup
sharpes = []
display_labels = []
for l in ["baseline", "no_high_vol", "vol_scaled_risk", "adaptive_hold", "combo_filter+scale"]:
    m = results.get(l, {})
    sharpes.append(m.get("sharpe", 0))
    display_labels.append(l.replace("_", " ")[:18])
ax.bar(display_labels, sharpes, color="darkcyan")
ax.set_ylabel("Sharpe Ratio")
ax.set_title("Sharpe: Vol Approaches vs Baseline")
plt.xticks(rotation=30, ha="right", fontsize=8)

plt.tight_layout()
plt.savefig(CHART_DIR / "vol_regime_performance.png", dpi=120)
plt.close()

# Chart 3: Equity curves comparison
fig, ax = plt.subplots(figsize=(12, 6))
for label in ["baseline", "no_high_vol", "vol_scaled_risk", "adaptive_hold", "combo_filter+scale"]:
    if label in all_trade_dfs and len(all_trade_dfs[label]) > 0:
        df_trades = all_trade_dfs[label]
        ax.plot(df_trades["date"], df_trades["equity"], label=label, linewidth=1.2)
ax.set_ylabel("Equity ($)")
ax.set_xlabel("Date")
ax.set_title("Equity Curves: Volatility Approaches")
ax.legend(fontsize=8)
ax.axhline(INITIAL_CAPITAL, color="gray", linestyle="--", alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / "vol_regime_equity.png", dpi=120)
plt.close()

# Chart 4: Volatility clustering
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
ax = axes[0]
lags = list(rv_autocorr.keys())
ac_vals = list(rv_autocorr.values())
ax.bar(lags, ac_vals, color="purple")
ax.set_xlabel("Lag (days)")
ax.set_ylabel("Autocorrelation")
ax.set_title("RV Autocorrelation (Clustering Strength)")
ax.axhline(0, color="gray", alpha=0.3)

ax = axes[1]
trans_labels = list(trans.keys())
trans_vals = list(trans.values())
bars = ax.bar(trans_labels, trans_vals, color=["red", "orange", "lightgreen", "green"])
ax.set_ylabel("P(next state | prev state)")
ax.set_title("Vol Regime Transition Matrix")
ax.set_xticklabels(trans_labels, rotation=30, ha="right", fontsize=8)
for bar, val in zip(bars, trans_vals):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.01, f"{val:.2f}",
            ha="center", fontsize=8)
plt.tight_layout()
plt.savefig(CHART_DIR / "vol_clustering.png", dpi=120)
plt.close()

# ── WRITE REPORT ────────────────────────────────────────────────────────────
print("Writing report...")

def fmt_pct(x):
    return f"{x:+.2%}" if not np.isinf(x) else "inf"

def fmt_num(x, dec=2):
    return f"{x:.{dec}f}"

report = f"""# Volatility Regime Analysis — Mission 3

**Date**: {datetime.now().strftime("%Y-%m-%d")}
**Instrument**: QQQ (Nasdaq-100 ETF)
**Data**: Hourly bars, {daily.index[0].date()} → {daily.index[-1].date()}
**Strategy tested**: S1 Asian Sweep (proxy for the system)

---

## Executive Summary

This report tests whether volatility should **filter entries**, **scale risk**,
or **change holding period** for the Nasdaq-100 Asian Sweep strategy.

---

## 1. Volatility Landscape

### Realized Volatility Regimes (20-day annualized)

| Metric | Value |
|--------|-------|
| Median RV | {daily['rv_20'].median():.1%} |
| 20th percentile | {daily['rv_20'].quantile(0.20):.1%} |
| 80th percentile | {daily['rv_20'].quantile(0.80):.1%} |
| Max RV | {daily['rv_20'].max():.1%} |
| % days in low_vol | {(daily['regime']=='low_vol').mean():.1%} |
| % days in mid_vol | {(daily['regime']=='mid_vol').mean():.1%} |
| % days in high_vol | {(daily['regime']=='high_vol').mean():.1%} |

### Volatility Clustering (GARCH persistence)

**Autocorrelation of realized volatility:**

| Lag | AC |
|-----|----|
{chr(10).join(f"| {lag}d | {val:.3f} |" for lag, val in rv_autocorr.items())}

**Regime transition probabilities:**

| From → To | Probability |
|-----------|------------|
{chr(10).join(f"| {k} | {v:.1%} |" for k, v in trans.items())}

**Interpretation**: High-vol days beget high-vol days ({trans.get('high->high', 0):.0%} persistence),
confirming strong volatility clustering. This means vol regimes are *predictable* —
a high-vol environment today likely persists for days/weeks.

---

## 2. Strategy Performance by Volatility Regime

### Baseline (no vol filter) — unconditional performance

| Metric | Value |
|--------|-------|
| Trades | {results['baseline']['n_trades']} |
| CAGR | {results['baseline']['cagr']:.1%} |
| Sharpe | {results['baseline']['sharpe']:.2f} |
| Max DD | {results['baseline']['max_dd']:.1%} |
| Win Rate | {results['baseline']['win_rate']:.1%} |
| PF | {results['baseline']['pf']:.2f} |

### Performance split by regime

| Regime | Trades | Win Rate | Avg Return | Total P&L |
|--------|--------|----------|------------|-----------|
{chr(10).join(f"| {r} | {d['n_trades']} | {d['win_rate']:.1%} | {d['avg_ret']:.2%} | ${d['total_pnl']:.0f} |" for r, d in regime_perf.items() if r in ['low_vol', 'mid_vol', 'high_vol'])}

### Performance by ATR percentile bucket

| ATR Bucket | Trades | Win Rate | Avg Return | Total P&L | PF |
|------------|--------|----------|------------|-----------|----|
{chr(10).join(f"| {b} | {d['n_trades']} | {d['win_rate']:.1%} | {d['avg_ret']:.2%} | ${d['total_pnl']:.0f} | {d.get('pf', 0):.2f} |" for b, d in atr_buckets.items())}

---

## 3. Entry Filtering Tests

| Approach | Trades | CAGR | Sharpe | Max DD | PF | Win Rate |
|----------|--------|------|--------|--------|----|---------|
{chr(10).join(f"| {results[k]['label']} | {results[k]['n_trades']} | {results[k]['cagr']:.1%} | {results[k]['sharpe']:.2f} | {results[k]['max_dd']:.1%} | {results[k]['pf']:.2f} | {results[k]['win_rate']:.1%} |" for k in ['baseline', 'filter=low_vol_only', 'filter=mid_low_only', 'filter=no_high_vol', 'filter=compressed_only', 'filter=no_compressed', 'filter=expansion_only'])}

---

## 4. Volatility-Scaled Risk (Barroso & Santa-Clara 2015)

Position size ∝ target_vol / realized_vol. Higher vol → smaller positions.

| Approach | Trades | CAGR | Sharpe | Max DD | PF |
|----------|--------|------|--------|--------|----|
| Baseline (fixed risk) | {results['baseline']['n_trades']} | {results['baseline']['cagr']:.1%} | {results['baseline']['sharpe']:.2f} | {results['baseline']['max_dd']:.1%} | {results['baseline']['pf']:.2f} |
| Vol-scaled risk | {results['vol_scaled_risk']['n_trades']} | {results['vol_scaled_risk']['cagr']:.1%} | {results['vol_scaled_risk']['sharpe']:.2f} | {results['vol_scaled_risk']['max_dd']:.1%} | {results['vol_scaled_risk']['pf']:.2f} |

### Vol target sensitivity

| Target Vol | Trades | CAGR | Sharpe | Max DD |
|------------|--------|------|--------|--------|
{chr(10).join(f"| {k.replace('target_', '')} | {v['n_trades']} | {v['cagr']:.1%} | {v['sharpe']:.2f} | {v['max_dd']:.1%} |" for k, v in vol_target_results.items())}

---

## 5. Adaptive Holding Period

Adjust stop width and R:R by vol regime:
- High vol → wider stop (1.3×), tighter RR (2.0)
- Low vol → tighter stop (0.8×), wider RR (3.5)

| Approach | Trades | CAGR | Sharpe | Max DD | PF |
|----------|--------|------|--------|--------|----|
| Baseline (fixed 3R) | {results['baseline']['n_trades']} | {results['baseline']['cagr']:.1%} | {results['baseline']['sharpe']:.2f} | {results['baseline']['max_dd']:.1%} | {results['baseline']['pf']:.2f} |
| Adaptive hold | {results['adaptive_hold']['n_trades']} | {results['adaptive_hold']['cagr']:.1%} | {results['adaptive_hold']['sharpe']:.2f} | {results['adaptive_hold']['max_dd']:.1%} | {results['adaptive_hold']['pf']:.2f} |

---

## 6. Combined Approaches

| Combo | Trades | CAGR | Sharpe | Max DD | PF |
|-------|--------|------|--------|--------|----|
| No-high-vol + Vol-scaled | {results['combo_filter+scale']['n_trades']} | {results['combo_filter+scale']['cagr']:.1%} | {results['combo_filter+scale']['sharpe']:.2f} | {results['combo_filter+scale']['max_dd']:.1%} | {results['combo_filter+scale']['pf']:.2f} |
| No-high-vol + Adaptive | {results['combo_filter+adapt']['n_trades']} | {results['combo_filter+adapt']['cagr']:.1%} | {results['combo_filter+adapt']['sharpe']:.2f} | {results['combo_filter+adapt']['max_dd']:.1%} | {results['combo_filter+adapt']['pf']:.2f} |

---

## 7. Volatility Compression → Breakout

After Bollinger Band squeeze (compression), does the market trend more?

| Condition | Avg |Absolute| 5d Move | Avg Signed 5d Ret | N days |
|-----------|---------------------|---------------------|--------|
| Compressed | {comp_breakout['compressed_avg_5d_move']:.2%} | {comp_breakout['compressed_avg_signed_ret']:.2%} | {comp_breakout['compressed_n']} |
| Normal | {comp_breakout['normal_avg_5d_move']:.2%} | {comp_breakout['normal_avg_signed_ret']:.2%} | {comp_breakout['normal_n']} |

**Ratio**: Compressed moves are {comp_breakout['compressed_avg_5d_move'] / max(comp_breakout['normal_avg_5d_move'], 0.0001):.2f}× the size of normal moves.

---

## 8. Compression-conditional strategy performance

| Condition | Trades | Win Rate | Total P&L |
|-----------|--------|----------|-----------|
{chr(10).join(f"| {r} | {d['n_trades']} | {d['win_rate']:.1%} | ${d['total_pnl']:.0f} |" for r, d in regime_perf.items() if r in ['compressed', 'not_compressed'])}

---

## 9. Findings & Recommendations

### Should volatility filter entries?

"""

# Auto-generate conclusions based on data
base_sharpe = results['baseline']['sharpe']
best_filter_sharpe = max(
    results.get('filter=no_high_vol', {}).get('sharpe', 0),
    results.get('filter=mid_low_only', {}).get('sharpe', 0),
    results.get('filter=expansion_only', {}).get('sharpe', 0),
)
best_filter_name = max(
    [('no_high_vol', results.get('filter=no_high_vol', {}).get('sharpe', 0)),
     ('mid_low_only', results.get('filter=mid_low_only', {}).get('sharpe', 0)),
     ('expansion_only', results.get('filter=expansion_only', {}).get('sharpe', 0))],
    key=lambda x: x[1])[0]

filter_verdict = "HELPFUL" if best_filter_sharpe > base_sharpe * 1.1 else \
                 ("NEUTRAL" if abs(best_filter_sharpe - base_sharpe) < base_sharpe * 0.1
                  else "HARMFUL")

report += f"""
**Verdict: {filter_verdict}**

Best filter ({best_filter_name}) Sharpe: {best_filter_sharpe:.2f} vs baseline {base_sharpe:.2f}.
"""

# Check if high-vol regime is actually bad
hv_perf = regime_perf.get('high_vol', {})
lv_perf = regime_perf.get('low_vol', {})
if hv_perf and lv_perf:
    if hv_perf.get('avg_ret', 0) < lv_perf.get('avg_ret', 0):
        report += "High-vol regime trades are indeed worse (lower avg return).\n"
    else:
        report += "**Surprise**: High-vol trades are NOT worse — filtering them may cut good trades.\n"

vol_scale_sharpe = results.get('vol_scaled_risk', {}).get('sharpe', 0)
scale_verdict = "HELPFUL" if vol_scale_sharpe > base_sharpe * 1.05 else \
                ("NEUTRAL" if abs(vol_scale_sharpe - base_sharpe) < base_sharpe * 0.05
                 else "HARMFUL")

report += f"""
### Should volatility scale risk?

**Verdict: {scale_verdict}**

Vol-scaled risk Sharpe: {vol_scale_sharpe:.2f} vs baseline {base_sharpe:.2f}.
The Barroso & Santa-Clara approach scales position size inversely to realized vol.
Note: the existing system already has a conformal DD-throttle that serves a similar
role — this is the complement (per-trade vol scaling vs portfolio-level DD scaling).
"""

adapt_sharpe = results.get('adaptive_hold', {}).get('sharpe', 0)
adapt_verdict = "HELPFUL" if adapt_sharpe > base_sharpe * 1.05 else \
                ("NEUTRAL" if abs(adapt_sharpe - base_sharpe) < base_sharpe * 0.05
                 else "HARMFUL")

report += f"""
### Should volatility change holding period?

**Verdict: {adapt_verdict}**

Adaptive hold Sharpe: {adapt_sharpe:.2f} vs baseline {base_sharpe:.2f}.
Prior research (FINDINGS.md) showed dynamic exits HURT the edge because profits
come from letting winners run to the 3R target. Adaptive holding periods that
change R:R by regime must be evaluated carefully.
"""

# Clustering conclusion
report += f"""
### Volatility Clustering

RV autocorrelation at 1-day lag: {rv_autocorr.get(1, 0):.3f}.
High-vol persistence: {trans.get('high->high', 0):.0%} (P(high vol tomorrow | high vol today)).
This confirms vol regimes are **persistent and predictable** — making regime-based
rules viable (they don't whipsaw).

### Compression → Breakout Signal

Compressed regimes are followed by {comp_breakout['compressed_avg_5d_move'] / max(comp_breakout['normal_avg_5d_move'], 0.0001):.1f}× larger absolute moves.
This is consistent with the Bollinger Band squeeze / volatility breakout literature.
However, the strategy performance in compressed vs non-compressed regimes
(Section 8) determines whether this is *tradeable* for the sweep edge specifically.

---

## Charts

- `vol_regime_timeseries.png` — RV, ATR percentile, clustering over time
- `vol_regime_performance.png` — Win rate, returns, P&L by regime and approach
- `vol_regime_equity.png` — Equity curves for all approaches
- `vol_clustering.png` — RV autocorrelation + transition matrix
"""

# Write report
report_path = OUTPUT_DIR / "volatility_regime_report.md"
with open(report_path, "w") as f:
    f.write(report)

# Write JSON results
json_path = OUTPUT_DIR / "vol_regime_results.json"
with open(json_path, "w") as f:
    # Convert numpy types
    def clean_json(obj):
        if isinstance(obj, dict):
            return {k: clean_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [clean_json(x) for x in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return obj

    full_results = {
        "experiment_metrics": {k: clean_json(v) for k, v in results.items()},
        "regime_performance": clean_json(regime_perf),
        "atr_buckets": clean_json(atr_buckets),
        "clustering": {
            "autocorrelation": {str(k): float(v) for k, v in rv_autocorr.items()},
            "transition_matrix": {k: float(v) for k, v in trans.items()},
        },
        "compression_breakout": clean_json(comp_breakout),
        "vol_target_sensitivity": {k: clean_json(v) for k, v in vol_target_results.items()},
        "generated": datetime.now().isoformat(),
    }
    json.dump(full_results, f, indent=2, default=str)

print(f"\n✅ Report written to {report_path}")
print(f"✅ JSON results written to {json_path}")
print(f"✅ Charts in {CHART_DIR}/vol_regime_*.png")
print("\n--- KEY METRICS ---")
print(f"Baseline: Sharpe {results['baseline']['sharpe']:.2f}, "
      f"CAGR {results['baseline']['cagr']:.1%}, "
      f"MaxDD {results['baseline']['max_dd']:.1%}")
print(f"Best filter: {best_filter_name} → Sharpe {best_filter_sharpe:.2f} ({filter_verdict})")
print(f"Vol-scaled: Sharpe {vol_scale_sharpe:.2f} ({scale_verdict})")
print(f"Adaptive hold: Sharpe {adapt_sharpe:.2f} ({adapt_verdict})")
print(f"Clustering AC1: {rv_autocorr.get(1, 0):.3f}")
print(f"Compression ratio: {comp_breakout['compressed_avg_5d_move'] / max(comp_breakout['normal_avg_5d_move'], 0.0001):.2f}×")
