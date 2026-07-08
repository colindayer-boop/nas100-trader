import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# 7 years of daily QQQ data - free, no API needed
data = yf.download("QQQ", start="2019-01-01", end="2026-06-01", interval="1d")

close = data["Close"].squeeze()
high = data["High"].squeeze()
low = data["Low"].squeeze()

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
data["DailyRange"] = high - low
data["AvgRange"] = data["DailyRange"].rolling(14).mean()
data["RangeOk"] = (
    (data["DailyRange"] >= data["AvgRange"] * 0.6) &
    (data["DailyRange"] <= data["AvgRange"] * 1.4)
)

# --- PREVIOUS WEEK HIGH/LOW (proxy for Asian range on daily) ---
# On daily bars we use previous 5-day high/low instead of Asian session
lookback = 5
data["RollingHigh"] = high.rolling(lookback).max().shift(1)
data["RollingLow"] = low.rolling(lookback).min().shift(1)

# Sweep = price exceeds the level but closes back inside
data["SweepHigh"] = (high > data["RollingHigh"]) & (close < data["RollingHigh"])
data["SweepLow"] = (low < data["RollingLow"]) & (close > data["RollingLow"])

# --- TREND FILTER: only long above 200 EMA, short below ---
data["EMA200"] = close.ewm(span=200).mean()
data["Uptrend"] = close > data["EMA200"]
data["Downtrend"] = close < data["EMA200"]

# --- SIGNAL ---
data["Signal"] = 0
data.loc[
    data["SweepLow"] & data["Uptrend"] & ~data["HighVol"] & data["RangeOk"],
    "Signal"
] = 1
data.loc[
    data["SweepHigh"] & data["Downtrend"] & ~data["HighVol"] & data["RangeOk"],
    "Signal"
] = -1

print("Long signals:", (data["Signal"] == 1).sum())
print("Short signals:", (data["Signal"] == -1).sum())

# --- BACKTEST WITH PROP FIRM RULES ---
capital = 10000
initial_capital = capital
risk_per_trade = 0.01
stop_loss_pct = 0.02
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
plt.title("QQQ Sweep Strategy - 7 Years Daily")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_7y.png")
plt.show()
