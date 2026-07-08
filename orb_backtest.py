import pandas as pd
import matplotlib.pyplot as plt
import pytz
import yfinance as yf

# Previous Day High/Low Breakout Strategy
# Classic institutional breakout pattern — works naturally on hourly bars
# Rules:
#   - Range = previous day's high and low (no intraday timing dependency)
#   - Break ABOVE prev day high + volume confirmation → long
#   - Break BELOW prev day low (bear regime only) → short
#   - Stop: opposite side of prev day range
#   - Exit: end of day or stop/target hit
#   - VIX regime filter: no trades when VIX 21d avg > 25
#   - SPY trend filter: longs only in golden cross, shorts only in death cross

# ── LOAD QQQ HOURLY DATA ──
df = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]

eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)

data = df[["open", "high", "low", "close", "volume"]].copy()
data.columns = ["Open", "High", "Low", "Close", "Volume"]
data["Date"] = data.index.date

close  = data["Close"]
high   = data["High"]
low    = data["Low"]
volume = data["Volume"]

# ── VIX REGIME FILTER ──
start_str = str(data.index.min().date())
end_str   = str((data.index.max() + pd.Timedelta(days=5)).date())

print("Downloading ^VIX and SPY...")
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
spy_bull   = spy_ema50 > spy_ema200

all_dates_ts = pd.DatetimeIndex([pd.Timestamp(d) for d in sorted(data["Date"].unique())])
vix_by_date  = vix_ma21.asof(all_dates_ts)
spy_by_date  = spy_bull.asof(all_dates_ts)
vix_by_date.index = [ts.date() for ts in vix_by_date.index]
spy_by_date.index = [ts.date() for ts in spy_by_date.index]

def vix_mult(v):
    if pd.isna(v): return 1.0
    if v > 25:     return 0.0
    if v >= 20:    return 0.5
    return 1.0

data["VIXMult"] = data["Date"].map(vix_by_date.map(vix_mult)).fillna(1.0)
data["SPYBull"]  = data["Date"].map(spy_by_date).fillna(True).astype(bool)

# ── PREVIOUS DAY HIGH/LOW ──
daily_high = data.groupby("Date")["High"].max()
daily_low  = data.groupby("Date")["Low"].min()

dates_sorted = sorted(daily_high.index)
prev_high = {d: daily_high[dates_sorted[i-1]] for i, d in enumerate(dates_sorted) if i > 0}
prev_low  = {d: daily_low[dates_sorted[i-1]]  for i, d in enumerate(dates_sorted) if i > 0}

data["PrevHigh"] = data["Date"].map(prev_high)
data["PrevLow"]  = data["Date"].map(prev_low)

# ── DAILY VOLUME FILTER ──
daily_vol    = data.groupby("Date")["Volume"].sum()
vol_ma20     = daily_vol.rolling(20).mean().shift(1)
high_vol_map = (daily_vol > vol_ma20 * 1.1).to_dict()
data["HighVolDay"] = data["Date"].map(high_vol_map).fillna(False)

data["IsClose"] = data.index.map(lambda x: x.hour == 15)

# ── TRADING WINDOW: 10am-2pm only (avoid chasing late breaks) ──
data["TradingWindow"] = data.index.map(lambda x: 10 <= x.hour < 14)

# ── SIGNALS ──
data["Signal"] = 0
long_cond = (
    (close > data["PrevHigh"]) &
    data["TradingWindow"] &
    data["SPYBull"] &
    data["HighVolDay"] &
    (data["VIXMult"] > 0) &
    data["PrevHigh"].notna()
)
short_cond = (
    (close < data["PrevLow"]) &
    data["TradingWindow"] &
    ~data["SPYBull"] &
    data["HighVolDay"] &
    (data["VIXMult"] > 0) &
    data["PrevLow"].notna()
)
data.loc[long_cond,  "Signal"] = 1
data.loc[short_cond, "Signal"] = -1

# One trade per day — first signal wins
seen_dates = set()
final_signals = {}
for idx in data.index:
    d = idx.date()
    if data.loc[idx, "Signal"] != 0 and d not in seen_dates:
        final_signals[idx] = data.loc[idx, "Signal"]
        seen_dates.add(d)
data["Signal"] = 0
for idx, sig in final_signals.items():
    data.loc[idx, "Signal"] = sig

print("Long signals:", (data["Signal"] == 1).sum())
print("Short signals:", (data["Signal"] == -1).sum())

# ── BACKTEST ──
capital          = 10000
initial_capital  = capital
risk_per_trade   = 0.01
stop_loss_pct    = 0.015
target_rr        = 2.0    # ORB paper uses 2:1 (shorter hold, tighter target)
daily_loss_limit = 0.05
max_dd_limit     = 0.10

trades      = []
trade_years = []
in_trade    = False
direction   = 0
entry_price = stop_price = target_price = shares = 0.0
day_start_capital  = capital
current_day        = None
trading_locked     = False
prop_firm_breached = False
traded_today       = False

for i in range(1, len(data)):
    bar_date   = data.index[i].date()
    price      = float(close.iloc[i])
    signal     = int(data["Signal"].iloc[i])
    is_close   = bool(data["IsClose"].iloc[i])
    size_mult  = float(data["VIXMult"].iloc[i])

    if bar_date != current_day:
        current_day       = bar_date
        day_start_capital = capital
        trading_locked    = False
        traded_today      = False

    if (capital - day_start_capital) / day_start_capital <= -daily_loss_limit or \
       (capital - initial_capital)   / initial_capital   <= -max_dd_limit:
        trading_locked     = True
        prop_firm_breached = True

    if trading_locked:
        continue

    # Force exit at close
    if in_trade and is_close:
        pnl      = shares * (price - entry_price) * direction
        capital += pnl
        trades.append(pnl)
        trade_years.append(data.index[i].year)
        in_trade  = False
        direction = 0
        continue

    if in_trade:
        hit_stop   = (direction ==  1 and price <= stop_price) or \
                     (direction == -1 and price >= stop_price)
        hit_target = (direction ==  1 and price >= target_price) or \
                     (direction == -1 and price <= target_price)
        if hit_stop or hit_target:
            exit_price = stop_price if hit_stop else target_price
            pnl        = shares * (exit_price - entry_price) * direction
            capital   += pnl
            trades.append(pnl)
            trade_years.append(data.index[i].year)
            in_trade  = False

    elif signal != 0 and not traded_today and size_mult > 0:
        prev_h = float(data["PrevHigh"].iloc[i])
        prev_l = float(data["PrevLow"].iloc[i])
        if pd.isna(prev_h) or pd.isna(prev_l):
            continue
        in_trade      = True
        traded_today  = True
        direction     = signal
        entry_price   = price
        # Fixed % stop — prev day level is trigger only, not stop
        if direction == 1:
            stop_price   = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + stop_loss_pct * target_rr)
        else:
            stop_price   = entry_price * (1 + stop_loss_pct)
            target_price = entry_price * (1 - stop_loss_pct * target_rr)
        risk   = abs(entry_price - stop_price)
        shares = (capital * risk_per_trade * size_mult) / risk

# ── RESULTS ──
trades = pd.Series(trades)
wins   = (trades > 0).sum()
equity = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak   = equity.cummax()
max_dd = ((equity - peak) / peak).min()

print(f"\n{'='*50}")
print("PREV DAY HIGH/LOW BREAKOUT — QQQ Hourly 7 Years")
print(f"Institutional breakout pattern, hourly bars")
print(f"{'='*50}")
print(f"Final capital:  ${capital:,.0f}")
print(f"Total return:   {(capital-initial_capital)/initial_capital:.1%}")
print(f"Max drawdown:   {max_dd:.1%}")
print(f"Total trades:   {len(trades)}")
if len(trades) > 0:
    print(f"Win rate:       {wins/len(trades):.1%}")
    print(f"Avg win:        ${trades[trades>0].mean():,.0f}")
    print(f"Avg loss:       ${trades[trades<0].mean():,.0f}")
    pf = trades[trades>0].sum() / abs(trades[trades<0].sum()) if (trades<0).any() else float("inf")
    print(f"Profit factor:  {pf:.2f}")

print(f"\n{'✅ Passed' if not prop_firm_breached else '⚠️  Breached'} prop firm rules")

print("\nYear  Trades  Win%   Return")
years = pd.Series(trade_years)
for yr in sorted(years.unique()):
    mask = years == yr; yt = trades[mask.values]
    print(f"{yr}  {len(yt):>6}  {(yt>0).sum()/len(yt):.0%}   ${yt.sum():,.0f}")

plt.figure(figsize=(12, 5))
plt.plot(equity.values)
plt.title("Prev Day H/L Breakout — QQQ Hourly 7 Years")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_orb.png")
plt.close()
print("\nChart saved to equity_orb.png")
