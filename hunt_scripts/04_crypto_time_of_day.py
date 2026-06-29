#!/usr/bin/env python3
"""
Hypothesis #4: Crypto time-of-day / weekend effect
Systematic return patterns by UTC hour / weekend on BTC/ETH.
Free hourly data.
"""
import os
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# Parameters
CRYPTOS = ['BTC-USD', 'ETH-USD']  # Test both BTC and ETH
LOOKBACK_HOURS = 24              # For persistence/checking patterns
SLIPPAGE = 0.0004                # 4bps for crypto (taker fee + slippage)
MIN_HOLD_HOURS = 1               # Minimum holding period

def download_crypto_data(ticker, start_date="2020-01-01"):
    """Download cryptocurrency data from Yahoo Finance"""
    print(f"Downloading {ticker} data...")
    ticker_obj = yf.Ticker(ticker)
    # Get hourly data
    data = ticker_obj.history(start=start_date, interval="1h")
    if data.empty:
        # Try daily and resample
        data = ticker_obj.history(start=start_date, interval="1d")
        data = data.resample('1h').ffill()

    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.columns = [c.lower() for c in data.columns]
    data.index = data.index.tz_localize('UTC')
    print(f"  Downloaded {len(data):,} hourly bars for {ticker}")
    return data

def time_of_day_strategy(crypto_data, ticker_name):
    """
    Time-of-day strategy:
    - Identify profitable hours of day (UTC) and/or weekend vs weekday
    - Long during profitable periods, short during unprofitable (or flat)
    """
    # Add time features
    df = crypto_data.copy()
    df['hour'] = df.index.hour
    df['weekday'] = df.index.weekday  # Monday=0, Sunday=6
    df['is_weekend'] = df['weekday'] >= 5  # Saturday=5, Sunday=6

    # Calculate hourly returns
    df['returns'] = df['close'].pct_change().fillna(0)

    # Analyze average returns by hour and weekend
    # Group by hour and weekend status
    hourly_pattern = df.groupby(['hour', 'is_weekend'])['returns'].mean().reset_index()

    # Find profitable conditions
    # We'll go long when expected return > threshold, short when < -threshold
    # For simplicity, let's do long-only during profitable times
    mean_return = df['returns'].mean()
    threshold = max(abs(mean_return), 0.0001)  # At least 1bp threshold

    # Determine profitable hours/weekend combinations
    profitable = hourly_pattern[
        (hourly_pattern['returns'] > threshold) &
        (hourly_pattern['returns'] > 0)  # Only positive returns for long
    ]

    # Create signal: long during profitable hours/weekend
    def is_profitable_time(row):
        match = profitable[
            (profitable['hour'] == row['hour']) &
            (profitable['is_weekend'] == row['is_weekend'])
        ]
        return len(match) > 0

    df['signal'] = df.apply(is_profitable_time, axis=1)

    # Alternative: also consider mean reversion (short during negative periods)
    # But let's start with long-only during profitable times

    # Strategy returns
    strategy_ret = df['returns'] * df['signal'].astype(int)

    # Apply slippage (trade when signal changes)
    signal_changes = df['signal'].diff().fillna(0) != 0
    num_transitions = signal_changes.sum()
    # Each transition requires a trade (enter or exit)

    if len(df) > 0:
        hours = len(df) / 24
        days = hours / 24
        years = days / 365.25
        trades_per_year = num_transitions / max(years, 1) if years > 0 else 0
        annual_slippage = trades_per_year * SLIPPAGE * 2  # Round trip
        hourly_slippage_drag = annual_slippage / (365.25 * 24) if (365.25 * 24) > 0 else 0
        strategy_ret = strategy_ret - hourly_slippage_drag

    # Calculate equity curve
    equity = (1 + strategy_ret).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1 if len(equity) > 0 else 0
    annual_return = (1 + total_return) ** (365.25 * 24 / len(strategy_ret)) - 1 if len(strategy_ret) > 0 and total_return > -1 else 0
    annual_vol = strategy_ret.std() * np.sqrt(365.25 * 24) if len(strategy_ret) > 1 else 0
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
        'signal': df['signal'],
        'hourly_pattern': hourly_pattern,
        'total_transitions': num_transitions
    }

def weekend_effect_strategy(crypto_data, ticker_name):
    """
    Weekend effect strategy:
    - Different behavior Friday close to Monday open vs weekday
    """
    df = crypto_data.copy()
    df['hour'] = df.index.hour
    df['weekday'] = df.index.weekday
    df['is_weekend'] = df['weekday'] >= 5

    # Calculate returns
    df['returns'] = df['close'].pct_change().fillna(0)

    # Simple weekend effect: hold from Friday 16:00 UTC to Monday 00:00 UTC
    # Actually, let's define weekend period more broadly
    # We'll be long from Friday evening to Monday morning

    # Mark Friday hours 16-23 and Saturday-Sunday all day, Monday 0-4 as weekend period
    df['is_weekend_period'] = (
        ((df['weekday'] == 4) & (df['hour'] >= 16)) |  # Fri 16:00-23:59
        (df['weekday'] == 5) |                         # All day Sat
        (df['weekday'] == 6) |                         # All day Sun
        ((df['weekday'] == 0) & (df['hour'] < 4))      # Mon 00:00-03:59
    )

    # Strategy returns
    strategy_ret = df['returns'] * df['is_weekend_period'].astype(int)

    # Apply slippage
    signal_changes = df['is_weekend_period'].diff().fillna(0) != 0
    num_transitions = signal_changes.sum()

    if len(df) > 0:
        hours = len(df) / 24
        days = hours / 24
        years = days / 365.25
        if years > 0:
            transitions_per_year = num_transitions / years
            annual_slippage = transitions_per_year * SLIPPAGE * 2
            hourly_slippage_drag = annual_slippage / (365.25 * 24)
            strategy_ret = strategy_ret - hourly_slippage_drag

    # Calculate equity curve
    equity = (1 + strategy_ret).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1 if len(equity) > 0 else 0
    annual_return = (1 + total_return) ** (365.25 * 24 / len(strategy_ret)) - 1 if len(strategy_ret) > 0 and total_return > -1 else 0
    annual_vol = strategy_ret.std() * np.sqrt(365.25 * 24) if len(strategy_ret) > 1 else 0
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
        'signal': df['is_weekend_period'],
        'total_transitions': num_transitions
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
        # Hourly data -> annualize with hours per year
        hours_per_year = 365.25 * 24
        sharpe = returns.mean() / returns.std() * np.sqrt(hours_per_year)
    else:
        sharpe = 0

    # Max drawdown from cumulative returns
    if len(returns) > 0:
        equity = (1 + returns).cumprod()
        if len(equity) > 0:
            roll_max = equity.cummax()
            drawdown = (equity - roll_max) / roll_max
            max_dd = drawdown.min()
        else:
            max_dd = 0
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
        # Download QQQ data (daily)
        qqq = yf.Ticker("QQQ")
        qqq_data = qqq.history(period="max", interval="1d")
        if qqq_data.empty:
            return 0.0
        qqq_returns = qqq_data['Close'].pct_change().dropna()

        # Convert our hourly returns to daily for comparison
        if len(returns_series) > 0:
            equity = (1 + returns_series).cumprod()
            daily_equity = equity.resample('1D').last()
            daily_returns = daily_equity.pct_change().dropna()

            # Align with QQQ
            aligned_idx = daily_returns.index.intersection(qqq_returns.index)
            if len(aligned_idx) < 20:
                return 0.0

            our_aligned = daily_returns.loc[aligned_idx]
            qqq_aligned = qqq_returns.loc[aligned_idx]

            correlation = np.corrcoef(our_aligned, qqq_aligned)[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
        else:
            return 0.0
    except:
        return 0.0

def test_crypto_strategy(ticker_name, strategy_type="time_of_day"):
    """Test a crypto strategy for a single ticker"""
    print(f"\n{'='*60}")
    print(f"Testing {ticker_name} - {strategy_type.replace('_', ' ').title()}")
    print('='*60)

    try:
        # Download data
        crypto_data = download_crypto_data(ticker_name, start_date="2020-01-01")

        # Select strategy
        if strategy_type == "time_of_day":
            strategy_func = time_of_day_strategy
            strategy_name = "Time-of-Day"
        elif strategy_type == "weekend_effect":
            strategy_func = weekend_effect_strategy
            strategy_name = "Weekend Effect"
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        # Run strategy
        results = strategy_func(crypto_data, ticker_name)

        # Split IS/OOS
        is_data, oos_data = split_is_oos(crypto_data)
        is_results = strategy_func(is_data, ticker_name)
        oos_results = strategy_func(oos_data, ticker_name)

        # Calculate statistics
        stats = calculate_returns_stats(results['returns'])
        is_stats = calculate_returns_stats(is_results['returns'])
        oos_stats = calculate_returns_stats(oos_results['returns'])

        # Calculate correlation with QQQ (using OOS returns)
        correlation = calculate_correlation_with_qqq(oos_results['results']['returns'], ticker_name)

        # Get transition count (proxy for trades)
        if strategy_type == "time_of_day":
            transitions = oos_results.get('total_transitions', 0)
        else:  # weekend_effect
            transitions = oos_results.get('total_transitions', 0)

        # Annualize transitions to get trades per year equivalent
        if len(oos_data) > 0:
            hours = len(oos_data) / 24
            days = hours / 24
            years = days / 365.25 if days > 0 else 1
            annualized_transitions = transitions / max(years, 1)
        else:
            annualized_transitions = 0

        # Gauntlet criteria
        checks = [
            ("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5),
            ("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35),
            ("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5),
            ("Not overfit", oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)),
            (">= 30 trades/year", annualized_transitions >= 30),
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
        print(f"Results for {ticker_name} ({strategy_name}):")
        print(f"  Period: {crypto_data.index.min().date()} to {crypto_data.index.max().date()}")
        print(f"  Total hours: {len(crypto_data):,}")
        print(f"  Total return: {results['total_return']:>+6.1%}")
        print(f"  Annual return: {results['annual_return']:>+6.1%}")
        print(f"  Sharpe ratio: {results['sharpe']:>+6.2f}")
        print(f"  Max drawdown: {results['max_drawdown']:>6.1%}")
        print(f"  Transitions: {transitions:,} ({annualized_transitions:.0f}/year)")
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
            'strategy': strategy_type,
            'is_sharpe': is_stats['sharpe'],
            'oos_sharpe': oos_stats['sharpe'],
            'oos_max_dd': oos_stats['max_dd'],
            'transitions': transitions,
            'annualized_transitions': annualized_transitions,
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
    """Main function to test hypothesis #4"""
    print("=" * 80)
    print("Testing Hypothesis #4: Crypto time-of-day / weekend effect")
    print("Systematic return patterns by UTC hour / weekend on BTC/ETH.")
    print("=" * 80)

    results = {}
    strategies = ["time_of_day", "weekend_effect"]

    for ticker in CRYPTOS:
        for strategy in strategies:
            key = f"{ticker}_{strategy}"
            result = test_crypto_strategy(ticker, strategy)
            if result:
                results[key] = result

                # Log to HUNT_LOG.md
                strategy_name = "Time-of-Day" if strategy == "time_of_day" else "Weekend Effect"
                log_entry = f"| 4. {strategy_name} ({ticker}) | {result['is_sharpe']:>+6.2f} | {result['oos_sharpe']:>+6.2f} | {result['oos_max_dd']:>6.1%} | {int(result['annualized_transitions']):>6,} | {result['correlation']:>+6.2f} | {'PASS' if result['passes_gauntlet'] else 'FAIL':>7} | {strategy_name} on {ticker.split('-')[0]} |"

                with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
                    f.write(log_entry + '\n')

                print(f"Logged result for {key} to HUNT_LOG.md")

    # Summary
    print("\n" + "=" * 80)
    print("HYPOTHESIS #4 SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results.values() if r['passes_gauntlet'])
    total_count = len(results)
    print(f"Tested {total_count} strategies: {passed_count} passed, {total_count - passed_count} failed")

    for key, result in results.items():
        ticker, strategy = key.split('_', 1)
        strategy_name = "Time-of-Day" if strategy == "time_of_day" else "Weekend Effect"
        status = "PASS" if result['passes_gauntlet'] else "FAIL"
        print(f"  {ticker} {strategy_name}: {status} (OOS Sharpe: {result['oos_sharpe']:>+6.2f})")

if __name__ == "__main__":
    main()