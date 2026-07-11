"""ADVERSARIAL REVIEW of Part A (ETF universe expansion) + signal-independence
measurement. Attacks:
  R1 recent-period tilt: yearly attribution + ex-best-year per keeper
  R2 double-counting: full keeper-pairwise correlation matrix (SMH vs SOXX etc.)
  R3 costs doubled to 6 bps/side
  R4 6-split OOS robustness per keeper
  R5 honest pooled Sharpe: trade-day sparsity handled explicitly
Persists keeper daily-return streams to research/results/etf_streams.csv for the
forward-shadow and independence work. Research only.
"""
import os, sys, warnings
import numpy as np, pandas as pd, pytz
warnings.filterwarnings("ignore")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
eastern = pytz.timezone("US/Eastern")
KEEPERS = {  # from universe_expansion.md
    "S1": ["QQQ", "SMH", "XLK", "GLD"],
    "S5": ["QQQ", "SPY", "DIA", "SMH", "SOXX", "XLF", "XLE"],
}
UNIV = sorted({t for v in KEEPERS.values() for t in v})

from datetime import datetime
import pytz as tz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from broker import load_config
cfg = load_config("alpaca")
cl = StockHistoricalDataClient(cfg["key"].strip(), cfg["secret"].strip())
print(f"fetching {len(UNIV)} keeper tickers hourly 2021+...")
raw = cl.get_stock_bars(StockBarsRequest(symbol_or_symbols=UNIV,
        timeframe=TimeFrame.Hour, start=datetime(2021, 1, 1, tzinfo=tz.utc))).df

def prep(sym):
    d = raw.xs(sym, level="symbol").copy()
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(eastern)
    d = d[["open", "high", "low", "close", "volume"]]
    d.columns = ["Open", "High", "Low", "Close", "Volume"]
    d["Date"] = d.index.date
    return d

def features(q):
    q = q.copy()
    q["SD"] = q.index.map(lambda i: (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date())
    ab = q[q.index.map(lambda i: i.hour >= 18 or i.hour < 2)]
    q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
    q["InS"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
    tp = (q["High"]+q["Low"]+q["Close"])/3
    vv, ct, cv, p_ = [], 0.0, 0.0, None
    for i in range(len(q)):
        d = q["Date"].iloc[i]
        if d != p_: ct = cv = 0.0; p_ = d
        v = q["Volume"].iloc[i]
        if v > 0: ct += tp.iloc[i]*v; cv += v
        vv.append(ct/cv if cv > 0 else np.nan)
    q["VWAP"] = vv
    dc = q[q.index.hour == 16][["Close"]].copy(); dc.index = dc.index.date
    dc = dc[~dc.index.duplicated(keep="last")]
    q["EMA50"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
    pc = q["Close"].shift(1)
    tr = pd.concat([q["High"]-q["Low"], (q["High"]-pc).abs(), (q["Low"]-pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean(); q["HV"] = atr > 1.5*atr.rolling(200).mean()
    q["S1"] = ((q["Low"] < q["AL"]) & (q["Close"] > q["AL"]) & q["InS"] & (q["Close"] > q["VWAP"])
               & (q["Close"] > q["EMA50"]) & ~q["HV"] & q["AL"].notna()).astype(int)
    orb = q[q.index.hour == 9]
    q["OH"] = q["Date"].map({d: h for d, h in zip(orb["Date"], orb["High"])})
    q["OV"] = q["Date"].map({d: v for d, v in zip(orb["Date"], orb["Volume"])})
    q["S5"] = (q.index.map(lambda x: 10 <= x.hour <= 13) & (q["Close"] > q["OH"])
               & q["OH"].notna() & (q["Volume"] > q["OV"]*0.6)).astype(int)
    return q

def run(q, col, risk, sl, rr, slip=0.0003):
    cap = 10_000.0; in_t = False; entry = stop = tgt = sh = 0.0
    day_traded = None; daily_eq = {}
    sig = q[col].values; close = q["Close"].values; dates = q["Date"].values
    for i in range(1, len(q)):
        price = close[i]; d = dates[i]
        if in_t:
            if price <= stop: cap += sh*(stop-entry)-sh*(entry+stop)*slip; in_t = False
            elif price >= tgt: cap += sh*(tgt-entry)-sh*(entry+tgt)*slip; in_t = False
        elif sig[i-1] == 1 and day_traded != d:
            in_t = True; day_traded = d; entry = price
            stop = price*(1-sl); tgt = price*(1+sl*rr); sh = (cap*risk)/(price*sl)
        daily_eq[d] = cap
    eq = pd.Series(daily_eq).sort_index()
    return eq.pct_change().dropna()

P = {"S1": (0.007, 0.015, 3.0), "S5": (0.0075, 0.010, 3.0)}
streams, streams6 = {}, {}
feats = {sym: features(prep(sym)) for sym in UNIV}
for sname, syms in KEEPERS.items():
    for sym in syms:
        r, s, rr_ = P[sname]
        streams[f"{sname}_{sym}"] = run(feats[sym], sname, r, s, rr_)
        streams6[f"{sname}_{sym}"] = run(feats[sym], sname, r, s, rr_, slip=0.0006)
S = pd.DataFrame(streams)
S.index = pd.to_datetime(S.index)
S.to_csv(os.path.join(REPO, "research", "results", "etf_streams.csv"))

def shp(x):
    x = x.dropna()
    return x.mean()/x.std()*np.sqrt(252) if len(x) > 40 and x.std() > 0 else np.nan

out = ["# ETF universe expansion — ADVERSARIAL REVIEW + independence",
       f"\n_{len(streams)} keeper streams, 2021+. Streams persisted to etf_streams.csv._\n",
       "## R1/R3/R4 — per-keeper attack table",
       "| stream | Sharpe | 6bps | ex-best-yr | min 6-split OOS | verdict |",
       "|---|---|---|---|---|---|"]
survivors = []
for k in streams:
    r = streams[k]; ri = r.copy(); ri.index = pd.to_datetime(ri.index)
    yearly = (1+ri).groupby(ri.index.year).prod()
    best = yearly.idxmax()
    exb = shp(ri[ri.index.year != best])
    c6 = shp(streams6[k])
    sp = [shp(ri.iloc[int(len(ri)*f):]) for f in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7)]
    base = shp(ri)
    ok = (not np.isnan(exb) and exb > 0.2 and c6 > 0.3 and min(sp) > 0.2)
    if ok: survivors.append(k)
    out.append(f"| {k} | {base:.2f} | {c6:.2f} | {exb:.2f} | {min(sp):.2f} | "
               f"{'SURVIVES' if ok else 'FAILS review'} |")

out.append("\n## R2 — keeper-pairwise correlation (independence measurement)")
C = S[survivors].corr()
pairs = [(a, b, C.loc[a, b]) for i, a in enumerate(survivors) for b in survivors[i+1:]]
hi = [(a, b, c) for a, b, c in pairs if c > 0.5]
avg = np.mean([c for _, _, c in pairs])
out.append(f"- survivors: {len(survivors)} | avg pairwise corr **{avg:.2f}** | pairs >0.5: "
           + (", ".join(f"{a}~{b} ({c:.2f})" for a, b, c in hi) if hi else "none"))
# drop the weaker member of each >0.5 pair (no tuning -- Sharpe rank, pre-registered)
drop = set()
for a, b, c in hi:
    weaker = a if shp(streams[a]) < shp(streams[b]) else b
    drop.add(weaker)
final = [k for k in survivors if k not in drop]
out.append(f"- de-duplicated set ({len(final)}): {final}" + (f" | dropped: {sorted(drop)}" if drop else ""))

out.append("\n## R5 — honest pooled portfolio (de-duplicated survivors)")
pool = S[final].fillna(0).mean(axis=1)
act = S[final].notna().any(axis=1)
pool = pool[act]
out.append(f"- pooled Sharpe (equal weight, zero on inactive days): **{shp(pool):.2f}** | "
           f"active days {act.mean():.0%} | MaxDD {((1+pool).cumprod()/(1+pool).cumprod().cummax()-1).min():.1%}")
sp = [shp(pool.iloc[int(len(pool)*f):]) for f in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7)]
out.append(f"- pooled 6-split OOS Sharpe: {' '.join(f'{x:.2f}' for x in sp)} | min {min(sp):.2f}")

verdict = ("VALIDATED_FOR_FORWARD_SHADOW" if len(final) >= 6 and shp(pool) > 1.2 and min(sp) > 0.8
           else "NEEDS_MORE_EVIDENCE")
out.append(f"\n## Verdict: **{verdict}**")
out.append("Conditions: forward-shadow every survivor (no live orders); 2021+ sample and "
           "OOS>IS tilt remain open concerns that only forward evidence resolves; "
           "CFD-mapped subset (QQQ/SPY/DIA/GLD) is the only prop-relevant portion.")
path = os.path.join(REPO, "research", "results", "universe_expansion_REVIEW.md")
open(path, "w").write("\n".join(out) + "\n")
print("\n".join(out))
