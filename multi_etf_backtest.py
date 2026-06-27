"""
MULTI-ETF EXPANSION: run the proven Asian-Sweep (S1/S4) logic on new uncorrelated
instruments (IWM small-caps, DIA Dow, TLT bonds) to test the diversification lever.

Key design:
- No GEX filter (QQQ-options-specific) — uses each instrument's OWN trend (EMA50/200).
- Net of transaction costs (same SLIP as full_yearly).
- Reports per-ETF per-year return AND correlation-to-QQQ (the diversification metric).
  Low correlation = genuine diversification = more return at lower portfolio risk.
"""
import pandas as pd, numpy as np, pytz, warnings
from datetime import date, timedelta
import yfinance as yf
warnings.filterwarnings("ignore")
eastern=pytz.timezone("US/Eastern"); START,END="2019-01-01","2023-12-31"; YEARS=range(2019,2024)
SLIP=0.0003

# ── regime (VIX market-wide) ──────────────────────────────────────────────────
vix=yf.download("^VIX",start=START,end=str(date.today()),progress=False)["Close"]
if isinstance(vix,pd.DataFrame): vix=vix.iloc[:,0]
vix.index=pd.to_datetime(vix.index).tz_localize(None).normalize(); vma=vix.rolling(21).mean()
def asof(s,dts):
    m=s.reindex(s.index.union(dts)).ffill(); r=m.asof(dts); r.index=[t.date() for t in r.index]; return r

# ── load multi-ETF hourly ─────────────────────────────────────────────────────
raw=pd.read_csv("multi_etf_hourly.csv")
raw["timestamp"]=pd.to_datetime(raw["timestamp"],utc=True)
raw=raw.set_index("timestamp").tz_convert(eastern)

def build(sym):
    q=raw[raw["symbol"]==sym][["open","high","low","close","volume"]].copy()
    q.columns=["Open","High","Low","Close","Volume"]
    q=q[(q.index.date>=pd.Timestamp(START).date())&(q.index.date<=pd.Timestamp(END).date())]; q["Date"]=q.index.date
    def isA(i): return i.hour>=18 or i.hour<2
    def sd(i): return (i+pd.Timedelta(days=1)).date() if i.hour>=18 else i.date()
    q["A"]=q.index.map(isA); q["SD"]=q.index.map(sd); ab=q[q["A"]]
    q["AL"]=q["SD"].map(ab.groupby("SD")["Low"].min())
    q["InS"]=q.index.map(lambda x:(2<=x.hour<5) or (9<=x.hour<12))
    tp=(q["High"]+q["Low"]+q["Close"])/3; vv=[];ct=cv=0.;p_=None
    for i in range(len(q)):
        d=q["Date"].iloc[i]
        if d!=p_: ct=cv=0.;p_=d
        if q["Volume"].iloc[i]>0: ct+=tp.iloc[i]*q["Volume"].iloc[i];cv+=q["Volume"].iloc[i]
        vv.append(ct/cv if cv>0 else float("nan"))
    q["VWAP"]=vv
    dc=q[q.index.hour==16][["Close"]].copy(); dc.index=dc.index.date; dc=dc[~dc.index.duplicated(keep="last")]
    q["EMA50"]=q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
    q["EMA200"]=q["Date"].map(dc["Close"].ewm(span=200).mean().to_dict())
    pc=q["Close"].shift(1); tr=pd.concat([q["High"]-q["Low"],(q["High"]-pc).abs(),(q["Low"]-pc).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean(); q["HV"]=atr>1.5*atr.rolling(200).mean()
    q["SL"]=(q["Low"]<q["AL"])&(q["Close"]>q["AL"])
    # S1-style: sweep + VWAP + own-trend (EMA50) + uptrend (EMA50>EMA200) + calm
    q["S1"]=(q["SL"]&q["InS"]&(q["Close"]>q["VWAP"])&(q["Close"]>q["EMA50"])&(q["EMA50"]>q["EMA200"])&~q["HV"]&q["AL"].notna()).astype(int)
    dts=pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(q["Date"].unique())]); vix_by=asof(vma,dts)
    return q, vix_by

def run(q, vix_by, sig_col, risk=0.006, sl=0.015, rr=3.0):
    """Returns dict year->ret and a per-day P&L series (for correlation)."""
    def vmult(d):
        v=vix_by.get(d,np.nan); return 1.0 if pd.isna(v) else (0.0 if v>25 else (0.5 if v>=20 else 1.0))
    out={}; daily={}
    for Y in YEARS:
        cap=init=10_000; in_t=False; entry=stop=tgt=sh=0.; ds=cap; cur=None; lock=False; dt=None
        for i in range(1,len(q)):
            if q.index[i].year!=Y: continue
            d=q.index[i].date(); price=float(q["Close"].iloc[i]); s=int(q[sig_col].iloc[i-1]); vm=vmult(q.index[i-1].date())
            if d!=cur: cur=d; ds=cap; lock=False
            if (cap-ds)/max(ds,1)<=-0.05 or (cap-init)/init<=-0.10: lock=True
            if lock: continue
            if in_t:
                if price<=stop: pnl=sh*(stop-entry)-sh*(entry+stop)*SLIP; cap+=pnl; daily[d]=daily.get(d,0)+pnl; in_t=False
                elif price>=tgt: pnl=sh*(tgt-entry)-sh*(entry+tgt)*SLIP; cap+=pnl; daily[d]=daily.get(d,0)+pnl; in_t=False
            elif s==1 and vm>0 and dt!=d:
                in_t=True; dt=d; entry=price; stop=price*(1-sl); tgt=price*(1+sl*rr); sh=(cap*risk*vm)/(price*sl)
        out[Y]=(cap-init)/init
    return out, pd.Series(daily)

# ── run on each new ETF ───────────────────────────────────────────────────────
print("Building + backtesting IWM, DIA, TLT (Asian sweep, net of costs)...")
results={}; daily_series={}
for sym in ["IWM","DIA","TLT"]:
    q,vix_by=build(sym); res,daily=run(q,vix_by,"S1"); results[sym]=res; daily_series[sym]=daily

# QQQ baseline daily P&L for correlation (rebuild quickly from full_yearly's S1)
print("Building QQQ S1 daily P&L for correlation...")
qsrc=open("full_yearly.py").read().split("# ── run all")[0]
ns={}; exec(qsrc, ns)
qq=ns["q"]; vmult=ns["vmult"]
qdaily={}
cap=10_000; in_t=False; entry=stop=tgt=sh=0.; cur=None; ds=cap; lock=False; dt=None
for i in range(1,len(qq)):
    d=qq.index[i].date(); price=float(qq["Close"].iloc[i]); s=int(qq["S1"].iloc[i-1]); vm=vmult(qq.index[i-1].date())
    if d!=cur: cur=d; ds=cap; lock=False
    if (cap-ds)/max(ds,1)<=-0.05 or (cap-10_000)/10_000<=-0.10: lock=True
    if lock: continue
    if in_t:
        if price<=stop: pnl=sh*(stop-entry)-sh*(entry+stop)*SLIP; cap+=pnl; qdaily[d]=qdaily.get(d,0)+pnl; in_t=False
        elif price>=tgt: pnl=sh*(tgt-entry)-sh*(entry+tgt)*SLIP; cap+=pnl; qdaily[d]=qdaily.get(d,0)+pnl; in_t=False
    elif s==1 and vm>0 and dt!=d:
        in_t=True; dt=d; entry=price; stop=price*(1-0.015); tgt=price*(1+0.015*3); sh=(cap*0.007*vm)/(price*0.015)
qqq_daily=pd.Series(qdaily)

# ── report ────────────────────────────────────────────────────────────────────
print("\n"+"="*70)
print("MULTI-ETF EXPANSION — Asian Sweep on new instruments (net of costs)")
print("="*70)
print(f"{'ETF':<8}"+"".join(f"{Y:>9}" for Y in YEARS)+f"{'avg':>9}{'corr→QQQ':>10}{'trades':>8}")
print("-"*70)
idx=pd.bdate_range(START,END)
for sym in ["IWM","DIA","TLT"]:
    r=results[sym]; avg=np.mean([r[Y] for Y in YEARS])
    a=daily_series[sym].reindex(idx).fillna(0); b=qqq_daily.reindex(idx).fillna(0)
    corr=a.corr(b) if a.std()>0 and b.std()>0 else float("nan")
    ntr=int((a!=0).sum())
    print(f"{sym:<8}"+"".join(f"{r[Y]:>+9.1%}" for Y in YEARS)+f"{avg:>+9.1%}{corr:>10.2f}{ntr:>8}")
print("-"*70)
print("corr→QQQ: LOW (<0.3) = genuine diversification (adds return, cuts portfolio risk).")
print("          HIGH (>0.6) = redundant with QQQ (adds little). Negative = hedge.")
