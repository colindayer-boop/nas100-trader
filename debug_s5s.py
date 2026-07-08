"""
Debug script to analyze why S5 ORB Short isn't generating signals
"""
import pandas as pd
import numpy as np
import pytz
from datetime import date, timedelta
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")
eastern=pytz.timezone("US/Eastern"); START,END="2019-01-01","2023-12-31"

# Load QQQ data (same as full_yearly.py)
df=pd.read_csv("qqq_hourly_7y.csv"); df["timestamp"]=pd.to_datetime(df["timestamp"],utc=True)
df=df.set_index("timestamp").tz_convert(eastern)
q=df[df["symbol"]=="QQQ"][["open","high","low","close","volume"]].copy()
q.columns=["Open","High","Low","Close","Volume"]
q=q[(q.index.date>=pd.Timestamp(START).date())&(q.index.date<=pd.Timestamp(END).date())]; q["Date"]=q.index.date

# Get GEX data
gex=pd.read_csv("gex_history.csv",index_col=0); gex.index=pd.to_datetime(gex.index).date
gex_map=(gex["gex"] if "gex" in gex.columns else gex.iloc[:,0]).to_dict()

# Get VIX data (regime filter)
vix=yf.download("^VIX",start=START,end=str(date.today()),progress=False)["Close"]
if isinstance(vix,pd.DataFrame): vix=vix.iloc[:,0]
vix.index=pd.to_datetime(vix.index).tz_localize(None).normalize(); vma=vix.rolling(21).mean()

# Get SPY data (regime filter) - with error handling
try:
    spy=yf.download("SPY",start=str(pd.Timestamp(START)-timedelta(days=365)),end=str(date.today()),progress=False)["Close"]
    if isinstance(spy,pd.DataFrame): spy=spy.iloc[:,0]
    spy.index=pd.to_datetime(spy.index).tz_localize(None).normalize(); sbull=spy.ewm(span=50).mean()>spy.ewm(span=200).mean()
except Exception as e:
    print(f"Warning: Could not download SPY data: {e}")
    # Create dummy data
    spy = pd.Series(index=pd.date_range(start=START, end=END), data=True)
    sbull = pd.Series(index=spy.index, data=True)

def asof(s,dts):
    m=s.reindex(s.index.union(dts)).ffill(); r=m.asof(dts); r.index=[t.date() for t in r.index]; return r

dts=pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(q["Date"].unique())]); vix_by=asof(vma,dts); bull_by=asof(sbull,dts)

def vmult(d):
    v=vix_by.get(d,np.nan); return 1.0 if pd.isna(v) else (0.0 if v>25 else (0.5 if v>=20 else 1.0))

def neg_gex(d): return gex_map.get(d,0)<0 if d in gex_map else True
def is_bull(d): return bool(bull_by.get(d,True))

# Shared QQQ features (same as full_yearly.py)
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
q["NG"]=q["Date"].map(neg_gex)
q["SL"]=(q["Low"]<q["AL"])&(q["Close"]>q["AL"])

# S5 ORB (hourly approx): opening range = hour-9 bar; breakout in hours 10-13
orb=q[q.index.hour==9].copy(); orb_hi={d:r["High"] for d,r in zip(orb["Date"],orb.to_dict("records"))}
orb_lo={d:r["Low"]  for d,r in zip(orb["Date"],orb.to_dict("records"))}
q["ORBHi"]=q["Date"].map(orb_hi); q["ORBLo"]=q["Date"].map(orb_lo)
q["ORBwin"]=q.index.map(lambda x:10<=x.hour<=13)

# S5 signals
q["S5L"]=(q["ORBwin"]&(q["Close"]>q["ORBHi"])&q["SB"]&q["NG"]&q["ORBHi"].notna()).astype(int)
q["S5S"]=(q["ORBwin"]&(q["Close"]<q["ORBLo"])&~q["SB"]&q["ORBLo"].notna()).astype(int)

# Analysis
print("=== S5 ORB Long/Short Signal Analysis ===")
print(f"Total days: {q['Date'].nunique()}")

# Count signals by year
for year in range(2019, 2024):
    year_data = q[q.index.year == year]
    long_signals = year_data["S5L"].sum()
    short_signals = year_data["S5S"].sum()
    print(f"{year}: Long={long_signals:3d}, Short={short_signals:3d}")

print("\n=== Detailed Analysis for 2022 (worst year) ===")
year_2022 = q[q.index.year == 2022]
print(f"Days in 2022: {len(year_2022)}")
print(f"Long signals: {year_2022['S5L'].sum()}")
print(f"Short signals: {year_2022['S5S'].sum()}")

if year_2022['S5S'].sum() == 0:
    print("\nChecking conditions for short signals in 2022:")
    print(f"ORB window bars: {year_2022['ORBwin'].sum()}")
    print(f"Close < ORB Low: {(year_2022['Close'] < year_2022['ORBLo']).sum()}")
    print(f"NOT SPY bullish: {(~year_2022['SB']).sum()}")
    print(f"ORB Low not null: {year_2022['ORBLo'].notna().sum()}")

    # Check combined conditions
    cond1 = year_2022['ORBwin']
    cond2 = year_2022['Close'] < year_2022['ORBLo']
    cond3 = ~year_2022['SB']
    cond4 = year_2022['ORBLo'].notna()

    print(f"\nCondition breakdown:")
    print(f"ORB window (10am-1pm): {cond1.sum()}")
    print(f"Breakdown (Close < ORB Low): {cond2.sum()}")
    print(f"SPY bearish (not SB): {cond3.sum()}")
    print(f"ORB Low valid: {cond4.sum()}")

    combined = cond1 & cond2 & cond3 & cond4
    print(f"All conditions met: {combined.sum()}")

    if combined.sum() == 0:
        print("\nLooking at cases where 3/4 conditions are met:")
        three_of_four = (cond1 & cond2 & cond3) | (cond1 & cond2 & cond4) | (cond1 & cond3 & cond4) | (cond2 & cond3 & cond4)
        print(f"Three of four conditions: {three_of_four.sum()}")

        if three_of_four.sum() > 0:
            print("\nExamples of near-misses:")
            near_misses = year_2022[three_of_four].head(3)
            for idx, row in near_misses.iterrows():
                miss_reasons = []
                if not (idx.hour >= 10 and idx.hour <= 13): miss_reasons.append("not in ORB window")
                if not (row['Close'] < row['ORBLo']): miss_reasons.append("no breakdown")
                if not (row['SB'] == False): miss_reasons.append("SPY not bearish")
                if not (pd.notna(row['ORBLo'])): miss_reasons.append("ORB Low null")
                print(f"  {idx}: {', '.join(miss_reasons)}")

print("\n=== Sample ORB values ===")
sample_days = q[q.index.hour == 9].head(3)
for idx, row in sample_days.iterrows():
    date = idx.date()
    print(f"{date}: ORB High={row['High']:.2f}, ORB Low={row['Low']:.2f}, Close={row['Close']:.2f}")