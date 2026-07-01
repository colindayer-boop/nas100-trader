"""
alpaca_universe_sweep.py — Test the S1 Asian-sweep edge on a LARGE universe using
Alpaca's free extended-hours hourly bars (no Polygon needed). Validates which
tickers hold, then shows the combined large-universe portfolio.
"""
import pandas as pd, numpy as np, pytz, warnings
warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
import pytz as tz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from broker import load_config

eastern = pytz.timezone("US/Eastern")
SLIP, RR, STOP, RISK = 0.0004, 3.0, 0.015, 0.007
cfg = load_config("alpaca")
cl = StockHistoricalDataClient(cfg["key"].strip(), cfg["secret"].strip())

UNIV = ["SPY","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLY","XLI","XLP","XLU",
        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","NFLX","GLD","TLT","SMH","AVGO"]

def fetch(sym):
    req = StockBarsRequest(symbol_or_symbols=[sym], timeframe=TimeFrame.Hour,
                           start=datetime(2021, 1, 1, tzinfo=tz.utc))
    d = cl.get_stock_bars(req).df
    if isinstance(d.index, pd.MultiIndex): d = d.xs(sym, level="symbol")
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(eastern)
    d = d[["open","high","low","close","volume"]].copy()
    d.columns = ["Open","High","Low","Close","Volume"]; d["Date"] = d.index.date
    return d

def sig(q):
    def isa(i): return i.hour >= 18 or i.hour < 2
    def sd(i): return (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date()
    q = q.copy(); q["A"] = q.index.map(isa); q["SD"] = q.index.map(sd); ab = q[q["A"]]
    q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
    q["IN"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
    tp = (q["High"]+q["Low"]+q["Close"])/3; vw=[]; ct=cv=0.; pdd=None
    for i in range(len(q)):
        d = q["Date"].iloc[i]
        if d != pdd: ct=cv=0.; pdd=d
        if q["Volume"].iloc[i] > 0: ct += tp.iloc[i]*q["Volume"].iloc[i]; cv += q["Volume"].iloc[i]
        vw.append(ct/cv if cv > 0 else np.nan)
    q["VW"] = vw; dc = q[q.index.hour==16][["Close"]].copy(); dc.index=dc.index.date
    dc = dc[~dc.index.duplicated(keep="last")]
    q["EMA"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
    pc = q["Close"].shift(1); tr = pd.concat([q["High"]-q["Low"],(q["High"]-pc).abs(),(q["Low"]-pc).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean(); q["HV"] = atr > 1.5*atr.rolling(200).mean()
    return (((q["Low"]<q["AL"])&(q["Close"]>q["AL"]))&q["IN"]&(q["Close"]>q["VW"])&(q["Close"]>q["EMA"])&~q["HV"]&q["AL"].notna())

def bt(q, s):
    c,h,l = q["Close"].values,q["High"].values,q["Low"].values; sv=s.values; tr=[]; i=0; n=len(q)
    while i < n:
        if not sv[i]: i+=1; continue
        e=c[i]; st=e*(1-STOP); tg=e*(1+STOP*RR); j=i+1; o=None
        while j < n:
            if l[j]<=st: o=-1; break
            if h[j]>=tg: o=RR; break
            j+=1
        if o is None: break
        tr.append((pd.Timestamp(q.index[i].date()), o)); i=j+1
    return tr

allt=[]; keep=[]; print(f"Fetching {len(UNIV)} tickers from Alpaca (extended hours, 2021+)...")
for sym in UNIV:
    try:
        q = fetch(sym); tr = bt(q, sig(q))
        oos = [o for d,o in tr if d.year >= 2024]
        wr = np.mean([o>0 for o in oos]) if oos else 0
        ret = np.prod([1+RISK*o for o in oos])-1 if oos else 0
        good = len(oos) >= 10 and ret > 0
        if good: keep.append(sym); allt += tr
        print(f"  {sym:6} OOS n={len(oos):3d} win={wr:.0%} ret={ret:+.0%}  {'KEEP' if good else '-'}")
    except Exception as e:
        print(f"  {sym:6} err {type(e).__name__}")

allt = sorted(allt)
pnl = pd.Series([RISK*o for _,o in allt], index=pd.to_datetime([d for d,_ in allt])).groupby(level=0).sum()
full = (1+pnl.reindex(pd.date_range(pnl.index.min(),pnl.index.max(),freq="D")).fillna(0)).cumprod()
mo = full.resample("ME").last().pct_change().dropna(); yrs = len(full)/365.25
print(f"\n=== LARGE-UNIVERSE SWEEP ({len(keep)} validated tickers) ===")
print(f"Trades: {len(allt)} (~{len(allt)/yrs:.0f}/yr) | CAGR {full.iloc[-1]**(1/yrs)-1:+.1%} | "
      f"Sharpe {mo.mean()/mo.std()*np.sqrt(12):.2f} | maxDD {(full/full.cummax()-1).min():.1%} | win-mo {(mo>0).mean():.0%}")
print(f"Validated tickers: {keep}")
