import yfinance as yf
import pandas as pd

# Download NAS100 data
data = yf.download("NQ=F", start="2018-01-01", end="2024-12-31", interval="1d")

close = data["Close"].squeeze()

# Calculate EMAs
data["EMA20"] = close.ewm(span=20).mean()
data["EMA50"] = close.ewm(span=50).mean()

# Signal
data["Signal"] = 0
data.loc[data["EMA20"] > data["EMA50"], "Signal"] = 1

# ── TRADE-BY-TRADE BACKTEST ──
capital = 10000      # starting capital $10,000
risk_per_trade = 0.01  # risk 1% per trade
stop_loss_pct = 0.02   # stop loss at 2% below entry

trades = []
in_trade = False
entry_price = 0
stop_price = 0

for i in range(1, len(data)):
    price = float(close.iloc[i])
    signal = int(data["Signal"].iloc[i - 1])  # yesterday's signal

    if not in_trade and signal == 1:
        # Enter trade
        in_trade = True
        entry_price = price
        stop_price = entry_price * (1 - stop_loss_pct)
        risk_amount = capital * risk_per_trade
        shares = risk_amount / (entry_price * stop_loss_pct)

    elif in_trade:
        # Check stop loss
        if price <= stop_price:
            loss = shares * (price - entry_price)
            capital += loss
            trades.append(loss)
            in_trade = False

        # Check exit signal
        elif signal == 0:
            profit = shares * (price - entry_price)
            capital += profit
            trades.append(profit)
            in_trade = False

# ── RESULTS ──
trades = pd.Series(trades)
wins = (trades > 0).sum()
losses = (trades < 0).sum()

print(f"Final capital:  ${capital:,.0f}")
print(f"Total return:   {(capital - 10000) / 10000:.1%}")
print(f"Total trades:   {len(trades)}")
print(f"Wins:           {wins}")
print(f"Losses:         {losses}")
print(f"Win rate:       {wins / len(trades):.1%}")
print(f"Max loss trade: ${trades.min():,.0f}")
print(f"Max win trade:  ${trades.max():,.0f}")
import matplotlib.pyplot as plt

# Plot equity curve
equity = [10000]
for t in trades:
    equity.append(equity[-1] + t)

plt.figure(figsize=(12, 5))
plt.plot(equity)
plt.title("NAS100 EMA Strategy - Equity Curve")
plt.xlabel("Trade number")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.show()