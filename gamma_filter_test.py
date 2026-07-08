"""
Gamma Exposure (GEX) Filter Test
Tests whether adding a GEX regime filter improves S1 Asian Sweep performance.

Logic:
- Positive GEX = market makers suppress volatility = bad for sweeps
- Negative GEX = market makers amplify moves = good for sweeps
- Gamma flip level = key support/resistance market makers defend

We proxy historical GEX using VIX term structure and put/call ratio
(real GEX data requires paid options history, but we can approximate
using free CBOE put/call ratio as a GEX proxy)
"""

import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime, timedelta, date
from scipy.stats import norm

eastern = pytz.timezone("US/Eastern")

print("Testing GEX filter on S1 Asian Sweep...")
print("Downloading data...\n")

# ── LOAD QQQ HOURLY ──
df = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]
df.index = df.index.tz_convert(eastern)
data = df[["open","high","low","close","volume"]].copy()
data.columns = ["Open","High","Low","Close","Volume"]
data["Date"] = data.index.date

# ── REGIME FILTERS ──
end = str(date.today())
vix = yf.download("^VIX", start="2019-01-01", end=end, progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

spy = yf.download("SPY", start="2019-01-01", end=end, progress=False)["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:,0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_bull = spy.ewm(span=50,adjust=False).mean() > spy.ewm(span=200,adjust=False).mean()

# ── GEX PROXY: CBOE Put/Call Ratio ──
# High P/C ratio = dealers short puts = negative GEX = trending market
# Low P/C ratio  = dealers short calls = positive GEX = pinned market
# Free from CBOE via yfinance
try:
    pc = yf.download("^PCALL", start="2019-01-01", end=end, progress=False)["Close"]
    if isinstance(pc, pd.DataFrame): pc = pc.iloc[:,0]
    pc.index = pd.to_datetime(pc.index).tz_localize(None).normalize()
    pc_ma5 = pc.rolling(5).mean()
    # High P/C (>1.0) = negative GEX proxy = good for sweeps
    gex_positive = pc_ma5 < 0.8   # low P/C = dealers suppressing moves
    print(f"Put/Call ratio data: {len(pc)} days")
    pc_available = True
except:
    pc_available = False
    print("Put/Call ratio not available — using VIX term structure instead")

# ── VIX TERM STRUCTURE as GEX proxy ──
# VIX9D < VIX = contango = positive GEX (calm, pinned)
# VIX9D > VIX = backwardation = negative GEX (trending, amplified)
try:
    vix9 = yf.download("^VIX9D", start="2019-01-01", end=end, progress=False)["Close"]
    if isinstance(vix9, pd.DataFrame): vix9 = vix9.iloc[:,0]
    vix9.index = pd.to_datetime(vix9.index).tz_localize(None).normalize()
    ts_negative = vix9 > vix  # backwardation = negative GEX regime
    print(f"VIX9D data: {len(vix9)} days")
    ts_available = True
except:
    ts_available = False
    print("VIX9D not available")

# ── MAP TO HOURLY DATA ──
all_dates_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(data["Date"].unique())])

def map_daily(series, dates):
    mapped = series.reindex(series.index.union(dates)).ffill()
    by_date = mapped.asof(dates)
    by_date.index = [ts.date() for ts in by_date.index]
    return by_date

vix_by_date = map_daily(vix_ma21, all_dates_ts)
spy_by_date = map_daily(spy_bull, all_dates_ts)
if ts_available:
    ts_by_date = map_daily(ts_negative, all_dates_ts)

def vix_mult(v):
    if pd.isna(v): return 1.0
    if v > 25: return 0.0
    if v >= 20: return 0.5
    return 1.0

data["VIXMult"] = data["Date"].map(vix_by_date.map(vix_mult)).fillna(1.0)
data["SPYBull"]  = data["Date"].map(spy_by_date).fillna(True).astype(bool)
if ts_available:
    data["NegGEX"] = data["Date"].map(ts_by_date).fillna(True).astype(bool)
else:
    data["NegGEX"] = True

# ── S1 SIGNAL LOGIC ──
def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
def sess_date(idx): return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()

data["Asian"]       = data.index.map(is_asian)
data["SessionDate"] = data.index.map(sess_date)
ab = data[data["Asian"]]
data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())
data["InSession"]  = data.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))

tp = (data["High"] + data["Low"] + data["Close"]) / 3
vwap_vals = []; cum_tp = cum_v = 0.0; prev_d = None
for i in range(len(data)):
    d = data["Date"].iloc[i]
    if d != prev_d: cum_tp = cum_v = 0.0; prev_d = d
    if data["Volume"].iloc[i] > 0:
        cum_tp += tp.iloc[i] * data["Volume"].iloc[i]
        cum_v  += data["Volume"].iloc[i]
    vwap_vals.append(cum_tp / cum_v if cum_v > 0 else float("nan"))
data["VWAP"] = vwap_vals

daily_close = data[data.index.hour == 16][["Close"]].copy()
daily_close.index = daily_close.index.date
daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
data["DailyEMA50"] = data["Date"].map(daily_close["Close"].ewm(span=50).mean().to_dict())

pc = data["Close"].shift(1)
tr = pd.concat([data["High"]-data["Low"],(data["High"]-pc).abs(),(data["Low"]-pc).abs()],axis=1).max(axis=1)
atr = tr.rolling(14).mean()
data["HighVol"] = atr > 1.5 * atr.rolling(200).mean()

data["SweepLow"] = (data["Low"] < data["AsianLow"]) & (data["Close"] > data["AsianLow"])
base = (data["SweepLow"] & data["InSession"] &
        (data["Close"] > data["VWAP"]) &
        (data["Close"] > data["DailyEMA50"]) &
        ~data["HighVol"] & data["AsianLow"].notna() &
        (data["VIXMult"] > 0) & data["SPYBull"])

data["Sig_Base"] = base.astype(int)
data["Sig_GEX"]  = (base & data["NegGEX"]).astype(int)

# ── BACKTEST ──
def backtest(sig_col, label):
    capital = 10_000; init = capital
    risk = 0.007; sl = 0.015; rr = 3.0
    trades = []; years = []
    in_trade = False; entry = stop = target = shares = 0.0
    day_start = capital; cur_day = None; locked = False

    for i in range(1, len(data)):
        d = data.index[i].date()
        price = float(data["Close"].iloc[i])
        sig   = int(data[sig_col].iloc[i-1])
        vmul  = float(data["VIXMult"].iloc[i-1])

        if d != cur_day:
            cur_day = d; day_start = capital; locked = False
        if (capital-day_start)/max(day_start,1) <= -0.05 or \
           (capital-init)/init <= -0.10:
            locked = True
        if locked: continue

        if in_trade:
            if price <= stop:
                pnl = shares*(stop-entry); capital+=pnl; trades.append(pnl); years.append(data.index[i].year); in_trade=False
            elif price >= target:
                pnl = shares*(target-entry); capital+=pnl; trades.append(pnl); years.append(data.index[i].year); in_trade=False
        elif sig==1 and vmul>0:
            in_trade=True; entry=price
            stop=price*(1-sl); target=price*(1+sl*rr)
            shares=(capital*risk*vmul)/(price*sl)

    t = pd.Series(trades)
    pf = t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else float("inf")
    ret = (capital-init)/init
    eq  = pd.Series([init]+list(t.cumsum()+init))
    dd  = ((eq-eq.cummax())/eq.cummax()).min()
    print(f"\n{label}")
    print(f"  Return:  {ret:+.1%}")
    print(f"  Max DD:  {dd:.1%}")
    print(f"  Trades:  {len(t)} ({len(t)/7:.0f}/yr)")
    print(f"  Win rate:{(t>0).mean():.0%}")
    print(f"  P-factor:{pf:.2f}")
    return {"ret": ret, "dd": dd, "trades": len(t), "wr": (t>0).mean(), "pf": pf}

r1 = backtest("Sig_Base", "S1 BASELINE (no GEX filter)")
r2 = backtest("Sig_GEX",  "S1 + GEX FILTER (VIX term structure proxy)")

print(f"\n{'='*50}")
print("VERDICT:")
pf_improve = r2['pf'] - r1['pf']
dd_improve = r1['dd'] - r2['dd']
trade_reduce = (r1['trades'] - r2['trades']) / r1['trades']
print(f"  PF change:     {r1['pf']:.2f} → {r2['pf']:.2f} ({pf_improve:+.2f})")
print(f"  DD change:     {r1['dd']:.1%} → {r2['dd']:.1%} ({dd_improve:+.1%} improvement)")
print(f"  Trades filtered: {trade_reduce:.0%} of signals removed")
if pf_improve > 0.1 and dd_improve > 0.005:
    print("  ✅ GEX filter HELPS — worth adding")
elif pf_improve > 0 and trade_reduce < 0.3:
    print("  ⚠️  Marginal improvement — borderline")
else:
    print("  ❌ GEX filter does NOT help significantly — skip it")
