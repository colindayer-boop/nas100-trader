"""
Gamma Exposure (GEX) Filter Backtest — OptionsDX QQQ Data
Tests whether GEX regime improves S1 Asian Sweep performance.

Data: OptionsDX QQQ EOD option chains (monthly CSVs)
Place all downloaded CSVs in: /Users/colindayer/nas100_backtest/optionsdx/

Columns used: QUOTE_DATE, UNDERLYING_LAST, EXPIRE_DATE, STRIKE,
              C_DELTA, C_GAMMA, C_IV, P_DELTA, P_GAMMA, P_IV,
              C_VOLUME, P_VOLUME, C_OI, P_OI
"""

import pandas as pd
import numpy as np
import glob
import os
import pytz
from datetime import date, timedelta
import yfinance as yf
from scipy.stats import norm

DATA_DIR  = "/Users/colindayer/nas100_backtest/optionsdx/"
QQQ_CSV   = "/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv"
eastern   = pytz.timezone("US/Eastern")

# ── STEP 1: LOAD OPTIONSDX CSVs ──
print("Loading OptionsDX QQQ option chain data...")
files = sorted(glob.glob(DATA_DIR + "*.csv") + glob.glob(DATA_DIR + "*.txt") +
               glob.glob(DATA_DIR + "**/*.csv") + glob.glob(DATA_DIR + "**/*.txt"))
if not files:
    print(f"❌ No CSV files found in {DATA_DIR}")
    print("   Download QQQ option chains from optionsdx.com and place CSVs there")
    exit()

print(f"Found {len(files)} files")
dfs = []
for f in files:
    try:
        df = pd.read_csv(f, low_memory=False)
        df.columns = [c.strip().strip("[]").upper() for c in df.columns]
        # Coerce numeric columns (skip date/time string columns)
        skip = {"QUOTE_READTIME", "QUOTE_DATE", "EXPIRE_DATE"}
        for col in df.columns:
            if col not in skip:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        dfs.append(df)
    except Exception as e:
        print(f"  Skip {os.path.basename(f)}: {e}")

raw = pd.concat(dfs, ignore_index=True)
print(f"Total rows: {len(raw):,}")
print(f"Columns: {raw.columns.tolist()[:15]}")

# ── STEP 2: PARSE DATES ──
date_col = next((c for c in raw.columns if 'DATE' in c and 'QUOTE' in c), None)
if not date_col:
    date_col = raw.columns[1]  # fallback
raw[date_col] = pd.to_datetime(raw[date_col])
raw = raw.rename(columns={date_col: "QUOTE_DATE"})

# Detect column names flexibly
def find_col(df, keywords):
    for k in keywords:
        matches = [c for c in df.columns if k in c]
        if matches: return matches[0]
    return None

strike_col  = find_col(raw, ["STRIKE"])
exp_col     = find_col(raw, ["EXPIRE", "EXPIR", "EXP_DATE"])
c_gamma_col = find_col(raw, ["C_GAMMA", "CALL_GAMMA"])
p_gamma_col = find_col(raw, ["P_GAMMA", "PUT_GAMMA"])
c_oi_col    = find_col(raw, ["C_OI", "CALL_OI", "C_OPEN_INT", "C_VOLUME"])
p_oi_col    = find_col(raw, ["P_OI", "PUT_OI", "P_OPEN_INT", "P_VOLUME"])
under_col   = find_col(raw, ["UNDERLYING_LAST", "UNDERLYING", "UNDER_LAST"])

print(f"\nDetected columns:")
print(f"  Strike: {strike_col}, Expiry: {exp_col}")
print(f"  Call gamma: {c_gamma_col}, Put gamma: {p_gamma_col}")
print(f"  Call OI: {c_oi_col}, Put OI: {p_oi_col}")
print(f"  Underlying: {under_col}")

# ── STEP 3: CALCULATE DAILY GEX ──
print("\nCalculating daily Gamma Exposure (GEX)...")

def calc_daily_gex(df, date):
    day = df[df["QUOTE_DATE"].dt.date == date].copy()
    if len(day) == 0:
        return None

    price = float(day[under_col].iloc[0]) if under_col else None
    if price is None: return None

    # GEX = gamma * OI * 100 * price
    # Calls: positive GEX (dealers long gamma)
    # Puts:  negative GEX (dealers short gamma = amplify moves)
    gex = 0.0
    if c_gamma_col and c_oi_col:
        call_gex = (day[c_gamma_col].fillna(0) *
                    day[c_oi_col].fillna(0) * 100 * price).sum()
        gex += call_gex
    if p_gamma_col and p_oi_col:
        put_gex = (day[p_gamma_col].fillna(0) *
                   day[p_oi_col].fillna(0) * 100 * price * -1).sum()
        gex += put_gex

    return {"date": date, "gex": gex, "price": price, "regime": "negative" if gex < 0 else "positive"}

all_dates = sorted(raw["QUOTE_DATE"].dt.date.unique())
print(f"Date range: {all_dates[0]} → {all_dates[-1]} ({len(all_dates)} days)")

gex_records = []
for d in all_dates:
    r = calc_daily_gex(raw, d)
    if r: gex_records.append(r)

gex_df = pd.DataFrame(gex_records).set_index("date")
print(f"GEX calculated for {len(gex_df)} days")
print(f"\nSample GEX:")
print(gex_df.tail(10)[["gex","regime"]].to_string())

# GEX stats
pos_days = (gex_df["gex"] > 0).sum()
neg_days = (gex_df["gex"] < 0).sum()
print(f"\nPositive GEX days: {pos_days} ({pos_days/len(gex_df):.0%})")
print(f"Negative GEX days: {neg_days} ({neg_days/len(gex_df):.0%})")

# ── STEP 4: LOAD QQQ HOURLY + BUILD S1 SIGNAL ──
print("\nLoading QQQ hourly data and building S1 signals...")

df = pd.read_csv(QQQ_CSV)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]
df.index = df.index.tz_convert(eastern)
data = df[["open","high","low","close","volume"]].copy()
data.columns = ["Open","High","Low","Close","Volume"]
data["Date"] = data.index.date

# Filter to GEX date range only
data = data[data["Date"] >= gex_df.index.min()]
data = data[data["Date"] <= gex_df.index.max()]
print(f"QQQ data filtered to: {data['Date'].min()} → {data['Date'].max()}")

# Regime filters
end = str(date.today())
vix = yf.download("^VIX", start=str(gex_df.index.min()), end=end, progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

spy = yf.download("SPY", start=str(gex_df.index.min()-timedelta(days=365)), end=end, progress=False)["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:,0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_bull = spy.ewm(span=50,adjust=False).mean() > spy.ewm(span=200,adjust=False).mean()

all_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(data["Date"].unique())])
def asof_map(series, ts_idx):
    m = series.reindex(series.index.union(ts_idx)).ffill()
    r = m.asof(ts_idx); r.index = [t.date() for t in r.index]
    return r

vix_map = asof_map(vix_ma21, all_ts)
spy_map = asof_map(spy_bull, all_ts)

def vmult(v):
    if pd.isna(v): return 1.0
    if v > 25: return 0.0
    if v >= 20: return 0.5
    return 1.0

data["VIXMult"] = data["Date"].map(vix_map.map(vmult)).fillna(1.0)
data["SPYBull"]  = data["Date"].map(spy_map).fillna(True).astype(bool)
data["NegGEX"]   = data["Date"].map(gex_df["gex"] < 0).fillna(True)

# S1 signal
def is_asian(idx): return idx.hour >= 18 or idx.hour < 2
def sess_date(idx): return (idx + pd.Timedelta(days=1)).date() if idx.hour >= 18 else idx.date()

data["Asian"]       = data.index.map(is_asian)
data["SessionDate"] = data.index.map(sess_date)
ab = data[data["Asian"]]
data["AsianHigh"] = data["SessionDate"].map(ab.groupby("SessionDate")["High"].max())
data["AsianLow"]  = data["SessionDate"].map(ab.groupby("SessionDate")["Low"].min())
data["InSession"]  = data.index.map(lambda x: (2<=x.hour<5) or (9<=x.hour<12))

tp = (data["High"]+data["Low"]+data["Close"])/3
vwap_vals=[]; ct=cv=0.0; pd_=None
for i in range(len(data)):
    d=data["Date"].iloc[i]
    if d!=pd_: ct=cv=0.0; pd_=d
    if data["Volume"].iloc[i]>0: ct+=tp.iloc[i]*data["Volume"].iloc[i]; cv+=data["Volume"].iloc[i]
    vwap_vals.append(ct/cv if cv>0 else float("nan"))
data["VWAP"]=vwap_vals

dc=data[data.index.hour==16][["Close"]].copy(); dc.index=dc.index.date
dc=dc[~dc.index.duplicated(keep="last")]
data["DailyEMA50"]=data["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())

pc=data["Close"].shift(1)
tr=pd.concat([data["High"]-data["Low"],(data["High"]-pc).abs(),(data["Low"]-pc).abs()],axis=1).max(axis=1)
atr=tr.rolling(14).mean()
data["HighVol"]=atr>1.5*atr.rolling(200).mean()

data["SweepLow"]=(data["Low"]<data["AsianLow"])&(data["Close"]>data["AsianLow"])
base=(data["SweepLow"]&data["InSession"]&
      (data["Close"]>data["VWAP"])&(data["Close"]>data["DailyEMA50"])&
      ~data["HighVol"]&data["AsianLow"].notna()&
      (data["VIXMult"]>0)&data["SPYBull"])

data["Sig_Base"] = base.astype(int)
data["Sig_GEX"]  = (base & data["NegGEX"]).astype(int)

# ── STEP 5: BACKTEST ──
def backtest(sig_col, label):
    capital=10_000; init=capital
    risk=0.007; sl=0.015; rr=3.0
    trades=[]; years=[]
    in_trade=False; entry=stop=target=shares=0.0
    day_start=capital; cur_day=None; locked=False

    for i in range(1, len(data)):
        d=data.index[i].date(); price=float(data["Close"].iloc[i])
        sig=int(data[sig_col].iloc[i-1]); vmul=float(data["VIXMult"].iloc[i-1])

        if d!=cur_day: cur_day=d; day_start=capital; locked=False
        if (capital-day_start)/max(day_start,1)<=-0.05 or (capital-init)/init<=-0.10:
            locked=True
        if locked: continue

        if in_trade:
            if price<=stop:
                trades.append(shares*(stop-entry)); years.append(data.index[i].year)
                capital+=trades[-1]; in_trade=False
            elif price>=target:
                trades.append(shares*(target-entry)); years.append(data.index[i].year)
                capital+=trades[-1]; in_trade=False
        elif sig==1 and vmul>0:
            in_trade=True; entry=price
            stop=price*(1-sl); target=price*(1+sl*rr)
            shares=(capital*risk*vmul)/(price*sl)

    t=pd.Series(trades)
    if len(t)==0:
        print(f"\n{label}: No trades"); return {}
    pf=t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else float("inf")
    ret=(capital-init)/init
    eq=pd.Series([init]+list(t.cumsum()+init))
    dd=((eq-eq.cummax())/eq.cummax()).min()

    print(f"\n{label}")
    print(f"  Return:   {ret:+.1%}")
    print(f"  Max DD:   {dd:.1%}")
    print(f"  Trades:   {len(t)} ({len(t)/max(1,(data['Date'].max()-data['Date'].min()).days/365):.0f}/yr)")
    print(f"  Win rate: {(t>0).mean():.0%}")
    print(f"  P-factor: {pf:.2f}")
    return {"ret":ret,"dd":dd,"trades":len(t),"wr":(t>0).mean(),"pf":pf}

print(f"\n{'='*55}")
print("BACKTEST RESULTS")
print(f"{'='*55}")
r1 = backtest("Sig_Base", "S1 BASELINE (no GEX filter)")
r2 = backtest("Sig_GEX",  "S1 + REAL GEX FILTER (negative gamma only)")

if r1 and r2:
    print(f"\n{'='*55}")
    print("VERDICT")
    print(f"{'='*55}")
    pf_d = r2['pf']-r1['pf']
    dd_d = r1['dd']-r2['dd']
    tr_d = (r1['trades']-r2['trades'])/r1['trades']
    print(f"  PF:      {r1['pf']:.2f} → {r2['pf']:.2f}  ({pf_d:+.2f})")
    print(f"  DD:      {r1['dd']:.1%} → {r2['dd']:.1%}  ({dd_d:+.1%})")
    print(f"  Trades filtered: {tr_d:.0%}")
    if pf_d > 0.15 and dd_d > 0.005:
        print("\n  ✅ GEX filter SIGNIFICANTLY HELPS — add to live system")
    elif pf_d > 0.05:
        print("\n  ⚠️  GEX filter marginally helps — optional to add")
    else:
        print("\n  ❌ GEX filter does not help — skip it, save your money")

# Save GEX history for live use
gex_df.to_csv("/Users/colindayer/nas100_backtest/gex_history.csv")
print(f"\nGEX history saved to gex_history.csv")
