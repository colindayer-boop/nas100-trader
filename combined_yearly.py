"""
Honest per-year returns for the VALIDATED strategies (S1 + S4, GEX-filtered).
Each strategy resets to $10k at the start of each year => clean annual return %.
We project on S1+S4 (QQQ) only — these are the two that survived OOS testing.
S2/S3/S5 are excluded (data-plumbing bugs gave near-zero trades; TBD).
"""
import pandas as pd, numpy as np, pytz, warnings
from datetime import date, timedelta
import yfinance as yf
warnings.filterwarnings("ignore")
eastern=pytz.timezone("US/Eastern"); START,END="2019-01-01","2023-12-31"
df=pd.read_csv("qqq_hourly_7y.csv"); df["timestamp"]=pd.to_datetime(df["timestamp"],utc=True)
df=df.set_index("timestamp").tz_convert(eastern)
q=df[df["symbol"]=="QQQ"][["open","high","low","close","volume"]].copy()
q.columns=["Open","High","Low","Close","Volume"]
q=q[(q.index.date>=pd.Timestamp(START).date())&(q.index.date<=pd.Timestamp(END).date())]; q["Date"]=q.index.date
gex=pd.read_csv("gex_history.csv",index_col=0); gex.index=pd.to_datetime(gex.index).date
gex_map=(gex["gex"] if "gex" in gex.columns else gex.iloc[:,0]).to_dict()
vix=yf.download("^VIX",start=START,end=str(date.today()),progress=False)["Close"]
if isinstance(vix,pd.DataFrame): vix=vix.iloc[:,0]
vix.index=pd.to_datetime(vix.index).tz_localize(None).normalize(); vma=vix.rolling(21).mean()
spy=yf.download("SPY",start=str(pd.Timestamp(START)-timedelta(days=365)),end=str(date.today()),progress=False)["Close"]
if isinstance(spy,pd.DataFrame): spy=spy.iloc[:,0]
spy.index=pd.to_datetime(spy.index).tz_localize(None).normalize(); sbull=spy.ewm(span=50).mean()>spy.ewm(span=200).mean()
def asof(s,dts):
    m=s.reindex(s.index.union(dts)).ffill(); r=m.asof(dts); r.index=[t.date() for t in r.index]; return r
dts=pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(q["Date"].unique())]); vix_by=asof(vma,dts); bull_by=asof(sbull,dts)
def vmult(d):
    v=vix_by.get(d,np.nan); return 1.0 if pd.isna(v) else (0.0 if v>25 else (0.5 if v>=20 else 1.0))
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
q["SB"]=q["Date"].map(bull_by).fillna(True).astype(bool)
q["NG"]=q["Date"].map(lambda d:gex_map.get(d,0)<0 if d in gex_map else True)
q["SL"]=(q["Low"]<q["AL"])&(q["Close"]>q["AL"])
q["S1"]=(q["SL"]&q["InS"]&(q["Close"]>q["VWAP"])&(q["Close"]>q["EMA50"])&q["SB"]&~q["HV"]&q["AL"].notna()&q["NG"]).astype(int)
q["S4"]=(q["SL"]&q["InS"]&(q["Close"]>q["EMA50"])&(q["EMA50"]>q["EMA200"])&~q["HV"]&q["AL"].notna()&q["NG"]).astype(int)

def yearly(sig, risk, sl=0.015, rr=3.0):
    out={}
    for Y in range(2019,2024):
        cap=init=10_000; in_t=False; entry=stop=tgt=sh=0.; ds=cap; cur=None; lock=False
        for i in range(1,len(q)):
            if q.index[i].year!=Y: continue
            d=q.index[i].date(); price=float(q["Close"].iloc[i]); s=int(sig.iloc[i-1]); vm=vmult(q.index[i-1].date())
            if d!=cur: cur=d; ds=cap; lock=False
            if (cap-ds)/max(ds,1)<=-0.05 or (cap-init)/init<=-0.10: lock=True
            if lock: continue
            if in_t:
                if price<=stop: cap+=sh*(stop-entry); in_t=False
                elif price>=tgt: cap+=sh*(tgt-entry); in_t=False
            elif s==1 and vm>0:
                in_t=True; entry=price; stop=price*(1-sl); tgt=price*(1+sl*rr); sh=(cap*risk*vm)/(price*sl)
        out[Y]=(cap-init)/init
    return out

s1=yearly(q["S1"],0.007); s4=yearly(q["S4"],0.005)
print("\n"+"="*58)
print("PER-YEAR RETURN — current frozen system (S1 + S4, GEX)")
print("="*58)
print(f"{'Year':>6}{'S1 %':>10}{'S4 %':>10}{'Combined':>12}")
print("-"*58)
combo={}
for Y in range(2019,2024):
    c=s1[Y]+s4[Y]; combo[Y]=c
    print(f"{Y:>6}{s1[Y]:>+10.1%}{s4[Y]:>+10.1%}{c:>+12.1%}")
print("-"*58)
avg_all=np.mean([combo[Y] for Y in range(2019,2024)])
avg_oos=np.mean([combo[Y] for Y in (2022,2023)])
print(f"{'5yr avg':>6}{'':>20}{avg_all:>+12.1%}")
print(f"{'OOS avg 22-23':>19}{'':>7}{avg_oos:>+12.1%}")

print("\n"+"="*58)
print("$50k PROP ACCOUNT — MONTHLY PROFIT PROJECTION")
print("="*58)
print("Assumes The5%ers $50k account, 80% profit split to trader.")
for label, annual in [("Optimistic (5yr avg, incl 2020-21 bull)", avg_all),
                      ("Realistic (OOS 2022-23 only)", avg_oos),
                      ("Conservative (worst year = 2022)", combo[2022])]:
    gross=50_000*annual; monthly_net=(gross/12)*0.80
    print(f"\n{label}:")
    print(f"   Annual {annual:+.1%}  =  ${gross:>+8,.0f}/yr gross  ->  ${monthly_net:>+7,.0f}/mo net")
print("\nNOTE: S2/S3/S5 excluded (backtest data bugs -> near-zero trades).")
print("Fix + paper-test before trusting. SPY leg of S4 not included either.")
print("="*58)
