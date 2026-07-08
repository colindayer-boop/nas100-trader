"""
Opening Range Breakout — 5-minute QQQ
Based on: Zarattini & Aziz (2023)
"Can Day Trading Really Be Profitable? Evidence from ORB on QQQ"

Data: FirstRateData 5-minute QQQ CSV
      Place the downloaded CSV in /Users/colindayer/nas100_backtest/
      and update DATA_FILE below with the exact filename.

Rules (from paper):
  - Opening range = first 30 minutes (9:30-10:00am ET) = first 6 x 5min bars
  - If 10:00am bar closes ABOVE range high → long at open of next bar
  - Stop = range low
  - Target = 2x the range (range high - range low)
  - Exit = 4pm close if not stopped or targeted
  - Filter: only trade if range is not too wide (< 1.5x 20-day avg range)
  - VIX regime: no trades when VIX 21d avg > 25
  - SPY trend: longs in golden cross, shorts in death cross
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytz
import yfinance as yf
import os
import glob

# ── FIND DATA FILE ──
DATA_DIR = "/Users/colindayer/nas100_backtest/"

# Auto-detect FirstRateData CSV (tries common naming patterns)
candidates = (
    glob.glob(DATA_DIR + "QQQ_*.csv") +
    glob.glob(DATA_DIR + "qqq_*.csv") +
    glob.glob(DATA_DIR + "*QQQ*5min*.csv") +
    glob.glob(DATA_DIR + "*QQQ*1min*.csv") +
    glob.glob(DATA_DIR + "*firstrate*QQQ*.csv")
)
# Exclude files we already know about
candidates = [f for f in candidates if "hourly" not in f.lower()
              and "paper" not in f.lower() and "backtest" not in f.lower()]

if not candidates:
    print("❌ No QQQ minute data file found.")
    print(f"   Place the FirstRateData CSV in: {DATA_DIR}")
    print("   Expected filename contains 'QQQ' and '5min' or '1min'")
    print("\n   Once you have the file, run: python3 orb_5min.py")
    exit()

DATA_FILE = candidates[0]
print(f"Loading: {DATA_FILE}")

# ── LOAD DATA ──
df = pd.read_csv(DATA_FILE, header=0)

# FirstRateData format: DateTime, Open, High, Low, Close, Volume
# Detect column names flexibly
df.columns = [c.strip().lower() for c in df.columns]
col_map = {}
for c in df.columns:
    if "date" in c or "time" in c: col_map[c] = "datetime"
    elif c == "open":   col_map[c] = "Open"
    elif c == "high":   col_map[c] = "High"
    elif c == "low":    col_map[c] = "Low"
    elif c == "close":  col_map[c] = "Close"
    elif c == "volume": col_map[c] = "Volume"
df = df.rename(columns=col_map)

df["datetime"] = pd.to_datetime(df["datetime"])
if df["datetime"].dt.tz is None:
    eastern = pytz.timezone("US/Eastern")
    df["datetime"] = df["datetime"].dt.tz_localize(eastern, ambiguous="infer",
                                                    nonexistent="shift_forward")
else:
    eastern = pytz.timezone("US/Eastern")
    df["datetime"] = df["datetime"].dt.tz_convert(eastern)

df = df.set_index("datetime").sort_index()
df = df[["Open", "High", "Low", "Close", "Volume"]]

# Detect bar interval
sample_diff = df.index.to_series().diff().dropna().mode()[0]
bar_minutes = int(sample_diff.total_seconds() / 60)
print(f"Bar interval detected: {bar_minutes} minutes")
print(f"Date range: {df.index[0].date()} → {df.index[-1].date()}")
print(f"Total bars: {len(df):,}")

# ── FILTER TO RTH ONLY ──
df = df[(df.index.hour >= 9) & (df.index.hour < 16)]
df = df[~((df.index.hour == 9) & (df.index.minute < 30))]
df["Date"] = df.index.date

# ── OPENING RANGE (9:30-10:00am = first 30 minutes) ──
bars_in_range = 30 // bar_minutes   # 6 bars for 5min, 30 bars for 1min

def get_opening_range(day_data):
    rth = day_data[(day_data.index.hour == 9) |
                   ((day_data.index.hour == 10) & (day_data.index.minute == 0))]
    rth = rth.iloc[:bars_in_range]
    if len(rth) < bars_in_range // 2:
        return None, None
    return rth["High"].max(), rth["Low"].min()

dates = sorted(df["Date"].unique())
orb_ranges = {}
for d in dates:
    day = df[df["Date"] == d]
    h, l = get_opening_range(day)
    if h and l:
        orb_ranges[d] = (h, l)

df["ORBHigh"] = df["Date"].map({d: v[0] for d, v in orb_ranges.items()})
df["ORBLow"]  = df["Date"].map({d: v[1] for d, v in orb_ranges.items()})

# Range size filter — skip abnormally wide days
df["ORBRange"] = df["ORBHigh"] - df["ORBLow"]
df["ORBRangePct"] = df["ORBRange"] / df["Close"]
daily_range_ma20 = df.drop_duplicates("Date").set_index("Date")["ORBRangePct"].rolling(20).mean().shift(1)
df["AvgRangePct"] = df["Date"].map(daily_range_ma20.to_dict())
df["NormalRange"] = df["ORBRangePct"] < df["AvgRangePct"] * 1.5

# ── VIX + SPY REGIME ──
start_str = str(df.index[0].date())
end_str   = str(df.index[-1].date())
print("Downloading VIX and SPY for regime filters...")

vix_raw = yf.download("^VIX", start=start_str, end=end_str, progress=False)
vix = vix_raw["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:, 0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

spy_raw = yf.download("SPY", start=start_str, end=end_str, progress=False)
spy = spy_raw["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:, 0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_ema50  = spy.ewm(span=50,  adjust=False).mean()
spy_ema200 = spy.ewm(span=200, adjust=False).mean()
spy_bull   = (spy_ema50 > spy_ema200)

all_dates_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
vix_by_date = vix_ma21.asof(all_dates_ts)
spy_by_date = spy_bull.asof(all_dates_ts)
vix_by_date.index = [ts.date() for ts in vix_by_date.index]
spy_by_date.index = [ts.date() for ts in spy_by_date.index]

def vix_mult(v):
    if pd.isna(v): return 1.0
    if v > 25:     return 0.0
    if v >= 20:    return 0.5
    return 1.0

df["VIXMult"] = df["Date"].map(vix_by_date.map(vix_mult)).fillna(1.0)
df["SPYBull"]  = df["Date"].map(spy_by_date).fillna(True).astype(bool)

# ── SIGNALS ──
# Entry window: 10:00am-1:00pm (after range forms, not too late)
df["InWindow"] = (
    ((df.index.hour == 10) & (df.index.minute >= 0)) |
    (df.index.hour == 11) |
    (df.index.hour == 12)
)
df["IsClose"] = (df.index.hour == 15) & (df.index.minute >= 55)

close = df["Close"]
long_cond = (
    (close > df["ORBHigh"]) &
    df["InWindow"] &
    df["SPYBull"] &
    df["NormalRange"] &
    (df["VIXMult"] > 0) &
    df["ORBHigh"].notna()
)
short_cond = (
    (close < df["ORBLow"]) &
    df["InWindow"] &
    ~df["SPYBull"] &
    df["NormalRange"] &
    (df["VIXMult"] > 0) &
    df["ORBLow"].notna()
)
df["Signal"] = 0
df.loc[long_cond,  "Signal"] = 1
df.loc[short_cond, "Signal"] = -1

# One signal per day — first one
seen = set()
final = {}
for idx in df.index:
    d = idx.date()
    if df.loc[idx, "Signal"] != 0 and d not in seen:
        final[idx] = df.loc[idx, "Signal"]
        seen.add(d)
df["Signal"] = 0
for idx, sig in final.items():
    df.loc[idx, "Signal"] = sig

print(f"Long signals:  {(df['Signal']==1).sum()}")
print(f"Short signals: {(df['Signal']==-1).sum()}")

# ── BACKTEST ──
CAPITAL      = 10_000
INIT_CAPITAL = CAPITAL
RISK_PCT     = 0.01
TARGET_RR    = 2.0
DAILY_LIMIT  = 0.05
MAX_DD       = 0.10

trades, trade_years = [], []
in_trade  = False; direction = 0
entry_p   = stop_p = target_p = shares = 0.0
day_start = CAPITAL; cur_day = None
locked    = breached = False; traded_today = False

for i in range(1, len(df)):
    bar_date  = df.index[i].date()
    price     = float(close.iloc[i])
    signal    = int(df["Signal"].iloc[i])
    is_close  = bool(df["IsClose"].iloc[i])
    size_mult = float(df["VIXMult"].iloc[i])
    orb_h     = df["ORBHigh"].iloc[i]
    orb_l     = df["ORBLow"].iloc[i]

    if bar_date != cur_day:
        cur_day = bar_date; day_start = CAPITAL
        locked = False; traded_today = False

    if (CAPITAL - day_start) / max(day_start,1) <= -DAILY_LIMIT or \
       (CAPITAL - INIT_CAPITAL) / INIT_CAPITAL  <= -MAX_DD:
        locked = breached = True

    if locked: continue

    if in_trade and is_close:
        pnl = shares * (price - entry_p) * direction
        CAPITAL += pnl; trades.append(pnl)
        trade_years.append(df.index[i].year)
        in_trade = False; continue

    if in_trade:
        hit_stop   = (direction==1 and price<=stop_p) or (direction==-1 and price>=stop_p)
        hit_target = (direction==1 and price>=target_p) or (direction==-1 and price<=target_p)
        if hit_stop or hit_target:
            exit_p = stop_p if hit_stop else target_p
            pnl = shares * (exit_p - entry_p) * direction
            CAPITAL += pnl; trades.append(pnl)
            trade_years.append(df.index[i].year)
            in_trade = False

    elif signal != 0 and not traded_today and size_mult > 0 and \
         not pd.isna(orb_h) and not pd.isna(orb_l):
        in_trade     = True; traded_today = True
        direction    = signal; entry_p = price
        orb_range    = orb_h - orb_l
        if direction == 1:
            stop_p   = orb_l                        # stop = range low
            target_p = entry_p + orb_range * TARGET_RR
        else:
            stop_p   = orb_h
            target_p = entry_p - orb_range * TARGET_RR
        risk = abs(entry_p - stop_p)
        if risk < entry_p * 0.001: in_trade = False; continue
        shares = (CAPITAL * RISK_PCT * size_mult) / risk

# ── RESULTS ──
t  = pd.Series(trades)
yr = pd.Series(trade_years)
eq = pd.Series([INIT_CAPITAL] + list(t.cumsum() + INIT_CAPITAL))
dd = ((eq - eq.cummax()) / eq.cummax()).min()

print(f"\n{'='*55}")
print("ORB STRATEGY — QQQ 5-min — Zarattini & Aziz (2023)")
print(f"{'='*55}")
print(f"Return:        {(CAPITAL-INIT_CAPITAL)/INIT_CAPITAL:+.1%}")
print(f"Final capital: ${CAPITAL:,.0f}")
print(f"Max drawdown:  {dd:.1%}")
print(f"Total trades:  {len(t)}  ({len(t)/7:.0f}/yr)")
if len(t):
    pf = t[t>0].sum()/abs(t[t<0].sum()) if (t<0).any() else float("inf")
    print(f"Win rate:      {(t>0).mean():.0%}")
    print(f"Profit factor: {pf:.2f}")
    print(f"Avg win:       ${t[t>0].mean():,.0f}")
    print(f"Avg loss:      ${t[t<0].mean():,.0f}")

print(f"\n{'Passed' if not breached else 'Breached'} prop firm rules")

print("\nYear  Trades  Win%   P&L")
for y in sorted(yr.unique()):
    yt = t[yr.values == y]
    print(f"{y}  {len(yt):>6}  {(yt>0).mean():.0%}   ${yt.sum():+,.0f}")

plt.figure(figsize=(12,5))
plt.plot(eq.values, linewidth=1.2)
plt.title("ORB 5-min QQQ — Zarattini & Aziz (2023)\nOpening Range Breakout with VIX + SPY filters")
plt.xlabel("Trade #"); plt.ylabel("Capital ($)")
plt.grid(True, alpha=0.3); plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_orb_5min.png", dpi=150)
plt.close()
print("\nChart: equity_orb_5min.png")
