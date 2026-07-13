"""Weekend-exposure audit: current hold (A) vs force-close-Friday (B).
Read-only. No production import. Archetypes: S1/S5 bracket (QQQ hourly), S3 time-exit (QQQ daily).
"""
import warnings, sys, numpy as np, pandas as pd
warnings.filterwarnings("ignore"); sys.path.insert(0, ".")
SLIP, FIN_BPS = 0.0003, 0.0003   # 3bps/side slippage; 3bps/day CFD financing on notional

df = pd.read_csv("qqq_hourly_7y.csv"); df["timestamp"]=pd.to_datetime(df["timestamp"],utc=True)
import pytz; et=pytz.timezone("US/Eastern")
q = df[df["symbol"]=="QQQ"].set_index("timestamp").tz_convert(et)[["open","high","low","close","volume"]]
q.columns=["O","H","L","C","V"]; q["date"]=q.index.date; q["wd"]=q.index.weekday
# last bar of each Friday (next bar is a new week)
is_fri_last = (q["wd"]==4) & (q["date"]!=pd.Series(q["date"]).shift(-1).values)

def metrics(eq, trades, fin):
    eq=pd.Series(eq).sort_index(); r=eq.pct_change().dropna(); yrs=len(eq)/252
    t=pd.DataFrame(trades, columns=["exit","R","held_wknd","gap_pnl"])
    wins=t["R"]>0; gp=t.loc[wins,"R"].sum(); gl=-t.loc[~wins,"R"].sum()
    return dict(CAGR=(eq.iloc[-1]/eq.iloc[0])**(1/yrs)-1 if eq.iloc[0]>0 else 0,
        Sharpe=r.mean()/r.std()*np.sqrt(252) if r.std()>0 else 0,
        PF=gp/max(gl,1e-9), MaxDD=(eq/eq.cummax()-1).min(),
        Win=wins.mean() if len(t) else 0, AvgR=t["R"].mean() if len(t) else 0,
        N=len(t), wknd_held=int(t["held_wknd"].sum()),
        wknd_gap_pnl=t["gap_pnl"].sum(), fin=fin)

def run_bracket(sig, stop, rr, risk, force_fri):
    cap=1e4; inpos=False; entry=stopP=tgtP=sh=0.; edate=None; trades=[]; eq={}; fin=0.; held_w=False; gap=0.
    C=q["C"].values; O=q["O"].values; d=q["date"].values; s=sig.values.astype(bool)
    for i in range(1,len(q)):
        p=C[i]
        if inpos:
            # weekend gap accounting: prev bar Friday-last, this bar new week
            if is_fri_last.values[i-1] and d[i]!=d[i-1]:
                gap += sh*(O[i]-entry_ref[0]); held_w=True; entry_ref[0]=O[i]
            hit=None
            if p<=stopP: hit=stopP; R=-1.0
            elif p>=tgtP: hit=tgtP; R=rr
            if hit is None and force_fri and is_fri_last.values[i]:
                hit=p; R=(p-entry)/(entry*stop)*(-1 if False else 1); R=(p-entry)/ (entry-stopP)
            if hit is not None:
                days=max((d[i]-edate).days,0); fincost=sh*entry*FIN_BPS*days
                cap+= sh*(hit-entry)-sh*(entry+hit)*SLIP - fincost; fin+=fincost
                trades.append((d[i],R,held_w,gap)); inpos=False; held_w=False; gap=0.
        if not inpos and s[i-1]:
            inpos=True; entry=p; edate=d[i]; stopP=p*(1-stop); tgtP=p*(1+stop*rr)
            sh=(cap*risk)/(p*stop); entry_ref=[p]
        eq[d[i]]=cap
    return metrics(eq, trades, fin)

# ---- S5 signal ----
orb=q[q.index.hour==9]; q["OH"]=q["date"].map({x:h for x,h in zip(orb["date"],orb["H"])})
q["OV"]=q["date"].map({x:v for x,v in zip(orb["date"],orb["V"])})
s5=pd.Series((q.index.map(lambda x:10<=x.hour<=13)&(q["C"]>q["OH"])&q["OH"].notna()&(q["V"]>q["OV"]*0.6)).values, index=q.index)
day_first=~pd.Series(q["date"]).duplicated().values  # one-entry-day handled by inpos guard
# ---- S1 signal ----
q["SD"]=q.index.map(lambda i:(i+pd.Timedelta(days=1)).date() if i.hour>=18 else i.date())
ab=q[q.index.map(lambda i:i.hour>=18 or i.hour<2)]; q["AL"]=q["SD"].map(ab.groupby("SD")["L"].min())
q["InS"]=q.index.map(lambda x:(2<=x.hour<5) or (9<=x.hour<12))
dc=q[q.index.hour==16][["C"]].copy(); dc.index=dc.index.date; dc=dc[~dc.index.duplicated(keep="last")]
q["E50"]=q["date"].map(dc["C"].ewm(span=50).mean().to_dict())
s1=((q["L"]<q["AL"])&(q["C"]>q["AL"])&q["InS"]&(q["C"]>q["E50"])&q["AL"].notna())

print(f"{'strategy/mode':22}{'CAGR':>7}{'Shrp':>6}{'PF':>6}{'MaxDD':>7}{'Win':>6}{'AvgR':>7}{'N':>5}{'wHeld':>6}{'wGapPnl':>9}{'CFDfin':>8}")
for name, sig, stop, rr, risk in [("S5", s5, 0.010, 3.0, 0.0075), ("S1", s1, 0.015, 3.0, 0.0070)]:
    for mode, ff in [("A hold", False), ("B fri-close", True)]:
        m=run_bracket(sig, stop, rr, risk, ff)
        print(f"{name+' '+mode:22}{m['CAGR']:+6.1%}{m['Sharpe']:6.2f}{m['PF']:6.2f}{m['MaxDD']:7.1%}"
              f"{m['Win']:6.1%}{m['AvgR']:+7.3f}{m['N']:5d}{m['wknd_held']:6d}{m['wknd_gap_pnl']:+9.0f}{m['fin']:8.0f}")

# ---- S3 daily, 5-day time exit ----
dd=q.groupby("date").agg(O=("O","first"),C=("C","last"),H=("H","max"),V=("V","sum"))
dd.index=pd.to_datetime(dd.index); dd["wd"]=dd.index.weekday
ma=dd["V"].rolling(20).mean(); s3=(dd["V"]>1.3*ma)&(dd["C"]>dd["O"])
def run_s3(force_fri):
    cap=1e4; inpos=False; entry=sh=0.; held=0; edate=None; trades=[]; eq={}; fin=0.; hw=False; gap=0.; ec=0.
    C=dd["C"].values; O=dd["O"].values; wd=dd["wd"].values; idx=dd.index; s=s3.values
    for i in range(1,len(dd)):
        p=C[i]
        if inpos:
            if wd[i]<wd[i-1]: gap+=sh*(O[i]-ec); hw=True; ec=O[i]   # week rollover
            held+=1; pnl=(p-entry)/entry
            exit_=held>=5 or pnl<=-0.020 or (force_fri and wd[i]==4)
            if exit_:
                days=max((idx[i]-edate).days,0); fc=sh*entry*FIN_BPS*days
                cap+=sh*(p-entry)-sh*(entry+p)*SLIP-fc; fin+=fc
                trades.append((idx[i], pnl/0.020, hw, gap)); inpos=False; held=0; hw=False; gap=0.
        if not inpos and s[i-1]:
            inpos=True; entry=p; edate=idx[i]; sh=(cap*0.004)/(p*0.020); ec=p
        eq[idx[i]]=cap
    return metrics(eq, trades, fin)
for mode, ff in [("A hold", False), ("B fri-close", True)]:
    m=run_s3(ff)
    print(f"{'S3 '+mode:22}{m['CAGR']:+6.1%}{m['Sharpe']:6.2f}{m['PF']:6.2f}{m['MaxDD']:7.1%}"
          f"{m['Win']:6.1%}{m['AvgR']:+7.3f}{m['N']:5d}{m['wknd_held']:6d}{m['wknd_gap_pnl']:+9.0f}{m['fin']:8.0f}")
