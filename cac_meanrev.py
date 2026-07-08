"""
cac_meanrev.py — Lag-1 log-return mean reversion on CAC40 daily data.
Signal: -1 × close_log_return_lag_1
  → if previous day was +0.5%, predict reversal → short
  → if previous day was −0.5%, predict reversal → long

Tests three variants:
  A) Raw edge: zero slippage/commission (upper bound)
  B) Retail taker: 0.5bps commission + 0.3bps slippage (approx 8bps round-trip)
  C) With VIX regime filter (no trades when VIX 21d MA > 25)
  D) With CAC trend filter (only trade in direction of 200-day EMA)

Hold period sweep: 1, 5, 10, 20 days (to find optimal horizon)
OOS split: IN-sample 2000-2014, OUT-of-sample 2015-2024

Key question: is there edge before costs? If yes, is it large enough to survive
retail execution? (Maker/taker fees on futures ~0.02% round-trip).
"""
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date
warnings.filterwarnings("ignore")

# Parameters
START_DATE = "2000-01-01"
END_DATE   = str(date.today())  # up to today
THRESH     = 0.005   # 0.5% prior move threshold
RISK_PER_TRADE = 0.01  # 1% of capital risked per trade

# Fetch CAC40 data (daily)
print("Loading CAC40 daily data...")
df_cac = yf.download("^FCHI", start=START_DATE, end=END_DATE, progress=False)
if isinstance(df_cac.columns, pd.MultiIndex):
    df_cac.columns = df_cac.columns.droplevel(1)
df_cac = df_cac[["Open", "High", "Low", "Close", "Volume"]].dropna()
df_cac.index = pd.to_datetime(df_cac.index)
df_cac = df_cac[df_cac.index >= pd.Timestamp(START_DATE)]
df_cac["Date"] = df_cac.index.date
print(f"  {len(df_cac):,} daily bars from {df_cac.index[0].date()} to {df_cac.index[-1].date()}")

# List of years for reporting
years = sorted(df_cac["Date"].apply(lambda d: d.year).unique())

# Fetch VIX for regime filter
print("Loading VIX data...")
vix = yf.download("^VIX", start=START_DATE, end=END_DATE, progress=False)["Close"]
if isinstance(vix, pd.DataFrame):
    vix = vix.iloc[:, 0]
vix_ma21 = vix.rolling(21).mean()

# Compute signal
df_cac["log_ret"] = np.log(df_cac["Close"] / df_cac["Close"].shift(1))
df_cac["signal_raw"] = -df_cac["log_ret"].shift(1)   # lag-1 inversion; NO look-ahead bias
df_cac["signal"] = np.where(df_cac["signal_raw"].abs() > THRESH, np.sign(df_cac["signal_raw"]), 0)

# Precompute trend filter (200-day EMA)
ema200 = df_cac["Close"].ewm(span=200, adjust=False).mean()
bull = df_cac["Close"] > ema200
bear = df_cac["Close"] < ema200

# ── Hold-period backtest engine ─────────────────────────────────────────────
def run(hold_days: int, cost_bps: float = 0.0, use_vix: bool = False, use_trend: bool = False) -> dict:
    """
    Enter on close of signal day; exit after hold_days days (market-on-close).
    cost_bps: round-trip total (commission + slippage) per trade in basis points.
    use_vix: apply VIX regime filter (no trades when VIX 21d MA > 25)
    use_trend: trade only in direction of 200-day EMA (long if close > EMA200, short if close < EMA200)
    Returns per-year return dict.
    """
    cost = cost_bps / 10_000
    out = {}
    for Y in years:
        cap = init = 10_000.0
        i = 0
        while i < len(df_cac):
            if df_cac.index[i].year != Y:
                i += 1
                continue
            sig  = int(df_cac["signal"].iloc[i])
            # VIX filter
            vm = 1.0
            if use_vix:
                v = vix_ma21.asof(pd.Timestamp(df_cac["Date"].iloc[i]))
                vm = 0.0 if (pd.isna(v) or v > 25) else 1.0
            # Trend filter
            tr = 1.0
            if use_trend:
                if sig == 1:  # long
                    tr = 1.0 if bool(bull.iloc[i]) else 0.0
                else:  # short
                    tr = 1.0 if bool(bear.iloc[i]) else 0.0
            if sig != 0 and vm > 0 and tr > 0:
                entry_p = float(df_cac["Close"].iloc[i])
                exit_i  = min(i + hold_days, len(df_cac) - 1)
                exit_p  = float(df_cac["Close"].iloc[exit_i])
                direction = sig  # +1 long, -1 short
                pnl_pct = direction * ((exit_p - entry_p) / entry_p) - cost
                # Fixed fractional risk per trade
                cap += cap * RISK_PER_TRADE * pnl_pct / max(abs(pnl_pct), 0.0001) * abs(pnl_pct)
                i = exit_i + 1
            else:
                i += 1
        out[Y] = (cap - init) / init
    return out

# Hold-period sweep
HOLD_DAYS  = [1, 5, 10, 20]
COST_CASES = [
    ("Raw (0bps)",           0.0,   False, False),
    ("Retail taker (8bps)",  8.0,   False, False),
    ("Retail + VIX filter",  8.0,   True,  False),
    ("Retail + Trend filter",8.0,   False, True),
    ("Retail + VIX + Trend", 8.0,   True,  True),
]

print(f"\n{'='*90}")
print("CAC40 MEAN REVERSION SIGNAL TEST — daily, lag-1 log return inversion")
print(f"Signal threshold: >{THRESH*100:.2f}% prior move")
print(f"{'='*90}")

for cost_name, cost_bps, use_vix, use_trend in COST_CASES:
    print(f"\n{cost_name}")
    hdr = f"  {'Hold':>5}" + "".join(f"{Y:>6}" for Y in years[::max(1, len(years)//8)]) + f"{'avg':>8}{'IN':>8}{'OUT':>8}"
    print(hdr); print("  " + "-"*80)
    for h in HOLD_DAYS:
        r  = run(h, cost_bps, use_vix, use_trend)
        avg = np.mean([r[Y] for Y in years])
        IN  = np.mean([r[Y] for Y in years if Y <= 2014])
        OUT = np.mean([r[Y] for Y in years if Y >= 2015])
        row = f"  {h:>3}d" + "".join(f"{r[Y]:>+7.2%}" for Y in years[::max(1, len(years)//8)])
        row += f"{avg:>+7.2%}{IN:>+7.2%}{OUT:>+8.2%}"
        print(row)

# Signal statistics
print(f"\n{'='*90}")
print("SIGNAL STATISTICS — does the lag-1 return predict the next day?")
print(f"{'='*90}")
sig_bars = df_cac[df_cac["signal"] != 0].copy()
sig_bars["next_ret"] = np.log(df_cac["Close"] / df_cac["Close"].shift(1)).shift(-1)
sig_bars["correct"]  = (sig_bars["signal"] * sig_bars["next_ret"]) > 0

for Y in list(years) + ["all"]:
    if Y == "all":
        sub = sig_bars
    else:
        sub = sig_bars[sig_bars.index.year == Y]
    if len(sub) == 0:
        continue
    acc     = sub["correct"].mean()
    n       = len(sub)
    avg_ret = sub["next_ret"].abs().mean() * 10_000
    print(f"  {str(Y):>6}: n={n:>7,}  1-day accuracy={acc:.1%}  avg |next_ret|={avg_ret:.2f}bps")

print(f"\n{'='*90}")
print("CONCLUSION:")
print("  If 1-day accuracy > 50% consistently AND raw edge is positive:")
print("    → statistical signal exists on CAC40; edge size determines executability")
print("  If accuracy ≈ 50%:")
print("    → no edge; any profit comes from cost structure or trend.")
print(f"{'='*90}")

# Plot equity curve for best case (example raw 20-day hold)
best = run(20, 0.0, False, False)
eq = [10_000]
for Y in sorted(best.keys()):
    eq.append(eq[-1] * (1 + best[Y]))
import matplotlib.pyplot as plt
plt.figure(figsize=(12,5))
plt.plot(eq, linewidth=1.5)
plt.title("CAC40 Mean Reversion — Raw, 20-day hold")
plt.xlabel("Year (cumulative)")
plt.ylabel("Capital ($)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_cac_meanrev.png")
print("\nChart saved: equity_cac_meanrev.png")