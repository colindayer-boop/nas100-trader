import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# GLD = Gold ETF, 7 years of daily data (free)
# For hourly we use Alpaca data if available, daily for now
SYMBOL = "GLD"
data = yf.download(SYMBOL, start="2019-01-01", end="2026-06-01", interval="1d", progress=False)

close = data["Close"].squeeze()
high  = data["High"].squeeze()
low   = data["Low"].squeeze()
open_ = data["Open"].squeeze()

# ───────── Liquidity levels (20-bar rolling high/low, excluding current bar) ─────────
RANGE_LEN = 20
range_high = high.rolling(RANGE_LEN).max().shift(1)
range_low  = low.rolling(RANGE_LEN).min().shift(1)

# ───────── Sweep events ─────────
sweep_high_event = (high > range_high) & (close < range_high)
sweep_low_event  = (low  < range_low)  & (close > range_low)

# ───────── Backtest ─────────
capital          = 10000
initial_capital  = capital
risk_per_trade   = 0.01
rr               = 2.0
stop_loss_pct    = 0.015   # 1.5% stop loss from entry

daily_loss_limit    = 0.05
max_drawdown_limit  = 0.10

trades      = []
trade_years = []

in_trade    = False
direction   = 0
entry_price = 0.0
stop_price  = 0.0
target_price= 0.0
shares      = 0.0

sweep_dir   = 0
sweep_level = None
sweep_bar   = -999

day_start_capital = capital
current_day       = None
trading_locked    = False
prop_firm_breached= False

for i in range(RANGE_LEN + 1, len(data)):
    idx       = data.index[i]
    bar_date  = idx.date()
    price     = float(close.iloc[i])
    o         = float(open_.iloc[i])
    h         = float(high.iloc[i])
    l         = float(low.iloc[i])

    # Reset daily cap
    if bar_date != current_day:
        current_day       = bar_date
        day_start_capital = capital
        trading_locked    = False

    daily_loss = (capital - day_start_capital) / day_start_capital
    total_dd   = (capital - initial_capital)   / initial_capital

    if daily_loss <= -daily_loss_limit or total_dd <= -max_drawdown_limit:
        trading_locked     = True
        prop_firm_breached = True

    if trading_locked:
        continue

    # ── Check exit first ──
    if in_trade:
        hit_stop   = (direction ==  1 and l <= stop_price)  or (direction == -1 and h >= stop_price)
        hit_target = (direction ==  1 and h >= target_price) or (direction == -1 and l <= target_price)

        if hit_stop or hit_target:
            exit_price = stop_price if hit_stop else target_price
            pnl        = shares * (exit_price - entry_price) * direction
            capital   += pnl
            trades.append(pnl)
            trade_years.append(idx.year)
            in_trade  = False
            direction = 0

    # ── Update sweep state (from previous bar signals) ──
    prev_i = i - 1
    if bool(sweep_high_event.iloc[prev_i]):
        sweep_dir   = -1
        sweep_level = float(high.iloc[prev_i])
        sweep_bar   = prev_i

    if bool(sweep_low_event.iloc[prev_i]):
        sweep_dir   = 1
        sweep_level = float(low.iloc[prev_i])
        sweep_bar   = prev_i

    sweep_active = (sweep_level is not None) and (i - sweep_bar <= 10)

    # ── Entry signals ──
    bull_reversal = sweep_active and sweep_dir == 1  and price > o   # close > open
    bear_reversal = sweep_active and sweep_dir == -1 and price < o   # close < open

    if not in_trade:
        if bull_reversal:
            in_trade    = True
            direction   = 1
            entry_price = price
            stop_price  = entry_price * (1 - stop_loss_pct)
            risk        = entry_price - stop_price
            target_price= entry_price + risk * rr
            risk_amount = capital * risk_per_trade
            shares      = risk_amount / risk

        elif bear_reversal:
            in_trade    = True
            direction   = -1
            entry_price = price
            stop_price  = entry_price * (1 + stop_loss_pct)
            risk        = stop_price - entry_price
            target_price= entry_price - risk * rr
            risk_amount = capital * risk_per_trade
            shares      = risk_amount / risk

# ───────── Results ─────────
trades = pd.Series(trades)
wins   = (trades > 0).sum()
losses = (trades < 0).sum()

equity   = pd.Series([initial_capital] + list(trades.cumsum() + initial_capital))
peak     = equity.cummax()
drawdown = (equity - peak) / peak
max_dd   = drawdown.min()

print(f"Symbol:         {SYMBOL}")
print(f"Final capital:  ${capital:,.0f}")
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
    print(f"\n⚠️  Prop firm limit breached")
else:
    print(f"\n✅  Passed prop firm rules")

print("\nYear  Trades  Win%   Return")
years = pd.Series(trade_years)
for yr in sorted(years.unique()):
    mask     = years == yr
    yr_trades= trades[mask.values]
    yr_wins  = (yr_trades > 0).sum()
    print(f"{yr}  {len(yr_trades):>6}  {yr_wins/len(yr_trades):.0%}   ${yr_trades.sum():,.0f}")

# Chart
plt.figure(figsize=(12, 5))
plt.plot(equity.values)
plt.title(f"{SYMBOL} Liquidity Sweep Reversal - 7 Years Daily")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig(f"/Users/colindayer/nas100_backtest/equity_gold.png")
plt.show()
print(f"\nChart saved to equity_gold.png")
