"""
A/B TEST: Does the IV Skew filter (Xing, Zhang & Zhao 2010) improve S1?

Xing et al. finding: steep OTM-put skew = informed bearish positioning =
the underlying tends to UNDERPERFORM over the following days/weeks.
=> Interpretation as a DEFENSIVE FILTER: when QQQ put skew is steep,
   skip long entries (we're trading long-only sweeps).

We compare, on the exact same S1 signal set (GEX-filtered baseline):
  A. Baseline               (no skew filter)
  B. Skew filter @ +1.0 sd  (skip longs when skew elevated)
  C. Skew filter @ +1.5 sd
  D. Skew filter @ +2.0 sd
  E. WRONG sign @ +1.0 sd   (only trade WHEN skew steep — to prove direction)
"""
import pandas as pd, numpy as np, glob, os, pytz, warnings
from datetime import date, timedelta
import yfinance as yf
warnings.filterwarnings("ignore")

DATA_DIR  = "/Users/colindayer/nas100_backtest/optionsdx/"
QQQ_CSV   = "/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv"
GEX_CACHE = "/Users/colindayer/nas100_backtest/gex_history.csv"
SKEW_CACHE= "/Users/colindayer/nas100_backtest/skew_history.csv"
START, END = "2019-01-01", "2023-12-31"
eastern = pytz.timezone("US/Eastern")

# ── DAILY IV SKEW (cached) ────────────────────────────────────────────────────
def compute_skew():
    files = sorted(glob.glob(DATA_DIR + "qqq_eod*.txt") + glob.glob(DATA_DIR + "qqq_eod*.csv"))
    recs = []
    for f in files:
        try:
            d0 = pd.read_csv(f, low_memory=False)
            d0.columns = [c.strip().strip("[]").upper() for c in d0.columns]
            dc = next((c for c in d0.columns if "QUOTE_DATE" in c), None)
            uc = next((c for c in d0.columns if "UNDERLYING_LAST" in c), None)
            sc = "STRIKE" if "STRIKE" in d0.columns else None
            ci = "C_IV" if "C_IV" in d0.columns else None
            pi = "P_IV" if "P_IV" in d0.columns else None
            if not all([dc, uc, sc, ci, pi]): continue
            for col in [uc, sc, ci, pi]:
                d0[col] = pd.to_numeric(d0[col], errors="coerce")
            d0[dc] = pd.to_datetime(d0[dc])
            for dd, grp in d0.groupby(d0[dc].dt.date):
                grp = grp.dropna(subset=[uc, sc, ci, pi])
                if len(grp) < 5: continue
                spot = float(grp[uc].median())
                atm = grp.iloc[(grp[sc]-spot).abs().argsort()[:1]]
                otm = grp.iloc[(grp[sc]-spot*0.95).abs().argsort()[:1]]
                a, o = float(atm[ci].iloc[0]), float(otm[pi].iloc[0])
                if a > 0 and o > 0:
                    recs.append({"date": dd, "skew": o - a})
        except Exception:
            continue
    s = pd.DataFrame(recs).drop_duplicates("date").set_index("date").sort_index()
    s.to_csv(SKEW_CACHE)
    return s

if os.path.exists(SKEW_CACHE):
    print("Loading skew from cache...")
    skew = pd.read_csv(SKEW_CACHE)
    skew["date"] = pd.to_datetime(skew["date"]).dt.date
    skew = skew.set_index("date")
else:
    print("Computing daily IV skew (one-time)...")
    skew = compute_skew()
print(f"  skew: {len(skew)} days | mean={skew['skew'].mean():.3f} sd={skew['skew'].std():.3f}")
skew_map = skew["skew"].to_dict()
sk_mean, sk_sd = skew["skew"].mean(), skew["skew"].std()

# ── PRICE + GEX + REGIME ──────────────────────────────────────────────────────
df = pd.read_csv(QQQ_CSV)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp").tz_convert(eastern)
q = df[df["symbol"]=="QQQ"][["open","high","low","close","volume"]].copy()
q.columns = ["Open","High","Low","Close","Volume"]
q = q[(q.index.date >= pd.Timestamp(START).date()) & (q.index.date <= pd.Timestamp(END).date())]
q["Date"] = q.index.date

gex = pd.read_csv(GEX_CACHE, index_col=0)
gex.index = pd.to_datetime(gex.index).date
gex_map = (gex["gex"] if "gex" in gex.columns else gex.iloc[:,0]).to_dict()

vix = yf.download("^VIX", start=START, end=str(date.today()), progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma = vix.rolling(21).mean()
spy = yf.download("SPY", start=str(pd.Timestamp(START)-timedelta(days=365)), end=str(date.today()), progress=False)["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:,0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_bull = spy.ewm(span=50).mean() > spy.ewm(span=200).mean()

def asof(series, dts):
    m = series.reindex(series.index.union(dts)).ffill(); r = m.asof(dts)
    r.index = [t.date() for t in r.index]; return r
dts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(q["Date"].unique())])
vix_by = asof(vix_ma, dts); bull_by = asof(spy_bull, dts)
def vmult(d):
    v = vix_by.get(d, np.nan)
    if pd.isna(v): return 1.0
    return 0.0 if v > 25 else (0.5 if v >= 20 else 1.0)

# ── S1 SIGNAL (GEX-filtered baseline, intraday) ───────────────────────────────
def is_asian(i): return i.hour >= 18 or i.hour < 2
def sess_date(i): return (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date()
q["Asian"] = q.index.map(is_asian); q["SD"] = q.index.map(sess_date)
ab = q[q["Asian"]]
q["AsianLow"] = q["SD"].map(ab.groupby("SD")["Low"].min())
q["InSession"] = q.index.map(lambda x: (2<=x.hour<5) or (9<=x.hour<12))
tp = (q["High"]+q["Low"]+q["Close"])/3
vv=[]; ct=cv=0.; pd_=None
for i in range(len(q)):
    d=q["Date"].iloc[i]
    if d!=pd_: ct=cv=0.; pd_=d
    if q["Volume"].iloc[i]>0: ct+=tp.iloc[i]*q["Volume"].iloc[i]; cv+=q["Volume"].iloc[i]
    vv.append(ct/cv if cv>0 else float("nan"))
q["VWAP"]=vv
dc=q[q.index.hour==16][["Close"]].copy(); dc.index=dc.index.date
dc=dc[~dc.index.duplicated(keep="last")]
q["EMA50"]=q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
pc=q["Close"].shift(1)
tr=pd.concat([q["High"]-q["Low"],(q["High"]-pc).abs(),(q["Low"]-pc).abs()],axis=1).max(axis=1)
atr=tr.rolling(14).mean(); q["HighVol"]=atr>1.5*atr.rolling(200).mean()
q["SPYBull"]=q["Date"].map(bull_by).fillna(True).astype(bool)
q["NegGEX"]=q["Date"].map(lambda d: gex_map.get(d,0)<0 if d in gex_map else True)
q["Skew"]=q["Date"].map(lambda d: skew_map.get(d, np.nan))
q["SweepLow"]=(q["Low"]<q["AsianLow"])&(q["Close"]>q["AsianLow"])
q["S1base"]=(q["SweepLow"]&q["InSession"]&(q["Close"]>q["VWAP"])&(q["Close"]>q["EMA50"])&
             q["SPYBull"]&~q["HighVol"]&q["AsianLow"].notna()&q["NegGEX"]).astype(int)

# ── BACKTEST ENGINE ───────────────────────────────────────────────────────────
def run(sig, risk=0.007, sl=0.015, rr=3.0):
    cap=init=10_000; trades=[]; in_t=False; entry=stop=tgt=sh=0.
    ds=cap; cur=None; lock=False
    for i in range(1,len(q)):
        d=q.index[i].date(); price=float(q["Close"].iloc[i])
        s=int(sig.iloc[i-1]); vm=vmult(q.index[i-1].date())
        if d!=cur: cur=d; ds=cap; lock=False
        if (cap-ds)/max(ds,1)<=-0.05 or (cap-init)/init<=-0.10: lock=True
        if lock: continue
        if in_t:
            if price<=stop: trades.append(sh*(stop-entry)); cap+=trades[-1]; in_t=False
            elif price>=tgt: trades.append(sh*(tgt-entry)); cap+=trades[-1]; in_t=False
        elif s==1 and vm>0:
            in_t=True; entry=price; stop=price*(1-sl); tgt=price*(1+sl*rr)
            sh=(cap*risk*vm)/(price*sl)
    t=pd.Series(trades)
    if len(t)==0: return dict(ret=0,dd=0,n=0,wr=0,pf=0)
    pf=t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else 99.9
    eq=pd.Series([init]+list(t.cumsum()+init)); dd=((eq-eq.cummax())/eq.cummax()).min()
    return dict(ret=(cap-init)/init, dd=dd, n=len(t), wr=(t>0).mean(), pf=pf)

# ── VARIANTS ──────────────────────────────────────────────────────────────────
def filt(base, thr, invert=False):
    cond = q["Skew"] <= thr if not invert else q["Skew"] > thr
    cond = cond | q["Skew"].isna()   # missing skew => don't filter
    return (base.astype(bool) & cond).astype(int)

variants = {
    "A. Baseline (GEX only, no skew)":      q["S1base"],
    "B. Skew filter  > mean+1.0sd skip":    filt(q["S1base"], sk_mean+1.0*sk_sd),
    "C. Skew filter  > mean+1.5sd skip":    filt(q["S1base"], sk_mean+1.5*sk_sd),
    "D. Skew filter  > mean+2.0sd skip":    filt(q["S1base"], sk_mean+2.0*sk_sd),
    "E. WRONG sign (only when steep skew)": filt(q["S1base"], sk_mean+1.0*sk_sd, invert=True),
}

print("\n"+"="*78)
print("A/B TEST — IV SKEW FILTER ON S1 (Xing, Zhang & Zhao 2010)")
print("="*78)
print(f"{'Variant':<40}{'Return':>9}{'MaxDD':>8}{'Trades':>8}{'WR':>6}{'PF':>7}")
print("-"*78)
base_r=None
for name,sig in variants.items():
    r=run(sig)
    if base_r is None: base_r=r
    print(f"{name:<40}{r['ret']:>+8.1%}{r['dd']:>8.1%}{r['n']:>8}{r['wr']:>6.0%}{r['pf']:>7.2f}")
print("-"*78)
print("Read: if B/C/D beat A on PF & DD without killing return, the filter EARNS its place.")
print("      if E (only-when-steep) is worst, that confirms steep skew = bearish (paper holds).")

# ── S6 FIX TEST: steep skew as SHORT in bear regime (paper-aligned) ───────────
# Xing: steep put skew => underperformance. Long-only fade has no edge (E above).
# Paper-aligned trade = SHORT when skew steep AND market already in downtrend.
print("\n"+"="*78)
print("S6 FIX — steep skew SHORT in bear regime (daily QQQ, multi-day hold)")
print("="*78)

# daily QQQ bars
qd = q.groupby("Date").agg({"Open":"first","High":"max","Low":"min","Close":"last"}).copy()
qd.index = pd.to_datetime(qd.index)
qd["Skew"] = qd.index.map(lambda d: skew_map.get(d.date(), np.nan))
qd["Bear"] = ~qd.index.map(lambda d: bool(bull_by.get(d.date(), True)))
qd["VM"]   = qd.index.map(lambda d: vmult(d.date()))

def run_short(thr_sd, hold, sl, rr):
    cap=init=10_000; trades=[]; in_t=False; entry=stop=tgt=sh=0.; held=0
    thr = sk_mean + thr_sd*sk_sd
    for i in range(1,len(qd)):
        price=float(qd["Close"].iloc[i])
        steep = qd["Skew"].iloc[i-1] > thr
        bear  = bool(qd["Bear"].iloc[i-1]); vm=float(qd["VM"].iloc[i-1])
        if in_t:
            held+=1
            if price>=stop or price<=tgt or held>=hold:
                trades.append(sh*(entry-price)); cap+=trades[-1]; in_t=False
        elif steep and bear and vm>0:
            in_t=True; entry=price; stop=price*(1+sl); tgt=price*(1-sl*rr); held=0
            sh=(cap*0.005*vm)/(price*sl)
    t=pd.Series(trades)
    if len(t)==0: return "no trades"
    pf=t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else 99.9
    eq=pd.Series([init]+list(t.cumsum()+init)); dd=((eq-eq.cummax())/eq.cummax()).min()
    return f"ret={(cap-init)/init:>+7.1%}  DD={dd:>6.1%}  n={len(t):>3}  WR={(t>0).mean():>4.0%}  PF={pf:>5.2f}"

print(f"{'thr':>5} {'hold':>5}  result")
for thr_sd in [1.0, 1.5]:
    for hold in [3, 5, 10]:
        print(f"{thr_sd:>5} {hold:>5}d  {run_short(thr_sd, hold, sl=0.025, rr=2.0)}")
