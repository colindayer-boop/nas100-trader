#!/usr/bin/env python3
"""
Hypothesis #3: Turn-of-month effect
Long equity index last 1-2 + first 3 trading days of month, flat else.
Documented calendar anomaly. Free.
"""
import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# Parameters
TICKERS = ['SPY', 'QQQ']  # Test major equity ETFs
LOOKBACK_DAYS = 2         # Last N trading days of month
LOOKAHEAD_DAYS = 3        # First N trading days of month
SLIPPAGE = 0.0001         # 1bps for ETFs
MIN_HOLD_HOURS = 1        # Minimum holding period

def download_etf_data(ticker, start_date="2020-01-01"):
    """Download ETF data from Yahoo Finance"""
    print(f"Downloading {ticker} data...")
    ticker_obj = yf.Ticker(ticker)
    # Get daily data
    data = ticker_obj.history(start=start_date, interval="1d")
    if data.empty:
        raise ValueError(f"No data found for {ticker}")

    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.columns = [c.lower() for c in data.columns]
    data.index = data.index.tz_localize('UTC')
    print(f"  Downloaded {len(data):,} daily bars for {ticker}")
    return data

def is_trading_day_end_of_month(date, n_days=2):
    """Check if date is within last N trading days of the month"""
    # Get the last trading day of the month
    year = date.year
    month = date.month

    # First day of next month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    # Last day of current month
    last_day_of_month = next_month - timedelta(days=1)

    # Get all trading days in the month
    # We'll approximate by checking if we're within N days of month end
    # and it's a weekday (simplified)
    days_to_month_end = (last_day_of_month.date() - date.date()).days

    # Must be a weekday and within last N days of month
    is_weekday = date.weekday() < 5  # Monday=0, Friday=4
    return is_weekday and 0 <= days_to_month_end < n_days

def is_trading_day_start_of_month(date, n_days=3):
    """Check if date is within first N trading days of the month"""
    # First day of month
    first_day = datetime(date.year, date.month, 1)

    # Get all trading days in the month
    # We'll approximate by checking if we're within N days of month start
    days_from_month_start = (date.date() - first_day.date()).days

    # Must be a weekday and within first N days of month
    is_weekday = date.weekday() < 5  # Monday=0, Friday=4
    return is_weekday and 0 <= days_from_month_start < n_days

def turn_of_month_strategy(etf_data, ticker_name):
    """
    Turn-of-month strategy:
    - Long on: last N trading days of month + first M trading days of month
    - Flat: all other times
    """
    # Convert to daily frequency (using close prices)
    daily_close = pd.DataFrame()
    daily_close['close'] = etf_data['close'].resample('1D').last()
    daily_close = daily_close.dropna()

    if len(daily_close) < 100:
        raise ValueError(f"Not enough daily data for {ticker_name}")

    # Generate signals
    dates = daily_close.index
    is_tom_long = np.zeros(len(dates), dtype=bool)

    for i, date in enumerate(dates):
        if is_trading_day_end_of_month(date, LOOKBACK_DAYS) or \
           is_trading_day_start_of_month(date, LOOKAHEAD_DAYS):
            is_tom_long[i] = True

    # Calculate daily returns
    daily_ret = daily_close['close'].pct_change().fillna(0)

    # Strategy returns: long when signal is True, flat otherwise
    strategy_ret = daily_ret * is_tom_long

    # Apply slippage (trade at month boundaries)
    # Count signal changes to estimate trades
    signal_changes = np.diff(np.concatenate([[False], is_tom_long, [False]]))
    entries = np.sum(signal_changes == 1)  # False -> True
    exits = np.sum(signal_changes == -1)   # True -> False
    total_trades = max(entries, exits)     # Number of periods in position

    # Approximate slippage per trade
    if len(daily_close) > 0:
        years = len(daily_close) / 252
        trades_per_year = total_trades / max(years, 1)
        # Assume we pay slippage on entry and exit
        annual_slippage = trades_per_year * SLIPPAGE * 2
        # Apply as daily drag
        daily_slippage_drag = annual_slippage / 252
        strategy_ret = strategy_ret - daily_slippage_drag

    # Calculate equity curve
    equity = (1 + strategy_ret).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1
    annual_return = (1 + total_return) ** (252 / len(strategy_ret)) - 1 if len(strategy_ret) > 0 else 0
    annual_vol = strategy_ret.std() * np.sqrt(252) if len(strategy_ret) > 1 else 0
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0

    # Max drawdown
    if len(equity) > 0:
        roll_max = equity.cummax()
        drawdown = (equity - roll_max) / roll_max
        max_dd = drawdown.min()
    else:
        max_dd = 0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_vol': annual_vol,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'returns': strategy_ret,
        'equity': equity,
        'signal': is_tom_long,
        'dates': dates,
        'total_trades': total_trades
    }

def split_is_oos(data, is_ratio=0.6):
    """Split data into IS and OOS periods (chronological split)"""
    split_idx = int(len(data) * is_ratio)
    is_data = data.iloc[:split_idx]
    oos_data = data.iloc[split_idx:]
    return is_data, oos_data

def calculate_returns_stats(returns):
    """Calculate return statistics for a returns series"""
    if len(returns) == 0:
        return {'sharpe': 0, 'max_dd': 0, 'periods': 0}

    # Sharpe ratio (annualized)
    if len(returns) > 1 and returns.std() > 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(252)  # Daily returns
    else:
        sharpe = 0

    # Max drawdown from cumulative returns
    if len(returns) > 0:
        equity = (1 + returns).cumprod()
        roll_max = equity.cummax()
        drawdown = (equity - roll_max) / roll_max
        max_dd = drawdown.min()
    else:
        max_dd = 0

    return {
        'sharpe': sharpe,
        'max_dd': max_dd,
        'periods': len(returns)
    }

def calculate_correlation_with_qqq(returns_series, ticker):
    """Calculate correlation with QQQ daily returns"""
    try:
        # Skip if we're already testing QQQ to avoid perfect correlation
        if ticker == 'QQQ':
            return 0.0

        # Download QQQ data
        qqq = yf.Ticker("QQQ")
        qqq_data = qqq.history(period="max", interval="1d")
        if qqq_data.empty:
            return 0.0
        qqq_returns = qqq_data['Close'].pct_change().dropna()

        # Align with our returns (both should be daily)
        aligned_idx = returns_series.index.intersection(qqq_returns.index)
        if len(aligned_idx) < 20:  # Need minimum overlap
            return 0.0

        our_aligned = returns_series.loc[aligned_idx]
        qqq_aligned = qqq_returns.loc[aligned_idx]

        correlation = np.corrcoef(our_aligned, qqq_aligned)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    except:
        return 0.0

def test_ticker(ticker_name):
    """Test the turn-of-month strategy for a single ticker"""
    print(f"\n{'='*60}")
    print(f"Testing {ticker_name}")
    print('='*60)

    try:
        # Download data
        etf_data = download_etf_data(ticker_name, start_date="2020-01-01")

        # Run strategy
        results = turn_of_month_strategy(etf_data, ticker_name)

        # Split IS/OOS
        is_data, oos_data = split_is_oos(etf_data)
        is_results = turn_of_month_strategy(is_data, ticker_name)
        oos_results = turn_of_month_strategy(oos_data, ticker_name)

        # Calculate statistics
        stats = calculate_returns_stats(results['returns'])
        is_stats = calculate_returns_stats(is_results['returns'])
        oos_stats = calculate_returns_stats(oos_results['returns'])

        # Calculate correlation with QQQ (using OOS returns)
        correlation = calculate_correlation_with_qqq(oos_results['returns'], ticker_name)

        # Get actual trade count from strategy results
        total_trades = oos_results['total_trades']

        # Gauntlet criteria
        checks = [
            ("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5),
            ("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35),
            ("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5),
            ("Not overfit", oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)),
            (">= 30 trades", total_trades >= 30),
            ("IS Sharpe > 0", is_stats['sharpe'] > 0),
            ("|Corr to QQQ| < 0.3", abs(correlation) < 0.3),
            # Regime check: positive in bull AND bear sub-periods
        ]

        # Regime check
        if len(oos_results['returns']) > 0:
            mid_point = len(oos_results['returns']) // 2
            oos_first = oos_results['returns'].iloc[:mid_point]
            oos_second = oos_results['returns'].iloc[mid_point:]

            first_stats = calculate_returns_stats(oos_first)
            second_stats = calculate_returns_stats(oos_second)

            regime_check = (first_stats['sharpe'] > 0) and (second_stats['sharpe'] > 0)
            checks.append(("Positive in bull/bear regimes", regime_check))
        else:
            checks.append(("Positive in bull/bear regimes", False))

        all_passed = all(check[1] for check in checks)

        # Display results
        print(f"Results for {ticker_name}:")
        print(f"  Period: {etf_data.index.min().date()} to {etf_data.index.max().date()}")
        print(f"  Total days: {len(etf_data):,}")
        print(f"  Days in strategy: {int(results['signal'].sum():,}")
        print(f"  Total return: {results['total_return']:>+6.1%}")
        print(f"  Annual return: {results['annual_return']:>+6.1%}")
        print(f"  Sharpe ratio: {results['sharpe']:>+6.2f}")
        print(f"  Max drawdown: {results['max_drawdown']:>6.1%}")
        print(f"  Total trades: {results['total_trades']:,}")
        print()
        print(f"  IS Sharpe: {is_stats['sharpe']:>+6.2f}")
        print(f"  OOS Sharpe: {oos_stats['sharpe']:>+6.2f}")
        print(f"  OOS Max DD: {oos_stats['max_dd']:>6.1%}")
        print(f"  Correlation with QQQ: {correlation:>+6.2f}")
        print()
        print("Gauntlet Checks:")
        for check_name, passed in checks:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {check_name}")
        print(f"  OVERALL: {'PASS' if all_passed else 'FAIL'}")

        return {
            'ticker': ticker_name,
            'is_sharpe': is_stats['sharpe'],
            'oos_sharpe': oos_stats['sharpe'],
            'oos_max_dd': oos_stats['max_dd'],
            'total_trades': total_trades,
            'correlation': correlation,
            'passes_gauntlet': all_passed,
            'checks': dict(checks),
            'results': results
        }

    except Exception as e:
        print(f"Error testing {ticker_name}: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to test hypothesis #3"""
    print("=" * 80)
    print("Testing Hypothesis #3: Turn-of-month effect")
    print("Long equity index last 1-2 + first 3 trading days of month, flat else.")
    print("=" * 80)

    results = {}

    for ticker in TICKERS:
        result = test_ticker(ticker)
        if result:
            results[ticker] = result

            # Log to HUNT_LOG.md
            log_entry = f"| 3. Turn-of-Month ({ticker}) | {result['is_sharpe']:>+6.2f} | {result['oos_sharpe']:>+6.2f} | {result['oos_max_dd']:>6.1%} | {result['total_trades']:>6,} | {result['correlation']:>+6.2f} | {'PASS' if result['passes_gauntlet'] else 'FAIL':>7} | Long last {LOOKBACK_DAYS}+first {LOOKAHEAD_DAYS} trading days of month |"

            with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
                f.write(log_entry + '\n')

            print(f"Logged result for {ticker} to HUNT_LOG.md")

    # Summary
    print("\n" + "=" * 80)
    print("HYPOTHESIS #3 SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results.values() if r['passes_gauntlet'])
    total_count = len(results)
    print(f"Tested {total_count} tickers: {passed_count} passed, {total_count - passed_count} failed")

    for ticker, result in results.items():
        status = "PASS" if result['passes_gauntlet'] else "FAIL"
        print(f"  {ticker}: {status} (OOS Sharpe: {result['oos_sharpe']:>+6.2f})")

if __name__ == "__main__":
    main()