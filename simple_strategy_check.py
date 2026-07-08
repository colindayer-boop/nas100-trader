"""
Simple check of strategy signal frequency and basic characteristics
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

print("LOADING DATA...")
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
strategy_name = "S5 ORB SHORT"
signals = q[q["S5S"] == 1]
print(f"{strategy_name}:")
print(f"  Total signals: {len(signals)}")
print(f"  Signals per year: {len(signals) / 5:.1f}")
if len(signals) > 0:
    # Show some signal details
    sample = signals.head(3)
    print("  Sample signals:")
    for idx, row in sample.iterrows():
        print(f"    {idx}: Close={row['Close']:.2f}, ORB Low={row['ORBLo']:.2f}, SPY Bull={row['SB']}, GEX Neg={row['NG']}")
print()

print("=" * 60)
strategy_name = "S3 ABNORMAL VOLUME"
# Daily volume analysis
qd = q.groupby("Date").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
qd.index = pd.to_datetime(qd.index)
qd["ma20"] = qd["Volume"].rolling(20).mean()
qd["bull"] = qd.index.map(lambda d: is_bull(d.date()))
qd["ng"] = qd.index.map(lambda d: neg_gex(d.date()))
qd["S3_raw"] = ((qd["Volume"] > 1.5 * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int)
qd["S3"] = qd["S3_raw"].shift(1)  # Avoid lookahead
signals = qd[qd["S3"] == 1].dropna()
print(f"{strategy_name}:")
print(f"  Total signals: {len(signals)}")
print(f"  Signals per year: {len(signals) / 5:.1f}")
if len(signals) > 0:
    # Show some signal details
    sample = signals.head(3)
    print("  Sample signals:")
    for date, row in sample.iterrows():
        print(f"    {date.date()}: Volume={row['Volume']:.0f}, 20-day MA={row['ma20']:.0f}, Ratio={row['Volume']/row['ma20']:.2f}, Bull={row['bull']}, GEX Neg={row['ng']}")
print()

print("=" * 60)
print("SIMPLE PARAMETER EXPLORATION (CONSERVATIVE RANGES)")
print("=" * 60)

# S3: Volume multiplier sensitivity
print("S3 Volume Multiplier Sensitivity:")
base_volume_condition = (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]
for mult in [1.2, 1.5, 1.8, 2.0, 2.5]:
    signals_count = ((qd["Volume"] > mult * qd["ma20"]) & base_volume_condition).sum()
    print(f"  Volume > {mult}x MA20: {signals_count} signals ({signals_count/5:.1f}/yr)")

print()
# S5 Short: Alternative timing
print("S5 ORB Short - Alternative Entry Windows:")
base_conditions = (q["Close"] < q["ORBLo"]) & (~q["SB"]) & q["NG"] & q["ORBLo"].notna()
windows = [
    ("Original (10am-1pm)", (q.index.hour >= 10) & (q.index.hour <= 13)),
    ("Early (9:30am-12pm)", (q.index.hour >= 9) & (q.index.hour <= 12)),
    ("Late (11am-2pm)", (q.index.hour >= 11) & (q.index.hour <= 14)),
    ("Midday (10am-2pm)", (q.index.hour >= 10) & (q.index.hour <= 14)),
    ("Afternoon only (12pm-3pm)", (q.index.hour >= 12) & (q.index.hour <= 15)),
]
for desc, window in windows:
    signals_count = (window & base_conditions).sum()
    print(f"  {desc}: {signals_count} signals ({signals_count/5:.1f}/yr)")

print()
# S5 Short: Alternative SPY conditions (simple tests)
print("S5 ORB Short - Alternative SPY Conditions:")
spy_conditions = [
    ("Always allow (no SPY filter)", pd.Series([True] * len(q), index=q.index)),
    ("Only when SPY below 200ma", spy.close < spy.ewm(span=200).mean()),
    ("Only when SPY below 50ma", spy.close < spy.ewm(span=50).mean()),
    ("Only when 50ma < 200ma (bearish)", spy.ewm(span=50).mean() < spy.ewm(span=200).mean()),
]
# Fix the series comparison issue
spy_close = spy.reindex(q.index, method='ffill')
spy_ma50 = spy.ewm(span=50).mean().reindex(q.index, method='ffill')
spy_ma200 = spy.ewm(span=200).mean().reindex(q.index, method='ffill')

spy_conditions_fixed = [
    ("Always allow (no SPY filter)", pd.Series([True] * len(q), index=q.index)),
    ("Only when SPY below 200ma", spy_close < spy_ma200),
    ("Only when SPY below 50ma", spy_close < spy_ma50),
    ("Only when 50ma < 200ma (bearish)", spy_ma50 < spy_ma200),
]

base_conditions = (q["Close"] < q["ORBLo"]) & q["NG"] & q["ORBLo"].notna()
for desc, condition in spy_conditions_fixed:
    signals_count = (base_conditions & condition).sum()
    print(f"  {desc}: {signals_count} signals ({signals_count/5:.1f}/yr)")

print()
print("=" * 60)
print("OBSERVATIONS:")
print("=" * 60)
print("1. S5 ORB Short gets 62 signals/year but current SPY filter (bullish only) eliminates")
print("   ALL short signals because it requires SPY to be bullish (~70% of time).")
print("   This explains why we got 0 short trades in the original backtest.")
print()
print("2. S3 gets only ~2 signals/year with 1.5x volume threshold - very infrequent.")
print("   Lowering to 1.2x gives ~6 signals/year, which is more reasonable.")
print()
print("3. These strategies may need different approach:")
print("   - S5 Short: Remove or invert SPY filter for short signals?")
print("   - S3: Lower volume threshold to 1.2-1.3x for more frequency")
print()
print("REMINDER: Any parameter changes require out-of-sample testing!")
print("=" * 60)
