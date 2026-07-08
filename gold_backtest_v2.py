import pandas as pd
import matplotlib.pyplot as plt
import pytz

# Load 7 years of hourly GLD data
df = pd.read_csv("/Users/colindayer/nas100_backtest/gld_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "GLD"]

eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)

data = df[["open", "high", "low", "close"]].copy()
data.columns = ["Open", "High", "Low", "Close"]

close = data["Close"]
high  = data["High"]
low   = data["Low"]
open_ = data["Open"]

# ── IMPROVEMENT 1: Asian session range (6pm-2am EST) ──
def is_asian(idx):
    return idx.hour >= 18 or idx.hour < 2

def session_date(idx):
    if idx.hour >= 18:
        return (idx + pd.Timedelta(days=1)).date()
    return idx.date()

data["Asian"] = data.index.map(is_asian)
data["SessionDate"] = data.index.map(session_date)

asian_bars = data[data["Asian"]]
asian_high = asian_bars.groupby("SessionDate")["High"].max()
asian_low  = asian_bars.groupby("SessionDate")["Low"].min()

data["AsianHigh"] = data["SessionDate"].map(asian_high)
data["AsianLow"]  = data["SessionDate"].map(asian_low)

# ── IMPROVEMENT 2: London session only (2am-5am EST) ──
data["InLondon"] = data.index.map(lambda x: 2 <= x.hour < 5)

# ── IMPROVEMENT 3: Displacement filter (strong candle body > 60% of range) ──
candle_range = (high - low).replace(0, 0.001)
candle_body  = (close - open_).abs()
data["StrongCandle"] = candle_body / candle_range > 0.6

# ── IMPROVEMENT 4: Fair Value Gap detection ──
# FVG up: low[i] > high[i-2] — gap between candle i-2 high and candle i low
# FVG down: high[i] < low[i-2]
data["FVG_Up"]   = low > high.shift(2)
data["FVG_Down"] = high < low.shift(2)

# ── Sweep events (price pierces Asian range but closes back inside) ──
data["SweepHigh"] = (high > data["AsianHigh"]) & (close < data["AsianHigh"])
data["SweepLow"]  = (low  < data["AsianLow"])  & (close > data["AsianLow"])

# ── Daily trend filter: 50 EMA on daily closes ──
daily_close = data[data.index.hour == 16][["Close"]].copy()
daily_close.index = daily_close.index.date
daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
daily_ema50 = daily_close["Close"].ewm(span=50).mean()
data["Date"] = data.index.date
data["DailyEMA50"]   = data["Date"].map(daily_ema50.to_dict())
data["Uptrend"]      = close > data["DailyEMA50"]
data["Downtrend"]    = close < data["DailyEMA50"]

# ── Signals: sweep + London + strong candle + FVG + trend ──
# Track sweep state
sweep_high_active = pd.Series(False, index=data.index)
sweep_low_active  = pd.Series(False, index=data.index)
sweep_bar_h = -999
sweep_bar_l = -999

for i in range(len(data)):
    if data["SweepHigh"].iloc[i]:
        sweep_bar_h = i
    if data["SweepLow"].iloc[i]:
        sweep_bar_l = i
    sweep_high_active.iloc[i] = (i - sweep_bar_h) <= 10
    sweep_low_active.iloc[i]  = (i - sweep_bar_l) <= 10

data["SweepHighActive"] = sweep_high_active
data["SweepLowActive"]  = sweep_low_active

data["Signal"] = 0
long_cond = (
    data["SweepLowActive"] &
    data["InLondon"] &
    data["StrongCandle"] &
    data["FVG_Up"] &
    data["Uptrend"] &
    data["AsianLow"].notna()
)
short_cond = (
    data["SweepHighActive"] &
    data["InLondon"] &
    data["StrongCandle"] &
    data["FVG_Down"] &
    data["Downtrend"] &
    data["AsianHigh"].notna()
)
data.loc[long_cond, "Signal"]  = 1
data.loc[short_cond, "Signal"] = -1

print("Long signals:", (data["Signal"] == 1).sum())
print("Short signals:", (data["Signal"] == -1).sum())

# ── Backtest ──
capital          = 10000
initial_capital  = capital
risk_per_trade   = 0.01
stop_loss_pct    = 0.015
target_rr        = 3.0
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

for i in range(1, len(data)):
    bar_date = data.index[i].date()
    price    = float(close.iloc[i])
    signal   = int(data["Signal"].iloc[i - 1])

    if bar_date != current_day:
        current_day       = bar_date
        day_start_capital = capital
        trading_locked    = False

    if (capital - day_start_capital) / day_start_capital <= -daily_loss_limit or \
       (capital - initial_capital)   / initial_capital   <= -max_dd_limit:
        trading_locked     = True
        prop_firm_breached = True

    if trading_locked:
        continue

    if in_trade:
        hit_stop   = (direction ==  1 and price <= stop_price)  or (direction == -1 and price >= stop_price)
        hit_target = (direction ==  1 and price >= target_price) or (direction == -1 and price <= target_price)
        if hit_stop or hit_target:
            exit_price = stop_price if hit_stop else target_price
            pnl        = shares * (exit_price - entry_price) * direction
            capital   += pnl
            trades.append(pnl)
            trade_years.append(data.index[i].year)
            in_trade  = False

    elif signal != 0:
        in_trade    = True
        direction   = signal
        entry_price = price
        if direction == 1:
            stop_price   = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + stop_loss_pct * target_rr)
        else:
            stop_price   = entry_price * (1 + stop_loss_pct)
            target_price = entry_price * (1 - stop_loss_pct * target_rr)
        risk    = abs(entry_price - stop_price)
        shares  = (capital * risk_per_trade) / risk

# ── Results ──
trades = pd.Series(trades)
wins   = (trades > 0).sum()

equity   = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak     = equity.cummax()
max_dd   = ((equity - peak) / peak).min()

print(f"\nFinal capital:  ${capital:,.0f}")
print(f"Total return:   {(capital - initial_capital) / initial_capital:.1%}")
print(f"Max drawdown:   {max_dd:.1%}")
print(f"Total trades:   {len(trades)}")
if len(trades) > 0:
    print(f"Win rate:       {wins / len(trades):.1%}")
    print(f"Avg win:        ${trades[trades > 0].mean():,.0f}")
    print(f"Avg loss:       ${trades[trades < 0].mean():,.0f}")
    print(f"Profit factor:  {trades[trades > 0].sum() / abs(trades[trades < 0].sum()):.2f}")

print(f"\n{'⚠️  Prop firm breached' if prop_firm_breached else '✅  Passed prop firm rules'}")

print("\nYear  Trades  Win%   Return")
years = pd.Series(trade_years)
for yr in sorted(years.unique()):
    mask      = years == yr
    yr_trades = trades[mask.values]
    yr_wins   = (yr_trades > 0).sum()
    print(f"{yr}  {len(yr_trades):>6}  {yr_wins/len(yr_trades):.0%}   ${yr_trades.sum():,.0f}")

plt.figure(figsize=(12, 5))
plt.plot(equity.values)
plt.title("GLD Asian Sweep + FVG + London Session - 7 Years Hourly")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_gold_v2.png")
plt.show()
print("\nChart saved to equity_gold_v2.png")
