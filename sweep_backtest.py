import warnings
import yfinance as yf
import pandas as pd
import pytz

pd.set_option('future.no_silent_downcasting', True)
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

# Download max available hourly data (Yahoo Finance limit = 2 years for 1h)
data = yf.download("NQ=F", period="2y", interval="1h")

# Download daily data to compute daily range filter
daily = yf.download("NQ=F", period="2y", interval="1d")

# Convert to NY timezone
ny = pytz.timezone("America/New_York")
data.index = data.index.tz_convert(ny)

# --- DAILY RANGE FILTER ---
# Compute daily range and 14-day rolling average; only trade on "normal" range days
daily["DailyRange"] = daily["High"].squeeze() - daily["Low"].squeeze()
daily["AvgDailyRange"] = daily["DailyRange"].rolling(14).mean()
# Normal = between 60% and 140% of the 14-day average range (tighter filter)
daily["RangeOk"] = (
    (daily["DailyRange"] >= 0.6 * daily["AvgDailyRange"]) &
    (daily["DailyRange"] <= 1.4 * daily["AvgDailyRange"])
)
# Map daily filter onto hourly bars by date
daily_range_ok = daily["RangeOk"].copy()
daily_range_ok.index = daily_range_ok.index.normalize()
if daily_range_ok.index.tz is not None:
    daily_range_ok.index = daily_range_ok.index.tz_localize(None)
range_ok_dict = daily_range_ok.to_dict()  # dict lookup avoids NaN + downcasting warning

data["date_key"] = data.index.normalize()
if data["date_key"].dt.tz is not None:
    data["date_key"] = data["date_key"].dt.tz_localize(None)
data["DailyRangeOk"] = data["date_key"].map(range_ok_dict).fillna(False).astype(bool)

close = data["Close"].squeeze()
high = data["High"].squeeze()
low = data["Low"].squeeze()

# --- VOLATILITY FILTER (ATR) ---
prev_close = close.shift(1)
data["TR"] = pd.concat([
    high - low,
    (high - prev_close).abs(),
    (low - prev_close).abs()
], axis=1).max(axis=1)
data["ATR"] = data["TR"].rolling(14).mean()
data["ATR_avg"] = data["ATR"].rolling(200).mean()
data["HighVol"] = data["ATR"] > 1.5 * data["ATR_avg"]

# --- ASIAN SESSION HIGH/LOW ---
hour = data.index.hour
minute = data.index.minute
date = data.index.date

data["InAsia"] = (hour >= 18) | (hour < 2)
data["InLondon"] = (hour >= 2) & (hour < 5)
data["InNY"] = ((hour == 9) & (minute >= 30)) | (hour == 10) | (hour == 11)

asian_high = pd.Series(index=data.index, dtype=float)
asian_low = pd.Series(index=data.index, dtype=float)

unique_dates = pd.Series(date).unique()
for d in unique_dates:
    asia_mask = (date == d) & data["InAsia"]
    if asia_mask.sum() > 0:
        a_high = high[asia_mask].max()
        a_low = low[asia_mask].min()
        asian_high[date == d] = a_high
        asian_low[date == d] = a_low

data["AsianHigh"] = asian_high
data["AsianLow"] = asian_low

# --- SWEEP DETECTION ---
data["SweepAsianHigh"] = (high > data["AsianHigh"]) & (close < data["AsianHigh"])
data["SweepAsianLow"] = (low < data["AsianLow"]) & (close > data["AsianLow"])

# --- SIGNAL ---
data["InSession"] = data["InLondon"] | data["InNY"]
data["Signal"] = 0
data.loc[data["SweepAsianLow"] & data["InSession"] & ~data["HighVol"] & data["DailyRangeOk"], "Signal"] = 1
data.loc[data["SweepAsianHigh"] & data["InSession"] & ~data["HighVol"] & data["DailyRangeOk"], "Signal"] = -1

print("Long signals:", (data["Signal"] == 1).sum())
print("Short signals:", (data["Signal"] == -1).sum())

# --- BACKTEST WITH PROP FIRM RULES ---
capital = 10000
initial_capital = capital
risk_per_trade = 0.01
stop_loss_pct = 0.015
target_rr = 3.0

daily_loss_limit = 0.05   # 5% max daily loss (prop firm rule)
max_drawdown_limit = 0.10  # 10% max total drawdown (prop firm rule)

trades = []
trade_dates = []
trade_ym = []
in_trade = False
direction = 0
entry_price = 0
stop_price = 0
target_price = 0
shares = 0

day_start_capital = capital
current_day = None
trading_locked = False
prop_firm_stopped = False
prop_firm_stop_date = None

for i in range(1, len(data)):
    bar_date = data.index[i].date()
    price = float(close.iloc[i])
    signal = int(data["Signal"].iloc[i - 1])

    # Reset daily loss tracker on new day
    if bar_date != current_day:
        current_day = bar_date
        day_start_capital = capital
        trading_locked = False

    # Check prop firm limits
    daily_loss = (capital - day_start_capital) / day_start_capital
    total_drawdown = (capital - initial_capital) / initial_capital

    if daily_loss <= -daily_loss_limit or total_drawdown <= -max_drawdown_limit:
        trading_locked = True
        if not prop_firm_stopped:
            prop_firm_stopped = True
            prop_firm_stop_date = bar_date

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
            trade_dates.append(data.index[i].year)
            trade_ym.append((data.index[i].year, data.index[i].month))
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

if prop_firm_stopped:
    print(f"\n⚠️  Prop firm limit hit on: {prop_firm_stop_date}")
else:
    print(f"\n✅  Passed prop firm rules — no limit breached")

# --- PER-YEAR BREAKDOWN ---
print("\nYear  Trades  Win%   Return")
years = pd.Series(trade_dates)
for yr in sorted(years.unique()):
    mask = years == yr
    yr_trades = trades[mask.values]
    yr_wins = (yr_trades > 0).sum()
    print(f"{yr}  {len(yr_trades):>6}  {yr_wins/len(yr_trades):.0%}   ${yr_trades.sum():,.0f}")

import matplotlib.pyplot as plt

plt.figure(figsize=(12, 5))
plt.plot(equity.values)
plt.title("Asian Session Sweep Strategy - Daily Range Filter + Prop Firm Rules")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_curve.png", dpi=150)
plt.close()
print("\nChart saved to nas100_backtest/equity_curve.png")
