"""
Analyze the weak strategies (S5 ORB Short and S3 Abnormal Volume) 
to understand their trade frequency, win rates, and potential improvements.
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

# Load data (same as full_yearly.py)
df = pd.read_csv("qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp").tz_convert(eastern)
q = df[df["symbol"]=="QQQ"][["open","high","low","close","volume"]].copy()
q.columns = ["Open","High","Low","Close","Volume"]
q = q[(q.index.date >= pd.Timestamp(START).date()) & (q.index.date <= pd.Timestamp(END).date())]
q["Date"] = q.index.date

gex = pd.read_csv("gex_history.csv", index_col=0)
gex.index = pd.to_datetime(gex.index).date
gex_map = (gex["gex"] if "gex" in gex.columns else gex.iloc[:,0]).to_dict()

vix = yf.download("^VIX", start=START, end=str(date.today()), progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vma = vix.rolling(21).mean()

# FIXED: Use date-only strings for SPY download
spy = yf.download("SPY", start=str(pd.Timestamp(START)-timedelta(days=365)).split()[0], end=str(date.today()), progress=False)["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:,0]
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

def neg_gex(d): return gex_map.get(d, 0) < 0 if d in gex_map else True
def is_bull(d): return bool(bull_by.get(d, True))

# Shared QQQ features
def isA(i): return i.hour >= 18 or i.hour < 2
def sd(i): return (i + pd.Timedelta(days=1)).date() if i.hour >= 18 else i.date()
q["A"] = q.index.map(isA)
q["SD"] = q.index.map(sd)
ab = q[q["A"]]
q["AL"] = q["SD"].map(ab.groupby("SD")["Low"].min())
q["InS"] = q.index.map(lambda x: (2 <= x.hour < 5) or (9 <= x.hour < 12))
tp = (q["High"] + q["Low"] + q["Close"]) / 3
vv = []; ct = cv = 0.; p_ = None
for i in range(len(q)):
    d = q["Date"].iloc[i]
    if d != p_: ct = cv = 0.; p_ = d
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

# === S5 ORB SHORT ANALYSIS ===
print("=" * 60)
print("S5 ORB SHORT STRATEGY ANALYSIS")
print("=" * 60)

# Daily analysis for S5S
short_signals = q[q["S5S"] == 1]
print(f"Total short signals: {len(short_signals)}")
if len(short_signals) > 0:
    print(f"Average per year: {len(short_signals) / 5:.1f}")
    
    # Entry and exit logic simulation (using same parameters as backtest)
    trades = []
    for date in short_signals["Date"].unique():
        day_data = q[q["Date"] == date].sort_index()
        signal_bars = day_data[day_data["S5S"] == 1]
        if len(signal_bars) == 0:
            continue
            
        # Take first signal of the day (as in backtest)
        signal_bar = signal_bars.iloc[0]
        entry_price = float(signal_bar["Close"])
        entry_time = signal_bar.name
        
        # Parameters from backtest: risk=0.003, stop=0.010, rr=2.5
        risk_per_share = 0.003
        stop_loss_pct = 0.010
        rr = 2.5
        stop_loss = entry_price * (1 + stop_loss_pct)  # Short: stop above entry
        take_profit = entry_price * (1 - stop_loss_pct * rr)  # Short: target below entry
        
        # Look for exit in ORB window (10am-1pm) or end of day
        exit_price = None
        exit_reason = ""
        bars_after_signal = day_data[day_data.index > entry_time]
        
        for _, bar in bars_after_signal.iterrows():
            high = float(bar["High"])
            low = float(bar["Low"])
            
            # Check stop loss (price goes above stop)
            if high >= stop_loss:
                exit_price = stop_loss
                exit_reason = "stop_loss"
                break
            # Check take profit (price goes below target)
            if low <= take_profit:
                exit_price = take_profit
                exit_reason = "take_profit"
                break
            # End of ORB window or day - close at close
            if bar.name.hour >= 13:  # After 1pm ET
                exit_price = float(bar["Close"])
                exit_reason = "eod_close"
                break
        
        # If no exit signal, close at end of day
        if exit_price is None:
            last_bar = day_data.iloc[-1]
            exit_price = float(last_bar["Close"])
            exit_reason = "eod_close"
        
        # Calculate return (short: profit when price goes down)
        pct_return = (entry_price - exit_price) / entry_price
        trades.append({
            "date": date,
            "entry": entry_price,
            "exit": exit_price,
            "return": pct_return,
            "reason": exit_reason,
            "hours_in_trade": (bars_after_signal.iloc[0].name - entry_time).total_seconds() / 3600 if len(bars_after_signal) > 0 else 0
        })
    
    trades_df = pd.DataFrame(trades)
    if len(trades_df) > 0:
        print(f"Completed trades: {len(trades_df)}")
        print(f"Win rate: {(trades_df['return'] > 0).mean():.1%}")
        print(f"Average return per trade: {trades_df['return'].mean():.2%}")
        print(f"Median return per trade: {trades_df['return'].median():.2%}")
        print(f"Best trade: {trades_df['return'].max():.2%}")
        print(f"Worst trade: {trades_df['return'].min():.2%}")
        print(f"Profit factor: {trades_df[trades_df['return'] > 0]['return'].sum() / abs(trades_df[trades_df['return'] < 0]['return'].sum()):.2f}")
        print("\nExit reasons:")
        print(trades_df["reason"].value_counts())
else:
    print("No short signals found!")

# === S3 ABNORMAL VOLUME ANALYSIS ===
print("\n" + "=" * 60)
print("S3 ABNORMAL VOLUME STRATEGY ANALYSIS")
print("=" * 60)

# Daily volume analysis
qd = q.groupby("Date").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
qd.index = pd.to_datetime(qd.index)
qd["ma20"] = qd["Volume"].rolling(20).mean()
qd["bull"] = qd.index.map(lambda d: is_bull(d.date()))
qd["ng"] = qd.index.map(lambda d: neg_gex(d.date()))
qd["S3_raw"] = ((qd["Volume"] > 1.5 * qd["ma20"]) & (qd["Close"] > qd["Open"]) & qd["bull"] & qd["ng"]).astype(int)

# Shift signal to avoid lookahead (signal known at close, trade next day)
qd["S3"] = qd["S3_raw"].shift(1)
signals = qd[qd["S3"] == 1].dropna()
print(f"Total signals: {len(signals)}")
print(f"Average per year: {len(signals) / 5:.1f}")

if len(signals) > 0:
    # Simulate trades (5-day max hold, 2% stop, 2.5x RR)
    trades = []
    for date in signals.index:
        # Get entry price (next day open)
        try:
            entry_date = qd.index[qd.index.get_loc(date) + 1]
        except (KeyError, IndexError):
            continue  # No next day
            
        entry_price = float(qd.loc[entry_date, "Open"])
        stop_loss = entry_price * (1 - 0.02)  # 2% stop
        take_profit = entry_price * (1 + 0.02 * 2.5)  # 2.5x RR
        
        # Look for exit over next 5 days
        exit_price = None
        exit_reason = ""
        days_held = 0
        
        # Get next 5 days of data
        try:
            loc = qd.index.get_loc(entry_date)
            future_data = qd.iloc[loc+1:loc+6]  # Next 5 days
        except (KeyError, IndexError):
            future_data = qd.iloc[loc+1:]  # Whatever is left
        
        for exit_date, bar in future_data.iterrows():
            days_held += 1
            high = float(bar["High"])
            low = float(bar["Low"])
            close = float(bar["Close"])
            
            # Check stop loss
            if low <= stop_loss:
                exit_price = stop_loss
                exit_reason = "stop_loss"
                break
            # Check take profit
            if high >= take_profit:
                exit_price = take_profit
                exit_reason = "take_profit"
                break
            # Max hold period
            if days_held >= 5:
                exit_price = close
                exit_reason = "max_hold"
                break
        
        # If no exit signal, close at last available price
        if exit_price is None and len(future_data) > 0:
            exit_price = float(future_data.iloc[-1]["Close"])
            exit_reason = "end_of_data"
        elif exit_price is None:
            # No future data available
            continue
        
        # Calculate return
        pct_return = (exit_price - entry_price) / entry_price
        trades.append({
            "signal_date": date,
            "entry_date": entry_date,
            "entry": entry_price,
            "exit": exit_price,
            "return": pct_return,
            "reason": exit_reason,
            "days_held": days_held
        })
    
    trades_df = pd.DataFrame(trades)
    if len(trades_df) > 0:
        print(f"Completed trades: {len(trades_df)}")
        print(f"Win rate: {(trades_df['return'] > 0).mean():.1%}")
        print(f"Average return per trade: {trades_df['return'].mean():.2%}")
        print(f"Median return per trade: {trades_df['return'].median():.2%}")
        print(f"Best trade: {trades_df['return'].max():.2%}")
        print(f"Worst trade: {trades_df['return'].min():.2%}")
        print(f"Profit factor: {trades_df[trades_df['return'] > 0]['return'].sum() / abs(trades_df[trades_df['return'] < 0]['return'].sum()):.2f}")
        print(f"Average days held: {trades_df['days_held'].mean():.1f}")
        print("\nExit reasons:")
        print(trades_df["reason"].value_counts())
    else:
        print("No completed trades!")
else:
    print("No signals found!")

# === PARAMETER SENSITIVITY ANALYSIS (CONSERVATIVE) ===
print("\n" + "=" * 60)
print("CONSERVATIVE PARAMETER SENSITIVITY ANALYSIS")
print("=" * 60)

# Test S3 with different volume thresholds (still reasonable range)
print("S3 Abnormal Volume - Volume Threshold Sensitivity:")
for vol_mult in [1.2, 1.5, 1.8, 2.0, 2.5]:
    qd_test = qd.copy()
    qd_test["S3_test"] = ((qd_test["Volume"] > vol_mult * qd_test["ma20"]) & 
                         (qd_test["Close"] > qd_test["Open"]) & 
                         qd_test["bull"] & qd_test["ng"]).astype(int).shift(1)
    signals_test = qd_test[qd_test["S3_test"] == 1].dropna()
    print(f"  Volume > {vol_mult:.1f}x MA20: {len(signals_test)} signals ({len(signals_test)/5:.1f}/yr)")

# Test S5 Short with different SPY conditions (still reasonable)
print("\nS5 ORB Short - SPY Condition Sensitivity:")
spy_conditions = [
    ("Always allow", lambda sbull: pd.Series([True]*len(sbull), index=sbull.index)),
    ("Only when bearish", lambda sbull: ~sbull),
    ("Only when strongly bearish (200MA < 50MA by 2%)", lambda sbull: (sbull == False) & (spy.ewm(span=50).mean() < spy.ewm(span=200).mean() * 0.98)),
    ("Never (contrarian test)", lambda sbull: sbull)  # Opposite of original
]

for desc, condition_func in spy_conditions:
    q_test = q.copy()
    spy_condition = condition_func(sbull).reindex(q_test.index, method='ffill').fillna(True)
    q_test["S5S_test"] = (q_test["ORBwin"] & (q_test["Close"] < q_test["ORBLo"]) & 
                         spy_condition & q_test["NG"] & q_test["ORBLo"].notna()).astype(int)
    signals_test = q_test[q_test["S5S_test"] == 1]
    print(f"  {desc}: {len(signals_test)} signals ({len(signals_test)/5:.1f}/yr)")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)
