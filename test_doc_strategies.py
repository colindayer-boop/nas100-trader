"""
test_doc_strategies.py — Run the doc's Prompts 2,3,4 through the six filters, on
OUR data, with costs. Fair test before deciding the doc has nothing to add.

P2 Ultimate Oscillator (7,14,28): long when UO crosses up through 30; exit UO>70
   or after 5 bars. (daily)
P3 Turtle: long 20-day high breakout; exit 10-day low breakdown. (daily, ATR ctx)
P4 Cross-sectional momentum: rank basket by 12-1 month return, long top ~20%,
   monthly rebalance. (the genuinely uncorrelated, low-frequency one)
"""
import pandas as pd, numpy as np, warnings
from mean_reversion_test import load, SLIP
warnings.filterwarnings("ignore")

BASKET = ["QQQ", "SPY", "IWM", "GLD", "AAPL", "MSFT", "NVDA"]
ANN_D = np.sqrt(252)


def daily(sym):
    df = load(sym)
    d = pd.DataFrame({"O": df["Open"].resample("1D").first(),
                      "H": df["High"].resample("1D").max(),
                      "L": df["Low"].resample("1D").min(),
                      "C": df["Close"].resample("1D").last()}).dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return d


def six_filters(IS, OOS, name):
    checks = {
        "[01] OOS Sharpe>0.5": OOS["sharpe"] > 0.5,
        "[02] maxDD>-35%":     OOS["dd"] > -0.35,
        "[03] OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
        "[04] not overfit":    OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
        "[05] >=30 trades":    OOS["n"] >= 30,
        "[06] IS Sharpe>0":    IS["sharpe"] > 0,
    }
    print(f"\n{'='*64}\n{name}")
    for lab, m in [("IS ", IS), ("OOS", OOS)]:
        print(f"  {lab}: n={m['n']:3d} wr={m['wr']:.0%} ret={m['ret']:+.1%} "
              f"Sharpe={m['sharpe']:.2f} DD={m['dd']:.1%}")
    for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
    print(f"  >>> {'✅ PASSES ALL SIX' if all(checks.values()) else '❌ REJECTED'}")
    return all(checks.values())


def m_from_trades(trades, lo, hi):
    sel = [r for (dt, r) in trades if lo <= dt.year <= hi]
    t = pd.Series(sel)
    if len(t) == 0: return dict(n=0, wr=0, ret=0, sharpe=0, dd=0)
    eq = (1+t).cumprod()
    return dict(n=len(t), wr=(t > 0).mean(), ret=eq.iloc[-1]-1,
                sharpe=t.mean()/t.std()*np.sqrt(len(t)) if t.std() > 0 else 0,
                dd=(eq/eq.cummax()-1).min())


# ── P2 Ultimate Oscillator ────────────────────────────────────────────────────
def uo(d):
    pc = d["C"].shift(1)
    bp = d["C"] - np.minimum(d["L"], pc)
    tr = np.maximum(d["H"], pc) - np.minimum(d["L"], pc)
    a7 = bp.rolling(7).sum()/tr.rolling(7).sum()
    a14 = bp.rolling(14).sum()/tr.rolling(14).sum()
    a28 = bp.rolling(28).sum()/tr.rolling(28).sum()
    return 100*(4*a7+2*a14+a28)/7


def run_uo(d):
    u = uo(d); trades = []; in_t = False; entry = 0; bars = 0
    for i in range(28, len(d)):
        px = d["C"].iloc[i]
        if in_t:
            bars += 1
            if u.iloc[i] > 70 or bars >= 5:
                trades.append(px/entry-1-SLIP); in_t = False
        elif u.iloc[i-1] < 30 <= u.iloc[i]:
            in_t = True; entry = px; bars = 0
    return trades


# ── P3 Turtle ─────────────────────────────────────────────────────────────────
def run_turtle(d):
    hh = d["H"].rolling(20).max().shift(1); ll = d["L"].rolling(10).min().shift(1)
    trades = []; in_t = False; entry = 0
    for i in range(20, len(d)):
        px = d["C"].iloc[i]
        if in_t:
            if px < ll.iloc[i]:
                trades.append(px/entry-1-SLIP); in_t = False
        elif px > hh.iloc[i]:
            in_t = True; entry = px
    return trades


# ── P4 Cross-sectional momentum (portfolio) ──────────────────────────────────
def run_xsmom():
    closes = {}
    for s in BASKET:
        m = daily(s)["C"].resample("ME").last()
        closes[s] = m
    px = pd.DataFrame(closes).dropna()
    mom = px.shift(1)/px.shift(12) - 1   # 12-1 month
    trades = []
    for i in range(12, len(px)-1):
        dt = px.index[i+1]
        ranks = mom.iloc[i].dropna().sort_values(ascending=False)
        if len(ranks) < 3: continue
        top = ranks.index[:max(1, len(ranks)//5)]   # top ~20%
        nxt = px.iloc[i+1]/px.iloc[i] - 1
        r = nxt[top].mean() - SLIP
        trades.append((dt, r))
    return trades


# single-asset strategies: pool across basket for trade count
for name, fn in [("P2 Ultimate Oscillator (7,14,28)", run_uo),
                 ("P3 Turtle (20H/10L breakout)", run_turtle)]:
    pooled = []
    for s in BASKET:
        for r in fn(daily(s)):
            pooled.append((None, r))  # placeholder dt
    # need dates for IS/OOS — redo per-symbol with dates
    pooled = []
    for s in BASKET:
        d = daily(s)
        # re-run capturing exit dates
        if fn is run_uo:
            u = uo(d); in_t=False; entry=0; bars=0
            for i in range(28, len(d)):
                px=d["C"].iloc[i]
                if in_t:
                    bars+=1
                    if u.iloc[i]>70 or bars>=5: pooled.append((d.index[i], px/entry-1-SLIP)); in_t=False
                elif u.iloc[i-1]<30<=u.iloc[i]: in_t=True; entry=px; bars=0
        else:
            hh=d["H"].rolling(20).max().shift(1); ll=d["L"].rolling(10).min().shift(1)
            in_t=False; entry=0
            for i in range(20, len(d)):
                px=d["C"].iloc[i]
                if in_t:
                    if px<ll.iloc[i]: pooled.append((d.index[i], px/entry-1-SLIP)); in_t=False
                elif px>hh.iloc[i]: in_t=True; entry=px
    six_filters(m_from_trades(pooled, 2019, 2022),
                m_from_trades(pooled, 2023, 2026), name + "  [pooled basket]")

xs = run_xsmom()
six_filters(m_from_trades(xs, 2019, 2022),
            m_from_trades(xs, 2023, 2026),
            "P4 Cross-sectional momentum (12-1, monthly, top 20%)")
