"""
Test dynamic-exit variants vs the validated fixed-stop baseline on S1.
Honest A/B — keep a variant ONLY if it beats baseline on return AND risk, net of costs.
Variants:
  baseline  : fixed stop (1.5%) + fixed target (3:1 RR)        [the validated one]
  trail     : trailing stop = peak*(1-1.5%), still capped at 3R target
  breakeven : move stop to entry once price hits +1R, else baseline
  partial   : take half off at +1.5R (stop→breakeven on remainder), rest runs to 3R
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
_src = open("full_yearly.py").read().split("# ── run all")[0]
exec(_src)   # gives q (with S1 signal), vmult, SLIP, YEARS

RISK, SL, RR = 0.007, 0.015, 3.0

def run(mode):
    yr_ret = {}; all_trades = []
    for Y in YEARS:
        cap = init = 10_000; in_t = False
        entry = stop = tgt = sh = peak = 0.0; half_done = False
        ds = cap; cur = None; lock = False; dt = None
        for i in range(1, len(q)):
            if q.index[i].year != Y: continue
            d = q.index[i].date(); price = float(q["Close"].iloc[i])
            s = int(q["S1"].iloc[i-1]); vm = vmult(q.index[i-1].date())
            if d != cur: cur = d; ds = cap; lock = False
            if (cap-ds)/max(ds,1) <= -0.05 or (cap-init)/init <= -0.10: lock = True
            if lock: continue
            if in_t:
                peak = max(peak, price); exit_px = None
                if mode == "baseline":
                    if price <= stop: exit_px = stop
                    elif price >= tgt: exit_px = tgt
                elif mode == "trail":
                    eff = max(stop, peak*(1-SL))
                    if price <= eff: exit_px = eff
                    elif price >= tgt: exit_px = tgt
                elif mode == "breakeven":
                    if price >= entry*(1+SL): stop = max(stop, entry)
                    if price <= stop: exit_px = stop
                    elif price >= tgt: exit_px = tgt
                elif mode == "partial":
                    if not half_done and price >= entry*(1+SL*1.5):
                        pnl = 0.5*sh*(price-entry) - 0.5*sh*(entry+price)*SLIP
                        cap += pnl; all_trades.append(pnl); sh *= 0.5
                        stop = entry; half_done = True
                    if price <= stop: exit_px = stop
                    elif price >= tgt: exit_px = tgt
                if exit_px is not None:
                    pnl = sh*(exit_px-entry) - sh*(entry+exit_px)*SLIP
                    cap += pnl; all_trades.append(pnl); in_t = False
            elif s == 1 and vm > 0 and dt != d:
                in_t = True; dt = d; entry = price; peak = price
                stop = price*(1-SL); tgt = price*(1+SL*RR)
                sh = (cap*RISK*vm)/(price*SL); half_done = False
        yr_ret[Y] = (cap-init)/init
    t = pd.Series(all_trades)
    pf = t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else 99.9
    wr = (t>0).mean() if len(t) else 0
    eq = pd.Series([10_000]+list(t.cumsum()+10_000)); dd = ((eq-eq.cummax())/eq.cummax()).min()
    return yr_ret, np.mean(list(yr_ret.values())), pf, wr, dd, len(t)

print("="*78)
print("DYNAMIC EXIT A/B on S1 (net of costs) — keep only if it beats baseline")
print("="*78)
print(f"{'Mode':<11}"+"".join(f"{Y:>8}" for Y in YEARS)+f"{'avg':>8}{'PF':>6}{'WR':>6}{'maxDD':>8}")
print("-"*78)
base = None
for mode in ["baseline","trail","breakeven","partial"]:
    yr,avg,pf,wr,dd,n = run(mode)
    if base is None: base = avg
    flag = "" if mode=="baseline" else ("  ✅ better" if avg>base else "  ✗ worse")
    print(f"{mode:<11}"+"".join(f"{yr[Y]:>+8.1%}" for Y in YEARS)+f"{avg:>+8.1%}{pf:>6.2f}{wr:>6.0%}{dd:>8.1%}{flag}")
print("-"*78)
print("Verdict: adopt a variant only if it raises avg return AND doesn't worsen maxDD/PF.")
