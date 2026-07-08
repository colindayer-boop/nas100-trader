"""
ORB Strategy — QQQ 1-minute bars
Based on: Zarattini & Aziz (2023)
Data: Alpaca free tier (qqq_1min_7y.csv)

Filters that make it work:
  - Opening range = first 30 minutes (9:30-10:00am ET)
  - Entry window: 10:00am-1:00pm only
  - Fixed 1% stop loss (not ORB low — too wide on 1-min)
  - 3:1 reward-to-risk
  - VIX 21d avg < 20 only (aggressive VIX filter — skips high-vol regimes)
  - SPY golden cross (no longs in bear market)
  - Normal range filter: ORB range < 1.2x 20-day avg
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytz
import yfinance as yf

STOP_PCT     = 0.010   # 1% fixed stop
TARGET_RR    = 3.0
RISK_PCT     = 0.010   # 1% risk per trade
CAPITAL_INIT = 10_000
DAILY_LIMIT  = 0.05
DD_LIMIT     = 0.10
VIX_PAUSE    = 20      # pause above this (aggressive filter)
DATA_FILE    = "/Users/colindayer/nas100_backtest/qqq_1min_7y.csv"

print("Loading 1-min data...")
df = pd.read_csv(DATA_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
if "symbol" in df.columns: df = df[df["symbol"] == "QQQ"]

eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)
df = df[["open","high","low","close","volume"]].copy()
df.columns = ["Open","High","Low","Close","Volume"]
df = df[(df.index.hour >= 9) & (df.index.hour < 16)]
df = df[~((df.index.hour == 9) & (df.index.minute < 30))]
df["Date"] = df.index.date
print(f"RTH bars: {len(df):,}")

# Opening range (first 30 bars = 9:30-10:00am)
orb_high, orb_low = {}, {}
for d, grp in df.groupby("Date"):
    orb = grp.iloc[:30]
    if len(orb) >= 15:
        orb_high[d] = orb["High"].max()
        orb_low[d]  = orb["Low"].min()
df["ORBHigh"] = df["Date"].map(orb_high)
df["ORBLow"]  = df["Date"].map(orb_low)

# Normal range filter
df["ORBRangePct"] = (df["ORBHigh"] - df["ORBLow"]) / df["Close"]
daily_rng = df.drop_duplicates("Date").set_index("Date")["ORBRangePct"]
df["AvgRangePct"] = df["Date"].map(daily_rng.rolling(20).mean().shift(1))
df["NormalRange"] = df["ORBRangePct"] < df["AvgRangePct"] * 1.2

# VIX + SPY regime
start_str = str(df.index[0].date())
end_str   = str(df.index[-1].date())
print("Downloading VIX + SPY...")
vix = yf.download("^VIX", start=start_str, end=end_str, progress=False)["Close"]
if isinstance(vix, pd.DataFrame): vix = vix.iloc[:,0]
vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
vix_ma21 = vix.rolling(21).mean()

spy = yf.download("SPY", start=start_str, end=end_str, progress=False)["Close"]
if isinstance(spy, pd.DataFrame): spy = spy.iloc[:,0]
spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
spy_bull = spy.ewm(span=50,adjust=False).mean() > spy.ewm(span=200,adjust=False).mean()

dates  = sorted(df["Date"].unique())
all_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
vbd = vix_ma21.asof(all_ts); vbd.index = [t.date() for t in vbd.index]
sbd = spy_bull.asof(all_ts);  sbd.index = [t.date() for t in sbd.index]

def vmult(v):
    if pd.isna(v) or v > VIX_PAUSE: return 0.0
    return 1.0

df["VIXMult"] = df["Date"].map(vbd.map(vmult)).fillna(1.0)
df["SPYBull"]  = df["Date"].map(sbd).fillna(True).astype(bool)

# Signals
close = df["Close"]
df["InWindow"] = (df.index.hour >= 10) & (df.index.hour < 13)
df["IsClose"]  = (df.index.hour == 15) & (df.index.minute >= 55)

df["Signal"] = 0
df.loc[
    (close > df["ORBHigh"]) & df["InWindow"] & df["SPYBull"] &
    (df["VIXMult"] > 0) & df["ORBHigh"].notna() & df["NormalRange"],
    "Signal"] = 1
df.loc[
    (close < df["ORBLow"]) & df["InWindow"] & ~df["SPYBull"] &
    (df["VIXMult"] > 0) & df["ORBLow"].notna() & df["NormalRange"],
    "Signal"] = -1

# One signal per day
seen = set(); final = {}
for idx in df.index:
    d = idx.date()
    if df.loc[idx, "Signal"] != 0 and d not in seen:
        final[idx] = df.loc[idx, "Signal"]; seen.add(d)
df["Signal"] = 0
for idx, sig in final.items(): df.loc[idx, "Signal"] = sig

print(f"Long signals: {(df.Signal==1).sum()}  Short: {(df.Signal==-1).sum()}")

# Backtest
capital = CAPITAL_INIT; trades = []; tyr = []
in_trade = False; direction = 0
entry_p = stop_p = target_p = shares = 0.0
day_start = capital; cur_day = None; locked = breached = False; traded = False

for i in range(1, len(df)):
    bd     = df.index[i].date(); price = float(close.iloc[i])
    signal = int(df["Signal"].iloc[i]); is_close = bool(df["IsClose"].iloc[i])
    vmul   = float(df["VIXMult"].iloc[i])

    if bd != cur_day:
        cur_day = bd; day_start = capital; locked = False; traded = False
    if (capital-day_start)/max(day_start,1) <= -DAILY_LIMIT or \
       (capital-CAPITAL_INIT)/CAPITAL_INIT  <= -DD_LIMIT:
        locked = breached = True
    if locked: continue

    if in_trade and is_close:
        pnl = shares*(price-entry_p)*direction; capital += pnl
        trades.append(pnl); tyr.append(df.index[i].year); in_trade = False; continue

    if in_trade:
        hs = (direction==1 and price<=stop_p) or (direction==-1 and price>=stop_p)
        ht = (direction==1 and price>=target_p) or (direction==-1 and price<=target_p)
        if hs or ht:
            ep = stop_p if hs else target_p
            pnl = shares*(ep-entry_p)*direction; capital += pnl
            trades.append(pnl); tyr.append(df.index[i].year); in_trade = False

    elif signal != 0 and not traded and vmul > 0:
        in_trade = True; traded = True; direction = signal; entry_p = price
        if direction == 1:
            stop_p   = price * (1 - STOP_PCT)
            target_p = price * (1 + STOP_PCT * TARGET_RR)
        else:
            stop_p   = price * (1 + STOP_PCT)
            target_p = price * (1 - STOP_PCT * TARGET_RR)
        shares = (capital * RISK_PCT) / abs(entry_p - stop_p)

# Results
t  = pd.Series(trades); yr = pd.Series(tyr)
eq = pd.Series([CAPITAL_INIT] + list(t.cumsum() + CAPITAL_INIT))
dd = ((eq - eq.cummax()) / eq.cummax()).min()
pf = t[t>0].sum() / abs(t[t<0].sum()) if (t<0).any() else float("inf")

print(f"\n{'='*52}")
print("ORB — QQQ 1-min — Zarattini & Aziz (2023)")
print(f"{'='*52}")
print(f"Return:        {(capital-CAPITAL_INIT)/CAPITAL_INIT:+.1%}")
print(f"Final capital: ${capital:,.0f}")
print(f"Max drawdown:  {dd:.1%}  {'✅' if dd>-0.10 else '❌'}")
print(f"Trades:        {len(t)} ({len(t)/7:.0f}/yr)")
print(f"Win rate:      {(t>0).mean():.0%}")
print(f"Profit factor: {pf:.2f}")
print(f"Prop firm:     {'✅ Never breached' if not breached else '⚠️  Breached'}")

print(f"\nYear  Trades  WR    P&L")
for y in sorted(yr.unique()):
    yt = t[yr.values == y]
    print(f"{y}  {len(yt):>6}  {(yt>0).mean():.0%}  ${yt.sum():+,.0f}")

plt.figure(figsize=(12,5))
plt.plot(eq.values, linewidth=1.2, color="#2196F3")
plt.axhline(CAPITAL_INIT * 0.90, color="red", linestyle="--", alpha=0.4, label="10% DD limit")
plt.title("ORB Strategy — QQQ 1-min — 7 Years\nZarattini & Aziz (2023) | 1% stop | VIX<20 filter")
plt.xlabel("Trade #"); plt.ylabel("Capital ($)")
plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_orb_1min.png", dpi=150)
plt.close()
print("\nChart: equity_orb_1min.png")
