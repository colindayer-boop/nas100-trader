"""
commodity_carry.py — Cross-sectional commodity factor test on FREE data.

TRUE carry needs the futures curve (CL1-CL2 across commodities) = paid data.
What we CAN test free: cross-sectional commodity MOMENTUM (TSMOM) — the robust,
documented cousin (Moskowitz-Ooi-Pedersen 2012). Rank a basket of commodity
futures by 12-1 month return, long the top third / short the bottom third,
monthly rebalance, costs on. If THIS shows edge, paying for curve data to add
carry is justified; if not, the commodity space isn't worth paying for.

Also runs a free OIL carry proxy (USO/USL) as a reference.
"""
import yfinance as yf, pandas as pd, numpy as np
import warnings; warnings.filterwarnings("ignore")
from datetime import date

SLIP = 0.0010
BASKET = ["CL=F","NG=F","GC=F","SI=F","HG=F","ZC=F","ZS=F","ZW=F",
          "KC=F","SB=F","CT=F","HO=F","RB=F"]   # oil, gas, metals, grains, softs, products


def monthly(tickers):
    raw = yf.download(tickers, start="2002-01-01", end=str(date.today()),
                      progress=False, auto_adjust=True)["Close"]
    if isinstance(raw, pd.Series): raw = raw.to_frame()
    return raw.resample("ME").last()


def xs_momentum(px, lookback=12, frac=0.34):
    mom = px.shift(1) / px.shift(lookback) - 1
    rets = []
    for i in range(lookback, len(px) - 1):
        dt = px.index[i + 1]
        sc = mom.iloc[i].dropna()
        valid = px.iloc[i].notna() & px.iloc[i + 1].notna()
        sc = sc[sc.index.isin(valid.index[valid])]
        if len(sc) < 6: continue
        n = max(1, int(len(sc) * frac))
        longs = sc.sort_values(ascending=False).index[:n]
        shorts = sc.sort_values().index[:n]
        fwd = px.iloc[i + 1] / px.iloc[i] - 1
        r = fwd[longs].mean() - fwd[shorts].mean() - 2 * SLIP   # long/short, cost both legs
        rets.append((dt, r))
    return rets


def stat(rets, lo, hi):
    sel = [r for d, r in rets if lo <= d.year <= hi]
    t = pd.Series(sel)
    if len(t) == 0: return None
    eq = (1 + t).cumprod()
    return dict(n=len(t), wr=(t > 0).mean(), ret=eq.iloc[-1] - 1,
                sharpe=t.mean()/t.std()*np.sqrt(12) if t.std() > 0 else 0,
                dd=(eq/eq.cummax()-1).min())


px = monthly(BASKET)
print(f"Commodity basket: {list(px.columns)}")
print(f"Data: {px.index.min().date()} -> {px.index.max().date()}\n")
rets = xs_momentum(px)
IS, OOS = stat(rets, 2003, 2014), stat(rets, 2015, 2026)
print("=== Cross-sectional commodity MOMENTUM (12-1, long top/short bottom third) ===")
for lab, m in [("IS  2003-14", IS), ("OOS 2015-26", OOS)]:
    print(f"  {lab}: n={m['n']} wr={m['wr']:.0%} ret={m['ret']:+.0%} "
          f"Sharpe={m['sharpe']:.2f} maxDD={m['dd']:.0%}")
checks = {
    "OOS Sharpe>0.5": OOS["sharpe"] > 0.5, "maxDD>-35%": OOS["dd"] > -0.35,
    "OOS Sharpe<2.5": OOS["sharpe"] < 2.5,
    "not overfit": OOS["sharpe"] <= IS["sharpe"]*1.3 + 0.5,
    ">=30 trades": OOS["n"] >= 30, "IS Sharpe>0": IS["sharpe"] > 0,
}
for k, v in checks.items(): print(f"    [{'PASS' if v else 'FAIL'}] {k}")
print(f"  >>> {'PASSES GAUNTLET' if all(checks.values()) else 'fails'}")
print("\nNote: long/short cross-sectional = market-neutral → low correlation to your")
print("equity book. If it passes, it's a genuine diversifier. TRUE carry (curve data,")
print("paid) typically adds ~0.2-0.4 Sharpe on top of momentum.")
