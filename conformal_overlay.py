"""
Conformal / regime risk-control overlay (simplified RWC, after Schmitt 2026
"Taming Tail Risk"). Wraps the 3-pillar system with a model-agnostic position
scaler calibrated from RECENT realized risk — the conformal idea: size so the
loss-exceedance stays under a target, tightening in bad regimes.

Two components (each uses only past info — no lookahead):
  vol-target : scale down when recent realized vol > target (calm-vs-stress regime)
  dd-throttle: scale down as live drawdown approaches the target cap (the buffer)
We NEVER lever above 1.0 (prop-safe). Goal: cut max drawdown / worst window
without killing too much return. Kept ONLY if the data shows it tames the tail.
"""
import pandas as pd, numpy as np, warnings, io, contextlib
warnings.filterwarnings("ignore")

# Reuse the 3-pillar combined daily P&L (suppress its prints)
g = {}
with contextlib.redirect_stdout(io.StringIO()):
    exec(open("combined_3pillar.py").read(), g)
combined = g["combined"].sort_index()
base = 10_000.0
idx = pd.date_range(combined.index.min(), combined.index.max(), freq="D")
pnl = combined.reindex(idx).fillna(0.0)
rr = pnl / base
TGT_VOL = rr[rr != 0].std() * 0.8   # target daily vol = 0.8x realized (conformal-ish)

def metrics(eq):
    rets = eq.pct_change().fillna(0)
    yrs = (eq.index[-1]-eq.index[0]).days/365.25
    cagr = (eq.iloc[-1]/base)**(1/yrs)-1
    sharpe = (rets.mean()*252)/(rets.std()*np.sqrt(252)) if rets.std()>0 else 0
    mdd = ((eq-eq.cummax())/eq.cummax()).min()
    # worst rolling 126-trading-day (~6mo) drawdown
    roll = eq/eq.cummax()-1
    worst6 = roll.rolling(126).min().min()
    return cagr, sharpe, mdd, worst6

def run(mode, target_dd=0.06, W=20):
    vols = rr.rolling(W).std()
    eq = base; peak = base; out = []
    for i in range(len(pnl)):
        sc = 1.0
        if mode in ("vol", "both"):
            v = vols.iloc[i-1] if i > 0 and not np.isnan(vols.iloc[i-1]) else TGT_VOL
            if v > 0: sc = min(sc, min(1.0, TGT_VOL / v))
        if mode in ("dd", "both"):
            cur_dd = (eq - peak) / peak             # <= 0
            head = (target_dd + cur_dd) / target_dd  # 1 at no DD, 0 at the cap
            sc = min(sc, max(0.3, head))             # floor 0.3x, never lever up
        eq = eq + sc * pnl.iloc[i]
        peak = max(peak, eq); out.append(eq)
    return pd.Series(out, index=pnl.index)

eq_base = base + pnl.cumsum()
print("="*78)
print("CONFORMAL RISK OVERLAY on 3-pillar system (target DD cap 6%)")
print("="*78)
print(f"{'Variant':<24}{'CAGR':>9}{'Sharpe':>8}{'MaxDD':>9}{'Worst6mo':>10}")
print("-"*78)
cb,sb,db,wb = metrics(eq_base)
print(f"{'baseline (no overlay)':<24}{cb:>+9.1%}{sb:>8.2f}{db:>+9.1%}{wb:>+10.1%}")
for mode,label in [("vol","vol-target only"),("dd","dd-throttle only"),("both","conformal (both)")]:
    c,s,dmax,w = metrics(run(mode))
    print(f"{label:<24}{c:>+9.1%}{s:>8.2f}{dmax:>+9.1%}{w:>+10.1%}")
print("-"*78)
print("Keep ONLY if it cuts MaxDD / Worst6mo meaningfully without gutting CAGR.")
print("(Calmar = CAGR/|MaxDD|; higher = better risk-adjusted for a prop account.)")
