import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# VWAP Trend Trading Strategy
# Based on: Zarattini & Aziz (2023) "VWAP: The Holy Grail for Day Trading Systems"
# Paper result: +671% on QQQ over 5 years, Sharpe 2.1, max drawdown 9.4%
# Rules: long when price closes above VWAP, short when below. Exit at 4pm.
# We adapt to hourly bars (paper used 1-min) and add prop firm rules.

# Download QQQ hourly — Alpaca CSV already on disk
df = pd.read_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.set_index("timestamp")
df = df[df["symbol"] == "QQQ"]

import pytz
eastern = pytz.timezone("US/Eastern")
df.index = df.index.tz_convert(eastern)

data = df[["open", "high", "low", "close", "volume"]].copy()
data.columns = ["Open", "High", "Low", "Close", "Volume"]

close  = data["Close"]
high   = data["High"]
low    = data["Low"]
volume = data["Volume"]

# ── SESSION VWAP (reset every day at 9:30am) ──
data["Date"] = data.index.date
data["RTH"]  = data.index.map(lambda x: 9 <= x.hour < 16)  # regular trading hours

# Only compute VWAP during RTH
data["TypicalPrice"] = (high + low + close) / 3
data["TPxVol"]       = data["TypicalPrice"] * volume

# Running cumulative VWAP per day (RTH only)
vwap_vals = []
cum_tpvol = 0.0
cum_vol   = 0.0
prev_date = None

for i in range(len(data)):
    row = data.iloc[i]
    d   = row["Date"]
    if d != prev_date:
        cum_tpvol = 0.0
        cum_vol   = 0.0
        prev_date = d
    if row["RTH"]:
        cum_tpvol += row["TPxVol"]
        cum_vol   += row["Volume"]
    vwap = cum_tpvol / cum_vol if cum_vol > 0 else float("nan")
    vwap_vals.append(vwap)

data["VWAP"] = vwap_vals

# ── SIGNAL: close above VWAP = long, close below = short ──
# Only trade during RTH, only enter at start of each session
data["AboveVWAP"] = close > data["VWAP"]

# Morning session only (9:30am-12pm) for entries — paper found most P&L accrues then
data["MorningSession"] = data.index.map(lambda x: 9 <= x.hour < 12)
data["CloseHour"]      = data.index.map(lambda x: x.hour == 15)  # exit at 4pm bar

# ── BACKTEST ──
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
session_traded     = False  # one trade per session

for i in range(1, len(data)):
    bar_date = data.index[i].date()
    price    = float(close.iloc[i])
    is_rth   = bool(data["RTH"].iloc[i])
    is_morning = bool(data["MorningSession"].iloc[i])
    is_close   = bool(data["CloseHour"].iloc[i])
    above_vwap = bool(data["AboveVWAP"].iloc[i - 1])

    # Reset daily
    if bar_date != current_day:
        current_day       = bar_date
        day_start_capital = capital
        trading_locked    = False
        session_traded    = False

    if (capital - day_start_capital) / day_start_capital <= -daily_loss_limit or \
       (capital - initial_capital)   / initial_capital   <= -max_dd_limit:
        trading_locked     = True
        prop_firm_breached = True

    if trading_locked or not is_rth:
        continue

    # Force exit at market close
    if in_trade and is_close:
        pnl       = shares * (price - entry_price) * direction
        capital  += pnl
        trades.append(pnl)
        trade_years.append(data.index[i].year)
        in_trade  = False
        direction = 0
        continue

    # Check stop/target
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

    # Entry: morning session, no active trade, one per day
    elif is_morning and not session_traded and not pd.isna(data["VWAP"].iloc[i]):
        in_trade      = True
        session_traded= True
        direction     = 1 if above_vwap else -1
        entry_price   = price
        if direction == 1:
            stop_price   = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + stop_loss_pct * target_rr)
        else:
            stop_price   = entry_price * (1 + stop_loss_pct)
            target_price = entry_price * (1 - stop_loss_pct * target_rr)
        risk   = abs(entry_price - stop_price)
        shares = (capital * risk_per_trade) / risk

# ── Results ──
trades = pd.Series(trades)
wins   = (trades > 0).sum()
equity = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak   = equity.cummax()
max_dd = ((equity - peak) / peak).min()

print("=" * 45)
print("VWAP TREND TRADING — QQQ hourly 7 years")
print("=" * 45)
print(f"Final capital:  ${capital:,.0f}")
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
plt.title("VWAP Trend Trading — QQQ Hourly 7 Years\n(Based on Zarattini & Aziz 2023)")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("/Users/colindayer/nas100_backtest/equity_vwap.png")
plt.show()
print("\nChart saved to equity_vwap.png")
