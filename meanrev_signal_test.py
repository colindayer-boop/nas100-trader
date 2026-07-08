"""
meanrev_signal_test.py — Lag-1 log-return mean reversion on QQQ 1-min RTH data.

Signal: -1 × close_log_return_lag_1
  → if previous bar was +0.2%, predict reversal → short
  → if previous bar was −0.2%, predict reversal → long

Tests three variants to understand the edge and cost sensitivity:
  A) Raw edge: zero slippage/commission (upper bound)
  B) Retail taker: 0.5bps commission + 0.3bps slippage (Alpaca market order)
  C) With VIX regime filter (no trades when VIX 21d MA > 25)

Hold period sweep: 1, 5, 15, 30, 60 bars (to find optimal horizon)
OOS split: IN-sample 2019-21, OUT-of-sample 2022-23

Key question: is there edge before costs? If yes, is it large enough to survive
retail execution? (Crypto perp maker fees are ~20bps round-trip vs. ~10bps retail.)
"""
import warnings
import numpy as np
import pandas as pd
import pytz
import yfinance as yf
from datetime import date, timedelta
warnings.filterwarnings("ignore")

eastern = pytz.timezone("US/Eastern")
YEARS   = range(2019, 2024)

print("Loading QQQ 1-min data...")
df = pd.read_csv("qqq_1min_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp").tz_convert(eastern)
if "symbol" in df.columns:
    df = df[df["symbol"] == "QQQ"]
df = df[["open", "high", "low", "close", "volume"]].copy()
df.columns = ["Open", "High", "Low", "Close", "Volume"]
# RTH only: 9:30–16:00
df = df[(df.index.hour >= 9) & (df.index.hour < 16)]
df = df[~((df.index.hour == 9) & (df.index.minute < 30))]
df = df[(df.index.date >= pd.Timestamp("2019-01-01").date()) &
        (df.index.date <= pd.Timestamp("2023-12-31").date())]
df["Date"] = df.index.date
print(f"  {len(df):,} RTH bars")

# ── Signal: -1 × lag-1 log return ──────────────────────────────────────────
df["log_ret"]    = np.log(df["Close"] / df["Close"].shift(1))
df["signal_raw"] = -df["log_ret"].shift(1)   # lag-1 inversion; NO look-ahead bias
# Threshold: only trade on "meaningful" prior moves (avoid noise)
THRESH = 0.0005   # 0.05% = ~0.3pt on QQQ — below this, too noisy
df["signal"] = np.where(df["signal_raw"].abs() > THRESH, np.sign(df["signal_raw"]), 0)

# ── VIX regime ─────────────────────────────────────────────────────────────
vix = yf.download("^VIX", start="2018-01-01", end=str(date.today()), progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:, 0]
vix_ma21 = vix.rolling(21).mean()
def vmult(d):
    v = vix_ma21.asof(pd.Timestamp(d))
    return 0.0 if (pd.isna(v) or v > 25) else 1.0

# ── Hold-period backtest engine ─────────────────────────────────────────────
def run(hold_bars: int, cost_bps: float = 0.0, use_vix: bool = False) -> dict:
    """
    Enter on close of signal bar; exit after hold_bars bars (market-on-close).
    cost_bps: round-trip total (commission + slippage) per trade in basis points.
    Returns per-year return dict.
    """
    cost = cost_bps / 10_000
    out = {}
    for Y in YEARS:
        cap = init = 10_000.0
        trades = []
        i = 0
        while i < len(df):
            if df.index[i].year != Y:
                i += 1; continue
            sig  = df["signal"].iloc[i]
            vm   = vmult(df["Date"].iloc[i]) if use_vix else 1.0
            if sig != 0 and vm > 0:
                entry_p = float(df["Close"].iloc[i])
                exit_i  = min(i + hold_bars, len(df) - 1)
                exit_p  = float(df["Close"].iloc[exit_i])
                direction = sig  # +1 long, -1 short
                pnl_pct = direction * ((exit_p - entry_p) / entry_p) - cost
                # Fixed fractional 0.5% risk per trade (small, many trades)
                cap += cap * 0.005 * pnl_pct / max(abs(pnl_pct), 0.0001) * abs(pnl_pct)
                trades.append(pnl_pct)
                i = exit_i + 1
            else:
                i += 1
        out[Y] = (cap - init) / init
    return out


# ── Sweep hold periods ──────────────────────────────────────────────────────
HOLD_BARS  = [1, 5, 15, 30, 60]
COST_CASES = [
    ("Raw (0bps)",           0.0,   False),
    ("Retail taker (8bps)", 8.0,   False),   # ~4bps commission + 4bps slip
    ("Retail + VIX filter", 8.0,   True),
    ("Perp maker (2bps)",   2.0,   False),   # ~1bps maker fee + 1bps slip
]

print(f"\n{'='*90}")
print("MEAN REVERSION SIGNAL TEST — QQQ 1-min, lag-1 log return inversion")
print(f"Signal threshold: >{THRESH*100:.2f}% prior move  |  IN=2019-21  OUT=2022-23")
print(f"{'='*90}")

for cost_name, cost_bps, use_vix in COST_CASES:
    print(f"\n{cost_name}")
    hdr = f"  {'Hold':>6}" + "".join(f"{Y:>8}" for Y in YEARS) + f"{'avg':>7}{'IN':>7}{'OUT':>8}"
    print(hdr); print("  " + "-"*72)
    for h in HOLD_BARS:
        r  = run(h, cost_bps, use_vix)
        avg = np.mean([r[Y] for Y in YEARS])
        IN  = np.mean([r[Y] for Y in (2019, 2020, 2021)])
        OUT = np.mean([r[Y] for Y in (2022, 2023)])
        row = f"  {h:>5}m" + "".join(f"{r[Y]:>+8.1%}" for Y in YEARS)
        row += f"{avg:>+7.1%}{IN:>+7.1%}{OUT:>+8.1%}"
        print(row)

# ── Signal statistics (directionality) ──────────────────────────────────────
print(f"\n{'='*90}")
print("SIGNAL STATISTICS — does the lag-1 return predict the next bar?")
print(f"{'='*90}")
# For each bar where signal != 0, check if next bar moved in predicted direction
sig_bars = df[df["signal"] != 0].copy()
sig_bars["next_ret"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1)
sig_bars["correct"]  = (sig_bars["signal"] * sig_bars["next_ret"]) > 0

for Y in list(YEARS) + ["all"]:
    if Y == "all":
        sub = sig_bars
    else:
        sub = sig_bars[sig_bars.index.year == Y]
    if len(sub) == 0: continue
    acc     = sub["correct"].mean()
    n       = len(sub)
    avg_ret = sub["next_ret"].abs().mean() * 10_000
    print(f"  {str(Y):>4}: n={n:>6,}  1-bar accuracy={acc:.1%}  avg |next_ret|={avg_ret:.2f}bps")

print(f"\n{'='*90}")
print("CONCLUSION:")
print("  If 1-bar accuracy > 50% consistently AND raw edge is positive:")
print("    → statistical signal exists on QQQ; edge size determines executability")
print("  If accuracy ≈ 50%:")
print("    → no edge; the video's edge comes from crypto perp maker mechanics, not signal alone")
print(f"{'='*90}")
