"""
mean_reversion_basket.py — RSI-2 mean reversion across a BASKET, pooled, through
the doc's six filters. Goal: enough trades to (a) raise live frequency and
(b) make the OOS test statistically real. Same edge, more independent symbols.
"""
import pandas as pd, numpy as np, pytz, warnings
from mean_reversion_test import load, rsi, metrics, SLIP, ANN_D
warnings.filterwarnings("ignore")

BASKET = ["QQQ", "SPY", "IWM", "GLD", "AAPL", "MSFT", "NVDA"]


def daily_trades(df):
    """Return list of (exit_date, ret) for RSI-2<10 & >200SMA, exit close>5dSMA/-3%."""
    d = df["Close"].resample("1D").last().dropna()
    dd = pd.DataFrame({"Close": d})
    dd["RSI"] = rsi(dd["Close"], 2)
    dd["SMA200"] = dd["Close"].rolling(200).mean()
    dd["SMA5"] = dd["Close"].rolling(5).mean()
    v = dd.dropna()
    out = []; in_t = False; entry = 0.0
    for i in range(1, len(v)):
        px = v["Close"].iloc[i]
        if in_t:
            ret = px / entry - 1
            if ret <= -0.03 or px > v["SMA5"].iloc[i]:
                out.append((v.index[i], ret - SLIP)); in_t = False
        elif v["RSI"].iloc[i] < 10 and px > v["SMA200"].iloc[i]:
            in_t = True; entry = px
    return out


def split_metrics(all_trades, lo, hi):
    sel = [r for (dt, r) in all_trades if lo <= dt.year <= hi]
    t = pd.Series(sel)
    if len(t) == 0: return dict(n=0, wr=0, ret=0, sharpe=0, dd=0)
    eq = (1 + t).cumprod()
    return dict(n=len(t), wr=(t > 0).mean(), ret=eq.iloc[-1]-1,
                sharpe=t.mean()/t.std()*np.sqrt(len(t)) if t.std() > 0 else 0,
                dd=(eq/eq.cummax()-1).min())


pooled = []
per_sym = {}
for s in BASKET:
    try:
        tr = daily_trades(load(s))
        per_sym[s] = len(tr); pooled += tr
    except FileNotFoundError:
        per_sym[s] = "no data"
pooled.sort()

IS  = split_metrics(pooled, 2019, 2022)
OOS = split_metrics(pooled, 2023, 2026)
yrs_oos = 2026 - 2023 + 1

print("Per-symbol trade counts (7y):", per_sym)
print(f"\nPOOLED BASKET (RSI-2 mean reversion, {len(BASKET)} symbols)")
print(f"  IS  (2019-22): n={IS['n']:3d}  wr={IS['wr']:.0%}  ret={IS['ret']:+.1%}  "
      f"Sharpe~{IS['sharpe']:.2f}  DD={IS['dd']:.1%}")
print(f"  OOS (2023-26): n={OOS['n']:3d}  wr={OOS['wr']:.0%}  ret={OOS['ret']:+.1%}  "
      f"Sharpe~{OOS['sharpe']:.2f}  DD={OOS['dd']:.1%}")
print(f"  Trade frequency (OOS): {OOS['n']/yrs_oos:.0f}/yr  (~{OOS['n']/yrs_oos/52:.1f}/week)")

checks = {
    "[01] OOS Sharpe>0.5":   OOS["sharpe"] > 0.5,
    "[02] maxDD>-35%":       OOS["dd"] > -0.35,
    "[03] OOS Sharpe<2.5":   OOS["sharpe"] < 2.5,
    "[04] not overfit":      OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
    "[05] >=30 trades":      OOS["n"] >= 30,
    "[06] IS Sharpe>0":      IS["sharpe"] > 0,
}
print("  FILTERS:")
for k, v in checks.items():
    print(f"    [{'PASS' if v else 'FAIL'}] {k}")
print(f"  >>> {'✅ PASSES ALL SIX' if all(checks.values()) else '❌ REJECTED'}")
