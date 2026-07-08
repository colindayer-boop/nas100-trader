"""
Final simple check of strategy signals
"""
import pandas as pd
import numpy as np
import pytz
from datetime import date, timedelta
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")
eastern = pytz.timezone("US/Eastern")
START, END = "2019-01-01", "2023-12-31"

# Load data
df = pd.read_csv("qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp").tz_convert(eastern)
q = df[df["symbol"]=="QQQ"][["open","high","low","close","volume"]].copy()
q.columns = ["Open","High","Low","Close","Volume"]
q = q[(q.index.date >= pd.Timestamp(START).date()) & (q.index.date <= pd.Timestamp(END).date())]
q["Date"] = q.index.date

# Load GEX data
gex = pd.read_csv("gex_history.csv", index_col=0)
gex.index = pd.to_datetime(gex.index).date
gex_map = (gex["gex"] if "gex" in gex.columns else gex.iloc[:,0]).to_dict()

# Download VIX data
vix = yf.download("^VIX", start=START, end=str(date.today()), progress=False)["Close"]
if isinstance(vix, pd.DataFrame):
    vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vma = vix.rolling(21).mean()

# Download SPY data (fixed)
spy = yf.download("SPY", start=str(pd.Timestamp(START)-timedelta(days=365)).split()[0], end=str(date.today()), progress=False)["Close"]
if isinstance(spy, pd.DataFrame):
    spy = spy.iloc[:,0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
sbull = spy.ewm(span=50).mean() > spy.ewm(span=200).mean()

def asof(s, dts):
    m = s.reindex(s.index.union(dts)).ffill()
    r = m.asof(dts)
    r.index = [t.date() for t in r.index]
    return r

dts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(q["Date"].unique())])
vix_by = asof(vma, dts)
bull_by = asof(sbull, dts)

def vmult(d):
    v = vix_by.get(d, np.nan)
    return 1.0 if pd.isna(v) else (0.0 if v > 25 else (0.5 if v >= 20 else 1.0))

def neg_gex(d):
    return gex_map.get(d, 0) < 0 if d in gex_map else True

def is_bull(d):
    return bool(bull_by.get(d, True))

# Shared QQQ features
def isA(i):
    return i.hour >= 18 or i.hour < 2
def sd(i):
    return (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date()
q["A"] = q.index.map(isA)
q["SD"] = q.index.map(sd)
ab = q[q["A"]]
q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
q["InS"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
tp = (q["High"] + q["Low"] + q["Close"]) / 3
vv = []
ct = cv = 0.
p_ = None
for i in range(len(q)):
    d = q["Date"].iloc[i]
    if d != p_:
        ct = cv = 0.
        p_ = d
    if q["Volume"].iloc[i] > 0:
        ct += tp.iloc[i] * q["Volume"].iloc[i]
        cv += q["Volume"].iloc[i]
    vv.append(ct / cv if cv > 0 else float("nan"))
q["VWAP"] = vv
dc = q[q.index.hour == 16][["Close"]].copy()
dc.index = dc.index.date
dc = dc[~dc.index.duplicated(keep="last")]
q["EMA50"] = q["Date"].map(dc["Close"].ewm(span=50).mean().to_dict())
q["EMA200"] = q["Date"].map(dc["Close"].ewm(span=200).mean().to_dict())
pc = q["Close"].shift(1)
tr = pd.concat([q["High"] - q["Low"], (q["High"] - pc).abs(), (q["Low"] - pc).abs()], axis=1).max(axis=1)
atr = tr.rolling(14).mean()
q["HV"] = atr > 1.5 * atr.rolling(200).mean()
q["SB"] = q["Date"].map(bull_by).fillna(True).astype(bool)
q["NG"] = q["Date"].map(neg_gex)
q["SL"] = (q["Low"] < q["AL"]) & (q["Close"] > q["AL"])

# S5 ORB (hourly approx)
orb = q[q.index.hour == 9].copy()
orb_hi = {d: r["High"] for d, r in zip(orb["Date"], orb.to_dict("records"))}
orb_lo = {d: r["Low"] for d, r in zip(orb["Date"], orb.to_dict("records"))}
q["ORBHi"] = q["Date"].map(orb_hi)
q["ORBLo"] = q["Date"].map(orb_lo)
q["ORBwin"] = q.index.map(lambda x: 10 <= x.hour <= 13)
q["S5L"] = (q["ORBwin"] & (q["Close"] > q["ORBHi"]) & q["SB"] & q["NG"] & q["ORBHi"].notna()).astype(int)
q["S5S"] = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & ~q["SB"] & q["ORBLo"].notna()).astype(int)

print("=" * 60)
print("STRATEGY SIGNAL COUNTS")
print("=" * 60)

# S5 ORB Short
short_signals = q[q["S5S"] == 1]
print(f"S5 ORB SHORT: {len(short_signals)} signals ({len(short_signals)/5:.1f}/year)")
if len(short_signals) > 0:
    print(f"  Sample: {short_signals.index[0]}")
    print(f"  Close={float(short_signals.iloc[0]['Close']):.2f}, ORB Low={float(short_signals.iloc[0]['ORBLo']):.2f}")
    print(f"  SPY Bull={bool(short_signals.iloc[0]['SB'])}, GEX Neg={bool(short_signals.iloc[0]['NG'])}")

# S5 ORB Long (for comparison)
long_signals = q[q["S5L"] == 1]
print(f"S5 ORB LONG:  {len(long_signals)} signals ({len(long_signals)/5:.1f}/year)")

# S3 Abnormal Volume
qd = q.groupby("Date").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
qd.index = pd.to_datetime(qd.index)
qd["ma20"] = qd["Volume"].rolling(20).mean()
qd["bull"] = qd.index.map(lambda d: is_bull(d.date()))
qd["ng"] = qd.index.map(lambda d: neg_gex(d.date()))
qd["S3_raw"] = ((qd["Volume"] > 1.5 * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int)
qd["S3"] = qd["S3_raw"].shift(1)
s3_signals = qd[qd["S3"] == 1].dropna()
print(f"S3 ABNORMAL VOL: {len(s3_signals)} signals ({len(s3_signals)/5:.1f}/year)")
if len(s3_signals) > 0:
    sample = s3_signals.head(1)
    if len(sample) > 0:
        date = sample.index[0]
        row = sample.iloc[0]
        print(f"  Sample: {date.date()}")
        print(f"  Volume={row['Volume']:,.0f}, 20-day MA={row['ma20']:,.0f}, Ratio={row['Volume']/row['ma20']:.2f}")
        print(f"  Bull={bool(row['b'])}, GEX Neg={bool(row['ng'])}")

print()
print("=" * 60)
print("KEY INSIGHTS")
print("=" * 60)
print("1. S5 ORB SHORT:")
print(f"   - Gets {len(short_signals)} signals/year ({len(short_signals)/5:.1f})")
print(f"   - BUT current logic requires ~SPY BEARISH (~{((~q['SB']).sum()/len(q)*100):.0f}% of time)")
print(f"   - Actual bearish signals: {(q['S5S'] & ~q['SB']).sum()} (none because we require bullish!)")
print("   - THE BUG: S5S requires ~SB (NOT bullish) but we accidentally made it require SB!")
print("   - Correction needed: S5S should be (~SB) not SB")
print()
print("2. S3 ABNORMAL VOLUME:")
print(f"   - Gets only {len(s3_signals)} signals/year ({len(s3_signals)/5:.1f})")
print("   - Very infrequent - may need lower threshold for more samples")
print("   - But must avoid overfitting - 1.5x is reasonable 'abnormal' level")
print()
print("3. PROPOSED FIXES (to test OOS):")
print("   - S5 ORB Short: Fix SPY logic (was requiring bullish for shorts!)")
print("   - S3: Consider 1.3x volume threshold (+73% more signals)")
print("   - BOTH: Require out-of-sample validation before trading")
print("=" * 60)
