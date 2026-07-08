import pandas as pd
import matplotlib.pyplot as plt
import pytz

# Load 7 years of hourly QQQ data from Alpaca
df = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]

# Convert to Eastern time for session logic
eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)

data = df[["open", "high", "low", "close"]].copy()
data.columns = ["Open", "High", "Low", "Close"]

close = data["Close"]
high = data["High"]
low = data["Low"]

# --- ASIAN SESSION HIGH/LOW (6pm-2am EST) ---
def is_asian(idx):
    h = idx.hour
    return h >= 18 or h < 2

data["Asian"] = data.index.map(is_asian)

# Get date label: Asian session belongs to the NEXT trading day
def session_date(idx):
    if idx.hour >= 18:
        return (idx + pd.Timedelta(days=1)).date()
    return idx.date()

data["SessionDate"] = data.index.map(session_date)

asian_bars = data[data["Asian"]]
asian_high = asian_bars.groupby("SessionDate")["High"].max()
asian_low = asian_bars.groupby("SessionDate")["Low"].min()

data["AsianHigh"] = data["SessionDate"].map(asian_high)
data["AsianLow"] = data["SessionDate"].map(asian_low)

# --- SESSION FILTERS (London + NY only) ---
def in_london(idx):
    return 2 <= idx.hour < 5

def in_ny(idx):
    return (idx.hour == 9 and idx.minute >= 30) or (10 <= idx.hour < 12)

data["InSession"] = data.index.map(lambda x: in_london(x) or in_ny(x))

# --- VOLATILITY FILTER (ATR) ---
prev_close = close.shift(1)
tr = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs()
], axis=1).max(axis=1)
atr = tr.rolling(14).mean()
atr_avg = atr.rolling(200).mean()
data["HighVol"] = atr > 1.5 * atr_avg

# --- DAILY RANGE FILTER ---
data["Date"] = data.index.date
daily_high = data.groupby("Date")["High"].transform("max")
daily_low = data.groupby("Date")["Low"].transform("min")
data["DailyRange"] = daily_high - daily_low
data["AvgDailyRange"] = data["DailyRange"].groupby(data["Date"]).first().rolling(14).mean()
data["AvgDailyRange"] = data["Date"].map(
    data.groupby("Date")["DailyRange"].first().rolling(14).mean()
)
data["RangeOk"] = (
    (data["DailyRange"] >= data["AvgDailyRange"] * 0.6) &
    (data["DailyRange"] <= data["AvgDailyRange"] * 1.4)
)

# --- DAILY TREND FILTER (50-day EMA on 4pm daily closes) ---
daily_close = data[data.index.hour == 16][["Close"]].copy()
daily_close.index = daily_close.index.date          # keep as datetime.date (no tz)
daily_close = daily_close[~daily_close.index.duplicated(keep="last")]
daily_ema50 = daily_close["Close"].ewm(span=50).mean()
# data["Date"] is also datetime.date — map directly without converting index
data["DailyEMA50"]     = data["Date"].map(daily_ema50.to_dict())
data["DailyUptrend"]   = close > data["DailyEMA50"]
data["DailyDowntrend"] = close < data["DailyEMA50"]

# --- SWEEP SIGNALS ---
data["SweepHigh"] = (high > data["AsianHigh"]) & (close < data["AsianHigh"])
data["SweepLow"] = (low < data["AsianLow"]) & (close > data["AsianLow"])

data["Signal"] = 0
long_cond = (
    data["SweepLow"] &
    data["InSession"] &
    data["DailyUptrend"] &
    ~data["HighVol"] &
    data["RangeOk"] &
    data["AsianHigh"].notna()
)
short_cond = (
    data["SweepHigh"] &
    data["InSession"] &
    data["DailyDowntrend"] &
    ~data["HighVol"] &
    data["RangeOk"] &
    data["AsianHigh"].notna()
)
data.loc[long_cond, "Signal"] = 1
data.loc[short_cond, "Signal"] = -1

print("Long signals:", (data["Signal"] == 1).sum())
print("Short signals:", (data["Signal"] == -1).sum())

# --- BACKTEST WITH PROP FIRM RULES ---
capital = 10000
initial_capital = capital
risk_per_trade = 0.01
stop_loss_pct = 0.015
target_rr = 3.0

daily_loss_limit = 0.05
max_drawdown_limit = 0.10

trades = []
trade_years = []
in_trade = False
direction = 0
entry_price = 0
stop_price = 0
target_price = 0
shares = 0

day_start_capital = capital
current_day = None
trading_locked = False
prop_firm_breached = False

for i in range(1, len(data)):
    bar_date = data.index[i].date()
    price = float(close.iloc[i])
    signal = int(data["Signal"].iloc[i - 1])

    if bar_date != current_day:
        current_day = bar_date
        day_start_capital = capital
        trading_locked = False

    daily_loss = (capital - day_start_capital) / day_start_capital
    total_dd = (capital - initial_capital) / initial_capital

    if daily_loss <= -daily_loss_limit or total_dd <= -max_drawdown_limit:
        trading_locked = True
        prop_firm_breached = True

    if trading_locked:
        continue

    if not in_trade and signal != 0:
        in_trade = True
        direction = signal
        entry_price = price
        risk_amount = capital * risk_per_trade

        if direction == 1:
            stop_price = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + stop_loss_pct * target_rr)
        else:
            stop_price = entry_price * (1 + stop_loss_pct)
            target_price = entry_price * (1 - stop_loss_pct * target_rr)

        shares = risk_amount / (entry_price * stop_loss_pct)

    elif in_trade:
        hit_stop = (direction == 1 and price <= stop_price) or (direction == -1 and price >= stop_price)
        hit_target = (direction == 1 and price >= target_price) or (direction == -1 and price <= target_price)

        if hit_stop or hit_target:
            pnl = shares * (price - entry_price) * direction
            capital += pnl
            trades.append(pnl)
            trade_years.append(data.index[i].year)
            in_trade = False
            direction = 0

trades = pd.Series(trades)
wins = (trades > 0).sum()
losses = (trades < 0).sum()

equity = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak = equity.cummax()
drawdown = (equity - peak) / peak
max_dd = drawdown.min()

print(f"\nFinal capital:  ${capital:,.0f}")
print(f"Total return:   {(capital - initial_capital) / initial_capital:.1%}")
print(f"Max drawdown:   {max_dd:.1%}")
print(f"Total trades:   {len(trades)}")
if len(trades) > 0:
    print(f"Win rate:       {wins / len(trades):.1%}")
    print(f"Avg win:        ${trades[trades > 0].mean():,.0f}")
    print(f"Avg loss:       ${trades[trades < 0].mean():,.0f}")
    pf = trades[trades > 0].sum() / abs(trades[trades < 0].sum())
    print(f"Profit factor:  {pf:.2f}")

if prop_firm_breached:
    print(f"\n⚠️  Prop firm limit breached at some point")
else:
    print(f"\n✅  Passed prop firm rules — no limit breached")

print("\nYear  Trades  Win%   Return")
years = pd.Series(trade_years)
for yr in sorted(years.unique()):
    mask = years == yr
    yr_trades = trades[mask.values]
    yr_wins = (yr_trades > 0).sum()
    print(f"{yr}  {len(yr_trades):>6}  {yr_wins/len(yr_trades):.0%}   ${yr_trades.sum():,.0f}")

# Chart
plt.figure(figsize=(12, 5))
plt.plot(equity.values)
plt.title("QQQ Asian Sweep Strategy - Daily Trend + Asian Range Filter")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_7y_hourly.png")
plt.close()
print("\nChart saved to equity_7y_hourly.png")
