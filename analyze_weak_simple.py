"""
Simple analysis of weak strategies without timezone issues
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

# S5 signals
q["S5L"] = (q["ORBwin"] & (q["Close"] > q["ORBHi"]) & q["SB"] & q["NG"] & q["ORBHi"].notna()).astype(int)
q["S5S"] = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & ~q["SB"] & q["ORBLo"].notna()).astype(int)

print("=== STRATEGY PERFORMANCE SUMMARY ===")
print(f"Period: {START} to {END} ({q['Date'].nunique()} trading days)")
print()

# S5 ORB Short detailed analysis
print("S5 ORB SHORT:")
short_signals = q[q["S5S"] == 1]
print(f"  Signals: {len(short_signals)} ({len(short_signals)/5:.1f}/year)")

if len(short_signals) > 0:
    # Simple daily return simulation for intraday strategy
    returns = []
    for idx in short_signals.index:
        # Enter at close of signal bar, exit at next day's close or stop/target
        entry_price = float(q.loc[idx, "Close"])
        stop_loss = entry_price * (1 + 0.01)  # 1% stop (from original code: STOP_S5 = 0.010)
        take_profit = entry_price * (1 - 0.01 * 3.0)  # 3:1 RR (RR_S5 = 3.0)
        
        # Find exit (simplified: next day close or stop/target intraday)
        # For simplicity, we'll use end-of-day price
        exit_idx = q.index.get_loc(idx) + 1
        if exit_idx < len(q):
            exit_price = float(q.iloc[exit_idx]["Close"])
            # Check if stop/hit intraday (approximation)
            high_since = q.iloc[idx:exit_idx+1]["High"].max()
            low_since = q.iloc[idx:exit_idx+1]["Low"].min()
            
            if low_since <= stop_loss:
                exit_price = stop_loss
            elif high_since >= take_profit:
                exit_price = take_profit
            
            ret = (exit_price - entry_price) / entry_price  # Short: profit when price down
            returns.append(ret)
    
    if returns:
        returns = np.array(returns)
        print(f"  Win rate: {(returns > 0).mean():.1%}")
        print(f"  Avg return/trade: {returns.mean():.2%}")
        print(f"  Median return/trade: {np.median(returns):.2%}")
        print(f"  Best trade: {returns.max():.2%}")
        print(f"  Worst trade: {returns.min():.2%}")
        print(f"  Profit factor: {returns[returns > 0].sum() / abs(returns[returns < 0].sum()):.2f}")
    else:
        print("  No completed trades")

# S3 Abnormal Volume detailed analysis
print("\nS3 ABNORMAL VOLUME:")
qd = q.groupby("Date").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
qd.index = pd.to_datetime(qd.index)
qd["ma20"] = qd["Volume"].rolling(20).mean()
qd["bull"] = qd.index.map(lambda d: is_bull(d.date()))
qd["ng"] = qd.index.map(lambda d: neg_gex(d.date()))
qd["S3_raw"] = ((qd["Volume"] > 1.5 * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int)
qd["S3"] = qd["S3_raw"].shift(1)  # Avoid lookahead

signals = qd[qd["S3"] == 1].dropna()
print(f"  Signals: {len(signals)} ({len(signals)/5:.1f}/year)")

if len(signals) > 0:
    returns = []
    for date in signals.index:
        try:
            entry_date = qd.index[qd.index.get_loc(date) + 1]
        except (KeyError, IndexError):
            continue
            
        entry_price = float(qd.loc[entry_date, "Open"])
        stop_loss = entry_price * (1 - 0.02)  # 2% stop (STOP_S3 = 0.02)
        take_profit = entry_price * (1 + 0.02 * 2.5)  # 2.5x RR (RR_S3 = 2.5)
        
        # Look ahead 5 days
        try:
            loc = qd.index.get_loc(entry_date)
            future_data = qd.iloc[loc+1:loc+6]
        except (KeyError, IndexError):
            future_data = qd.iloc[loc+1:]
        
        exit_price = None
        for exit_date, bar in future_data.iterrows():
            high = float(bar["High"])
            low = float(bar["Low"])
            close = float(bar["Close"])
            
            if low <= stop_loss:
                exit_price = stop_loss
                break
            if high >= take_profit:
                exit_price = take_profit
                break
        
        if exit_price is None and len(future_data) > 0:
            exit_price = float(future_data.iloc[-1]["Close"])
        elif exit_price is None:
            continue
            
        ret = (exit_price - entry_price) / entry_price
        returns.append(ret)
    
    if returns:
        returns = np.array(returns)
        print(f"  Win rate: {(returns > 0).mean():.1%}")
        print(f"  Avg return/trade: {returns.mean():.2%}")
        print(f"  Median return/trade: {np.median(returns):.2%}")
        print(f"  Best trade: {returns.max():.2%}")
        print(f"  Worst trade: {returns.min():.2%}")
        print(f"  Profit factor: {returns[returns > 0].sum() / abs(returns[returns < 0].sum()):.2f}")
    else:
        print("  No completed trades")

print("\n=== PARAMETER SENSITIVITY (CONSERVATIVE RANGES) ===")
print("S3 Volume Threshold (keep >1.0x to avoid noise):")
base_signals = ((qd["Volume"] > 1.0 * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int).shift(1)
base_count = (qd["S3_raw"] > 0).sum()
print(f"  >1.0x MA20: {base_count} signals")
for mult in [1.2, 1.5, 1.8, 2.0]:
    count = ((qd["Volume"] > mult * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int).shift(1).sum()
    print(f"  >{mult}x MA20: {count} signals ({count/5:.1f}/year)")

print("\nS5ORB Alternative Short Conditions (testing if SPY bias is wrong):")
# Test if being SHORT when SPY is BULLISH works better
spy_bull_short = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & q["SB"] & q["NG"] & q["ORBLo"].notna()).astype(int)
spy_bear_short = (q["ORBwin"] & (q["Close"] < q["ORBLo"]) & (~q["SB"]) & q["NG"] & q["ORBLo"].notna()).astype(int)
print(f"  Short when SPY BULLISH: {spy_bull_short.sum()} signals")
print(f"  Short when SPY BEARISH: {spy_bear_short.sum()} signals (original)")

# Test different time windows for S5 ORB
print("\nS5ORB Different Entry Windows:")
print(f"  Original (10am-1pm): {q['S5S'].sum()} signals")
# Test earlier entry (9:30am-12:30pm)
early_window = (q.index.hour >= 9) & (q.index.hour < 12) & (q.index.minute >= 30)
early_signals = (early_window & (q["Close"] < q["ORBLo"]) & (~q["SB"]) & q["NG"] & q["ORBLo"].notna()).astype(int)
print(f"  Early (9:30am-12:30pm): {early_signals.sum()} signals")
# Test later entry (11am-2pm)
late_window = (q.index.hour >= 11) & (q.index.hour < 14)
late_signals = (late_window & (q["Close"] < q["ORBLo"]) & (~q["SB"]) & q["NG"] & q["ORBLo"].notna()).astype(int)
print(f"  Late (11am-2pm): {late_signals.sum()} signals")

print("\nNOTE: These are exploratory tests only. Any parameter changes would require")
print("      out-of-sample validation to avoid overfitting.")
