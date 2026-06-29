"""
xsmom_proper.py — Cross-sectional momentum on a PROPER diverse universe.

The doc's P4 failed on 7 correlated names. Here we give it what it needs:
real dispersion. Two universes, both downloaded fresh from yfinance:

  A) 11 SPDR sector ETFs (XLK XLF XLE XLV XLU XLP XLI XLB XLRE XLC XLY)
  B) 8 cross-asset sleeves (SPY QQQ IWM EFA EEM TLT GLD DBC) — stocks/intl/bonds/cmdty

Strategy: 12-1 month momentum, rank, long top ~30%, monthly rebalance, equal
weight, costs on. Run through the same six filters, IS (pre-2022) vs OOS (2022+).
Also report vs SPY buy-hold so we know if it actually adds anything.
"""
import pandas as pd, numpy as np, warnings
import yfinance as yf
from datetime import date
warnings.filterwarnings("ignore")

SLIP = 0.0010   # monthly rebalance, ETF — round-trip turnover cost
SECTORS = ["XLK","XLF","XLE","XLV","XLU","XLP","XLI","XLB","XLRE","XLC","XLY"]
CROSS   = ["SPY","QQQ","IWM","EFA","EEM","TLT","GLD","DBC"]


def monthly_closes(tickers, start="2010-01-01"):
    raw = yf.download(tickers, start=start, end=str(date.today()),
                      progress=False, auto_adjust=True)["Close"]
    if isinstance(raw, pd.Series): raw = raw.to_frame()
    m = raw.resample("ME").last()
    return m.dropna(how="all")


def run_xsmom(px, top_frac=0.30):
    """Return (monthly_return_series, trade_returns_with_dates)."""
    mom = px.shift(1) / px.shift(12) - 1
    rets, trades = [], []
    for i in range(12, len(px) - 1):
        dt = px.index[i + 1]
        score = mom.iloc[i].dropna()
        valid = px.iloc[i].notna() & px.iloc[i + 1].notna()
        avail = valid.index[valid]
        score = score[score.index.isin(avail)]
        if len(score) < 4:
            continue
        n = max(1, int(round(len(score) * top_frac)))
        top = score.sort_values(ascending=False).index[:n]
        fwd = (px.iloc[i + 1][top] / px.iloc[i][top] - 1).mean() - SLIP
        rets.append((dt, fwd))
        trades.append((dt, fwd))
    return rets, trades


def stats(rets, lo, hi):
    sel = [(d, r) for (d, r) in rets if lo <= d.year <= hi]
    if not sel: return None
    r = pd.Series([x[1] for x in sel])
    eq = (1 + r).cumprod()
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else 0
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    return dict(n=len(r), wr=(r > 0).mean(), ret=eq.iloc[-1] - 1, cagr=cagr,
                sharpe=sharpe, dd=(eq / eq.cummax() - 1).min())


def spy_bench(lo, hi):
    spy = monthly_closes(["SPY"])["SPY"].pct_change().dropna()
    spy = spy[(spy.index.year >= lo) & (spy.index.year <= hi)]
    eq = (1 + spy).cumprod()
    return dict(cagr=eq.iloc[-1] ** (12/len(spy)) - 1,
                sharpe=spy.mean()/spy.std()*np.sqrt(12),
                dd=(eq/eq.cummax()-1).min())


def gauntlet(name, rets):
    IS, OOS = stats(rets, 2010, 2021), stats(rets, 2022, 2026)
    print(f"\n{'='*64}\n{name}")
    for lab, m in [("IS  (2010-21)", IS), ("OOS (2022-26)", OOS)]:
        print(f"  {lab}: n={m['n']:3d} wr={m['wr']:.0%} CAGR={m['cagr']:+.1%} "
              f"Sharpe={m['sharpe']:.2f} maxDD={m['dd']:.1%}")
    b = spy_bench(2022, 2026)
    print(f"  SPY bench OOS : CAGR={b['cagr']:+.1%} Sharpe={b['sharpe']:.2f} maxDD={b['dd']:.1%}")
    checks = {
        "[01] OOS Sharpe>0.5": OOS["sharpe"] > 0.5,
        "[02] maxDD>-35%":     OOS["dd"] > -0.35,
        "[03] OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
        "[04] not overfit":    OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
        "[05] >=30 trades":    OOS["n"] >= 30,
        "[06] IS Sharpe>0":    IS["sharpe"] > 0,
    }
    for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
    beats = OOS["sharpe"] > b["sharpe"]
    print(f"  Beats SPY (risk-adj)? {'YES' if beats else 'NO'}")
    print(f"  >>> {'PASSES ALL SIX' if all(checks.values()) else 'REJECTED'}")


for nm, univ in [("A) 11 SPDR sectors", SECTORS), ("B) 8 cross-asset sleeves", CROSS)]:
    px = monthly_closes(univ)
    print(f"\n### {nm}: {list(px.columns)} | {px.index.min().date()}→{px.index.max().date()}")
    rets, _ = run_xsmom(px)
    gauntlet(nm, rets)
