#!/usr/bin/env python3
"""
Quality Factor Test - Uses YOUR existing data pipeline
No new data needed - leverages what you already have
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

print("🧪 Testing Quality/Profitability Factor...")

# REUSE YOUR EXACT DATA LOADING FROM pillar_allocation.py (lines 5-48)
full_yearly_code = open('/Users/colindayer/nas100_backtest/full_yearly.py').read()
split_point = full_yearly_code.find('# ── run all')
exec(full_yearly_code[:split_point])  # Gets q, gld, vmult, SLIP, YEARS

btc_preamble = open('/Users/colindayer/nas100_backtest/btc_sweep_test.py').read()
split_point2 = btc_preamble.find('def run(sl')
exec(btc_preamble[:split_point2])  # Gets d (BTC data)

# EXTRACT PRICE SERIES (NOT P&L) - THIS IS KEY
qqq_close = q['Close']  # QQQ hourly close
gld_data = pd.read_csv('/Users/colindayer/nas100_backtest/gld_hourly_7y.csv')
gld_data['timestamp'] = pd.to_datetime(gld_data['timestamp'])
gld_data = gld_data.set_index('timestamp')
gld_close = gld_data['Close']  # GLD hourly close
btc_close = d['Close']  # BTC hourly close

# CALCULATE QUALITY PROXY: EARNINGS YIELD (12-MONTH TOTAL RETURN INVERTED)
def earnings_yield_proxy(price_series):
    """12-month total return as quality proxy (more negative = better value)"""
    return -price_series.pct_change(252)  # Negative 12m return = cheaper/more profitable

qqq_ey = earnings_yield_proxy(qqq_close)
gld_ey = earnings_yield_proxy(gld_close)
btc_ey = earnings_yield_proxy(btc_close)

# RESAMPLE TO DAILY
qqq_ey_d = qqq_ey.resample('D').last()
gld_ey_d = gld_ey.resample('D').last()
btc_ey_d = btc_ey.resample('D').last()

# COMBINE
ey_df = pd.DataFrame({
    'qqq': qqq_ey_d,
    'gld': gld_ey_d,
    'btc': btc_ey_d
}).fillna(method='ffill').fillna(0)

# CREATE QUALITY SIGNALS: LONG TOP 30% (highest quality), SHORT BOTTOM 30%
def quality_signal(series):
    ranks = series.rank(pct=True)  # 0=worst quality, 1=best quality
    return (ranks > 0.7).astype(int) - (ranks < 0.3).astype(int)  # -1, 0, or 1

qqq_sig = quality_signal(ey_df['qqq'])
gld_sig = quality_signal(ey_df['gld'])
btc_sig = quality_signal(ey_df['btc'])

# EQUAL WEIGHT PORTFOLIO
portfolio_signal = (qqq_sig + gld_sig + btc_sig) / 3
portfolio_signal = np.clip(portfolio_signal, -1, 1)

# BACKTEST USING YOUR EXISTING LOGIC FRAMEWORK
# Simulate what your trading functions would produce
prices = pd.DataFrame({
    'qqq': qqq_close,
    'gld': gld_close,
    'btc': btc_close
}).resample('D').last().ffill()

daily_returns = prices.pct_change()
positions = portfolio_signal.shift(1).fillna(0)  # Yesterday's signal
daily_pnl = (positions * daily_returns).sum(axis=1)  # Equal weight

# CALCULATE METRICS (IDENTICAL TO YOUR pillar_allocation.py)
cumulative = (1 + daily_pnl.fillna(0)).cumprod()
total_return = cumulative.iloc[-1] - 1
years = len(daily_pnl) / 252
cagr = (1 + total_return)**(1/years) - 1 if years > 0 else 0

excess_ret = daily_pnl  # Assuming zero risk-free
sharpe = np.mean(excess_ret) / np.std(excess_ret) * np.sqrt(252) if np.std(excess_ret) > 0 else 0

roll_max = np.maximum.accumulate(cumulative)
drawdown = (cumulative - roll_max) / roll_max
max_dd = np.min(drawdown)

# DISPLAY RESULTS
print("\n" + "="*60)
print("QUALITY FACTOR BACKTEST RESULTS (2019-2025 FULL SAMPLE) ")
print("="*60)
print(f"CAGR:           {cagr:>8.2%}")
print(f"Sharpe Ratio:   {sharpe:>8.2f}")
print(f"Max Drawdown:   {max_dd:>8.2%}")
print(f"Total Return:   {total_return:>8.2%}")

# QUICK CORRELATION CHECK WITH YOUR PILLARS
nasdaq = (trades_intraday("S1",0.007,0.015,3.0) + trades_intraday("S4",0.005,0.015,3.0) +
          trades_intraday("S5L",0.005,0.010,2.5) + trades_intraday("S5S",0.003,0.010,2.5,short=True))
gold = trades_gold()
btc = trades_btc()

def pnl_to_returns(pnl_list):
    if not pnl_list: return pd.Series(dtype=float)
    dates, pnls = zip(*pnl_list)
    return pd.Series(pnls, index=pd.DatetimeIndex(dates)).resample('D').sum().ffill() / 10000

nasdaq_ret = pnl_to_returns(nasdaq)
gold_ret = pnl_to_returns(gold)
btc_ret = pnl_to_returns(btc)

# Strategy returns
strat_ret = (positions * daily_returns).sum(axis=1)

# Correlations
corr_nasdaq = np.corrcoef(strat_ret.dropna(), nasdaq_ret.reindex(strat_ret.index).dropna())[0,1]
corr_gold = np.corrcoef(strat_ret.dropna(), gold_ret.reindex(strat_ret.index).dropna())[0,1]
corr_btc = np.corrcoef(strat_ret.dropna(), btc_ret.reindex(strat_ret.index).dropna())[0,1]

print("\n" + "="*60)
print(" CORRELATION WITH YOUR EXISTING PILLARS ")
print("="*60)
print(f"Nasdaq (S1+S4+S5L+S5S): {corr_nasdaq:>+6.2f}")
print(f"Gold (FVG):               {corr_gold:>+6.2f}")
print(f"BTC (Sweep):              {corr_btc:>+6.2f}")
max_corr = max(abs(corr_nasdaq), abs(corr_gold), abs(corr_btc))
print(f"\nMax Absolute Correlation: {max_corr:>6.2f}")

if max_corr < 0.3:
    print("✅ EXCELLENT: Low correlation - strong diversification candidate")
elif max_corr < 0.5:
    print("⚠️  MODERATE: Some correlation - may still add value")
else:
    print("❌ HIGH: Too correlated - limited diversification benefit")

print("\n" + "="*60)
print(" NEXT STEPS IF RESULTS LOOK PROMISING ")
print("="*60)
print("1. Run OOS validation (2023-2025) - NEVER peek during development!")
print("2. If OOS Sharpe > Equal Weight AND OOS MaxDD ≤ Equal Weight MaxDD:")
print("   → Integrate as 4th pillar in pillar_allocation.py")
print("3. I'll give you the exact integration code if it passes tests")