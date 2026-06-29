"""
mean_reversion_portfolio.py — REALISTIC capital-constrained portfolio sim of the
RSI-2 basket. Fixes the fantasy Sharpe from naive pooling by enforcing:
  - one shared account ($100k), equal-weight 1/N capital per slot
  - MAX_CONCURRENT cap (can't be in everything at once)
  - crash guard: no NEW entries when VIX>30 OR SPY below its 200-day SMA
  - 3% hard stop, exit on close>5-day SMA, costs on every fill
Daily equity curve → real Sharpe / maxDD / CAGR, split IS vs OOS, six filters.
"""
import pandas as pd, numpy as np, warnings
import yfinance as yf
from datetime import date
from mean_reversion_test import load, rsi, SLIP
warnings.filterwarnings("ignore")

BASKET = ["QQQ", "SPY", "IWM", "GLD", "AAPL", "MSFT", "NVDA"]
INIT = 100_000.0
MAX_CONCURRENT = 5
STOP = 0.03
VIX_GUARD = 30.0

# ── daily panels ──────────────────────────────────────────────────────────────
def daily_panel(sym):
    df = load(sym)
    d = pd.DataFrame({"Close": df["Close"].resample("1D").last()}).dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    d["RSI"] = rsi(d["Close"], 2)
    d["SMA200"] = d["Close"].rolling(200).mean()
    d["SMA5"] = d["Close"].rolling(5).mean()
    return d

panels = {s: daily_panel(s) for s in BASKET}
all_dates = sorted(set().union(*[set(p.index) for p in panels.values()]))

# market regime: VIX + SPY 200SMA
vix = yf.download("^VIX", start="2019-01-01", end=str(date.today()), progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:, 0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
spy_close = panels["SPY"]["Close"]; spy200 = panels["SPY"]["SMA200"]

def guarded(dt):
    v = vix.asof(pd.Timestamp(dt))
    sp, s200 = spy_close.asof(pd.Timestamp(dt)), spy200.asof(pd.Timestamp(dt))
    if pd.notna(v) and v > VIX_GUARD: return True
    if pd.notna(sp) and pd.notna(s200) and sp < s200: return True
    return False

# ── event-driven sim ──────────────────────────────────────────────────────────
def simulate():
    cash = INIT; positions = {}; equity_curve = []; trades = []
    for dt in all_dates:
        # mark-to-market exits first
        for s in list(positions.keys()):
            p = panels[s]
            if dt not in p.index: continue
            px = p.at[dt, "Close"]; pos = positions[s]
            ret = px / pos["entry"] - 1
            if ret <= -STOP or px > p.at[dt, "SMA5"]:
                pnl = pos["shares"] * (px * (1 - SLIP) - pos["entry"])
                cash += pos["shares"] * px * (1 - SLIP)
                trades.append((dt, ret - SLIP)); del positions[s]
        # entries (respect concurrency + crash guard)
        if not guarded(dt):
            slots = MAX_CONCURRENT - len(positions)
            if slots > 0:
                cands = []
                for s, p in panels.items():
                    if s in positions or dt not in p.index: continue
                    if pd.isna(p.at[dt, "SMA200"]): continue
                    if p.at[dt, "RSI"] < 10 and p.at[dt, "Close"] > p.at[dt, "SMA200"]:
                        cands.append((p.at[dt, "RSI"], s))
                cands.sort()  # most oversold first
                # current total equity for sizing
                eq = cash + sum(positions[s]["shares"] * panels[s]["Close"].asof(pd.Timestamp(dt))
                                for s in positions)
                alloc = eq / MAX_CONCURRENT
                for _, s in cands[:slots]:
                    px = panels[s].at[dt, "Close"]
                    if cash < alloc: continue
                    sh = alloc / (px * (1 + SLIP))
                    cash -= sh * px * (1 + SLIP)
                    positions[s] = {"entry": px * (1 + SLIP), "shares": sh}
        eq = cash + sum(positions[s]["shares"] * panels[s]["Close"].asof(pd.Timestamp(dt))
                        for s in positions)
        equity_curve.append((dt, eq))
    return pd.Series(dict(equity_curve)), trades

eq, trades = simulate()
eq.index = pd.to_datetime(eq.index)

def stats(e, tr, lo, hi):
    mask = (e.index.year >= lo) & (e.index.year <= hi)
    es = e[mask]
    if len(es) < 5: return None
    r = es.pct_change().dropna()
    sharpe = r.mean()/r.std()*np.sqrt(252) if r.std() > 0 else 0
    dd = (es/es.cummax()-1).min()
    yrs = (es.index[-1]-es.index[0]).days/365.25
    cagr = (es.iloc[-1]/es.iloc[0])**(1/yrs)-1 if yrs > 0 else 0
    n = sum(1 for (dt, _) in tr if lo <= dt.year <= hi)
    wins = [r for (dt, r) in tr if lo <= dt.year <= hi and r > 0]
    wr = len(wins)/n if n else 0
    return dict(sharpe=sharpe, dd=dd, cagr=cagr, n=n, wr=wr, ret=es.iloc[-1]/es.iloc[0]-1)

IS, OOS = stats(eq, trades, 2019, 2022), stats(eq, trades, 2023, 2026)
print(f"REALISTIC PORTFOLIO SIM — RSI-2 basket, {MAX_CONCURRENT} max concurrent, "
      f"VIX>{VIX_GUARD:.0f}/SPY<200SMA crash guard, costs on\n")
for label, m in [("IS  (2019-22)", IS), ("OOS (2023-26)", OOS)]:
    print(f"  {label}: n={m['n']:3d}  wr={m['wr']:.0%}  ret={m['ret']:+.1%}  "
          f"CAGR={m['cagr']:+.1%}  Sharpe={m['sharpe']:.2f}  maxDD={m['dd']:.1%}")
print(f"  Frequency (OOS): {OOS['n']/3.5:.0f}/yr (~{OOS['n']/3.5/52:.1f}/wk)")

checks = {
    "[01] OOS Sharpe>0.5":  OOS["sharpe"] > 0.5,
    "[02] maxDD>-35%":      OOS["dd"] > -0.35,
    "[03] OOS Sharpe<2.5":  OOS["sharpe"] < 2.5,
    "[04] not overfit":     OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
    "[05] >=30 trades":     OOS["n"] >= 30,
    "[06] IS Sharpe>0":     IS["sharpe"] > 0,
}
print("\n  SIX FILTERS:")
for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
print(f"\n  >>> {'✅ PASSES ALL SIX — deployable candidate' if all(checks.values()) else '❌ REJECTED'}")
