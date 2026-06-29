"""
reconcile_sweep.py — Robustness sweep in the SAME monthly engine that produced
the validated OOS Sharpe 1.07. Vary lookback and top-N; month-end rebalance.
If only lookback=12/top~3 works, it was a lucky single point → reject.
"""
import pandas as pd, numpy as np, warnings
import yfinance as yf
from datetime import date
warnings.filterwarnings("ignore")

SLIP = 0.0010
CROSS = ["SPY","QQQ","IWM","EFA","EEM","TLT","GLD","DBC"]


def monthly_closes(tickers, start="2010-01-01"):
    raw = yf.download(tickers, start=start, end=str(date.today()),
                      progress=False, auto_adjust=True)["Close"]
    if isinstance(raw, pd.Series): raw = raw.to_frame()
    return raw.resample("ME").last().dropna(how="all")


def run(px, lookback, topN):
    mom = px.shift(1) / px.shift(lookback) - 1
    rets = []
    for i in range(lookback, len(px) - 1):
        dt = px.index[i + 1]
        score = mom.iloc[i].dropna()
        valid = px.iloc[i].notna() & px.iloc[i + 1].notna()
        score = score[score.index.isin(valid.index[valid])]
        if len(score) < 4: continue
        top = score.sort_values(ascending=False).index[:topN]
        fwd = (px.iloc[i + 1][top] / px.iloc[i][top] - 1).mean() - SLIP
        rets.append((dt, fwd))
    return rets


def stats(rets, lo, hi):
    sel = [r for (d, r) in rets if lo <= d.year <= hi]
    if not sel: return None
    r = pd.Series(sel); eq = (1 + r).cumprod()
    return dict(n=len(r), sharpe=r.mean()/r.std()*np.sqrt(12) if r.std() > 0 else 0,
                cagr=eq.iloc[-1]**(12/len(r))-1, dd=(eq/eq.cummax()-1).min())


px = monthly_closes(CROSS)
spy = px["SPY"].pct_change().dropna()
spy_oos = spy[(spy.index.year >= 2022)]
spy_sharpe = spy_oos.mean()/spy_oos.std()*np.sqrt(12)
print(f"SPY OOS Sharpe benchmark: {spy_sharpe:.2f}\n")
print(f"{'LB':>3} {'TopN':>4} | {'IS_Sh':>6} {'OOS_Sh':>6} {'CAGR':>7} {'maxDD':>7} | {'6pass':>5} {'>SPY':>4}")
print("-"*60)
npass = 0; rows = []
for lb in [6, 9, 12]:
    for tn in [2, 3, 4]:
        rets = run(px, lb, tn)
        IS, OOS = stats(rets, 2010, 2021), stats(rets, 2022, 2026)
        if not IS or not OOS: continue
        six = (OOS["sharpe"] > 0.5 and OOS["dd"] > -0.35 and OOS["sharpe"] < 2.5
               and OOS["sharpe"] <= IS["sharpe"]*1.3+0.5 and OOS["n"] >= 30
               and IS["sharpe"] > 0)
        beat = OOS["sharpe"] > spy_sharpe
        if six and beat: npass += 1
        print(f"{lb:>3} {tn:>4} | {IS['sharpe']:>6.2f} {OOS['sharpe']:>6.2f} "
              f"{OOS['cagr']:>+6.1%} {OOS['dd']:>+6.1%} | "
              f"{'YES' if six else 'no':>5} {'YES' if beat else 'no':>4}")
print("-"*60)
print(f"\nRobust combos (6 filters + beat SPY): {npass}/9")
print(">>> " + ("ROBUST — edge holds across params" if npass >= 5
      else "FRAGILE — likely overfit, REJECT" if npass <= 2
      else "MIXED — borderline"))
