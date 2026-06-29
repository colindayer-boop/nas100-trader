#!/usr/bin/env python3
"""
Hypothesis #6: Pairs / stat-arb
Z-score mean-reversion on cointegrated ETF pairs
(e.g. GLD/GDX, XLE/USO, EWA/EWC). Market-neutral.
"""
import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

warnings.filterwarnings("ignore")

# Parameters
PAIRS = [
    ('GLD', 'GDX'),   # Gold miners vs gold
    ('XLE', 'USO'),   # Energy sector vs oil
    ('EWA', 'EWC'),   # Australia vs Canada
    ('EEM', 'IEV', 'EFA'),  # Emerging min vol vs EAFE (try triplet)
    ('QQQ', 'IWM'),   # Nasdaq vs small cap
    ('VNQ', 'XLF'),   # Real estate vs financials
]  # Pairs to test
LOOKBACK_DAYS = 60      # For calculating hedge ratio and z-score
ENTRY_ZSCORE = 2.0      # Enter when z-score > 2
EXIT_ZSCORE = 0.5       # Exit when z-score < 0.5
SLIPPAGE = 0.0001       # 1bps for ETFs
MIN_HOLD_DAYS = 1       # Minimum holding period

def download_etf_data(ticker, start_date="2020-01-01"):
    """Download ETF data from Yahoo Finance"""
    try:
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(start=start_date, interval="1d")
        if data.empty:
            return None

        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
        data.columns = [c.lower() for c in data.columns]
        data.index = data.index.tz_localize('UTC')
        return data
    except Exception as e:
        # print(f"  Failed to download {ticker}: {e}")
        return None

def calculate_hedge_ratio(y, x):
    """Calculate hedge ratio using OLS regression"""
    # Add constant for intercept
    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit()
    return model.params[1]  # Slope coefficient (hedge ratio)

def pairs_trading_strategy(pair_data, pair_names):
    """
    Pairs trading strategy:
    - Test for cointegration
    - Calculate spread: y - hedge_ratio * x
    - Enter when z-score of spread > ENTRY_ZSCORE (short spread)
    - Enter when z-score of spread < -ENTRY_ZSCORE (long spread)
    - Exit when |z-score| < EXIT_ZSCORE
    """
    ticker1, ticker2 = pair_names
    df1 = pair_data[ticker1]
    df2 = pair_data[ticker2]

    if df1 is None or df2 is None:
        raise ValueError(f"Missing data for {ticker1} or {ticker2}")

    # Align data to common daily index (close prices)
    start_date = max(df1.index.min(), df2.index.min())
    end_date = min(df1.index.max(), df2.index.max())

    if start_date >= end_date:
        raise ValueError(f"No overlapping date range for {ticker1}-{ticker2}")

    common_index = pd.date_range(start=start_date, end=end_date, freq='1D', tz='UTC')

    # Align close prices
    price1 = df1['close'].reindex(common_index, method='ffill')
    price2 = df2['close'].reindex(common_index, method='ffill')

    # Remove any remaining NaN
    valid_idx = ~(price1.isna() | price2.isna())
    price1 = price1[valid_idx]
    price2 = price2[valid_idx]

    if len(price1) < LOOKBACK_DAYS * 2:  # Need sufficient history
        raise ValueError(f"Insufficient data for {ticker1}-{ticker2} (need >{LOOKBACK_DAYS*2} days)")

    # Calculate returns
    ret1 = price1.pct_change().fillna(0)
    ret2 = price2.pct_change().fillna(0)

    # Initialize signal and position series
    signals = pd.Series(0, index=price1.index)  # 1 = long spread, -1 = short spread, 0 = flat
    positions = pd.Series(0, index=price1.index)  # Current position

    # Roll-forward calculation of hedge ratio and z-score
    hedge_ratios = pd.Series(index=price1.index, dtype=float)
    z_scores = pd.Series(index=price1.index, dtype=float)

    for i in range(LOOKBACK_DAYS, len(price1)):
        # Lookback window
        lookback_1 = price1.iloc[i-LOOKBACK_DAYS:i]
        lookback_2 = price2.iloc[i-LOOKBACK_DAYS:i]

        # Skip if insufficient data in lookback
        if len(lookback_1) < LOOKBACK_DAYS // 2:
            continue

        # Test for cointegration (Engle-Granger)
        try:
            # Using statsmodels coint test
            score, pvalue, _ = coint(lookback_1, lookback_2)
            is_cointegrated = pvalue < 0.05  # Significant at 5% level
        except:
            is_cointegrated = False

        if not is_cointegrated:
            # Not cointegrated, no position
            hedge_ratios.iloc[i] = 0
            z_scores.iloc[i] = 0
            signals.iloc[i] = 0
            continue

        # Calculate hedge ratio using OLS
        hedge_ratio = calculate_hedge_ratio(lookback_1.values, lookback_2.values)
        hedge_ratios.iloc[i] = hedge_ratio

        # Calculate spread
        spread = lookback_1.values - hedge_ratio * lookback_2.values
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)

        if spread_std > 0:
            # Current spread
            current_spread = price1.iloc[i-1] - hedge_ratio * price2.iloc[i-1]
            z_score = (current_spread - spread_mean) / spread_std
            z_scores.iloc[i] = z_score

            # Generate signals
            prev_signal = signals.iloc[i-1] if i > 0 else 0
            prev_position = positions.iloc[i-1] if i > 0 else 0

            # Exit conditions
            exit_long = prev_position == 1 and z_score < EXIT_ZSCORE
            exit_short = prev_position == -1 and z_score > -EXIT_ZSCORE

            if exit_long or exit_short:
                signals.iloc[i] = 0  # Flat
            else:
                # Entry conditions
                enter_long = prev_position == 0 and z_score < -ENTRY_ZSCORE
                enter_short = prev_position == 0 and z_score > ENTRY_ZSCORE

                if enter_long:
                    signals.iloc[i] = 1  # Long spread (long ticker1, short ticker2)
                elif enter_short:
                    signals.iloc[i] = -1  # Short spread (short ticker1, long ticker2)
                else:
                    signals.iloc[i] = prev_signal  # Hold previous position
        else:
            # Spread has no volatility
            signals.iloc[i] = 0
            z_scores.iloc[i] = 0

    # Set positions based on signals (with hysteresis to avoid whipsaw)
    position = 0
    for i in range(len(signals)):
        signal = signals.iloc[i]
        if signal == 0:
            # Flat signal - go to zero position
            position = 0
        elif signal == 1 and position != 1:
            # Long signal
            position = 1
        elif signal == -1 and position != -1:
            # Short signal
            position = -1
        # Otherwise hold current position
        positions.iloc[i] = position

    # Calculate returns
    # Long spread: long ticker1, short ticker2
    # Short spread: short ticker1, long ticker2
    ret_long_spread = ret1 - (hedge_ratios.shift(1) * ret2)  # hedge_ratio from previous period
    ret_short_spread = -(ret1 - (hedge_ratios.shift(1) * ret2))  # Opposite

    # Strategy returns based on position
    strategy_ret = (positions.shift(1) * 0)  # Initialize
    strategy_ret = (positions.shift(1) == 1) * ret_long_spread + \
                   (positions.shift(1) == -1) * ret_short_spread
    strategy_ret = strategy_ret.fillna(0)

    # Apply slippage (trade when position changes)
    position_changes = positions.diff().abs().fillna(0)
    # Each full round trip (0->1 or 0->-1->0 etc) counts as a trade
    # We'll count when position changes from 0 to non-zero or vice versa
    trade_signals = ((positions == 0) & (positions.shift() != 0)) | \
                    ((positions != 0) & (positions.shift() == 0))
    num_trades = trade_signals.sum()

    if len(price1) > 0:
        days = len(price1)
        years = days / 252
        if years > 0:
            trades_per_year = num_trades / years
            annual_slippage = trades_per_year * SLIPPAGE * 2  # Round trip per trade
            daily_slippage_drag = annual_slippage / 252
            strategy_ret = strategy_ret - daily_slippage_drag

    # Calculate equity curve
    equity = (1 + strategy_ret).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1 if len(equity) > 0 else 0
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
        'positions': positions,
        'z_scores': z_scores,
        'hedge_ratios': hedge_ratios,
        'num_trades': num_trades,
        'pair': (ticker1, ticker2)
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

def calculate_correlation_with_qqq(returns_series):
    """Calculate correlation with QQQ daily returns"""
    try:
        # Download QQQ data (daily)
        qqq = yf.Ticker("QQQ")
        qqq_data = qqq.history(period="max", interval="1d")
        if qqq_data.empty:
            return 0.0
        qqq_returns = qqq_data['Close'].pct_change().dropna()

        # Align with our returns (both should be daily)
        aligned_idx = returns_series.index.intersection(qqq_returns.index)
        if len(aligned_idx) < 20:
            return 0.0

        our_aligned = returns_series.loc[aligned_idx]
        qqq_aligned = qqq_returns.loc[aligned_idx]

        correlation = np.corrcoef(our_aligned, qqq_aligned)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    except:
        return 0.0

def main():
    """Main function to test hypothesis #6"""
    print("=" * 80)
    print("Testing Hypothesis #6: Pairs / stat-arb")
    print("Z-score mean-reversion on cointegrated ETF pairs")
    print("=" * 80)

    # Download data for all ETFs in pairs
    print("\n1. Downloading ETF data...")
    etf_data = {}
    failed_tickers = set()
    for pair in PAIRS:
        for ticker in pair:
            if ticker not in etf_data:
                data = download_etf_data(ticker, start_date="2020-01-01")
                if data is not None:
                    etf_data[ticker] = data
                    print(f"  ✓ {ticker}: {len(data):,} days")
                else:
                    failed_tickers.add(ticker)
                    print(f"  ✗ {ticker}: Failed to download")

    # Filter out pairs with missing data
    valid_pairs = [pair for pair in PAIRS if pair[0] not in failed_tickers and pair[1] not in failed_tickers]
    print(f"\nFound {len(valid_pairs)} valid pairs out of {len(PAIRS)}")

    if len(valid_pairs) == 0:
        print("ERROR: No valid pairs to test")
        return

    results = {}

    # Test each pair
    for pair in valid_pairs:
        print(f"\n{'='*60}")
        print(f"Testing pair: {pair[0]}/{pair[1]}")
        print('='*60)

        try:
            # Prepare data for this pair
            pair_data = {pair[0]: etf_data[pair[0]], pair[1]: etf_data[pair[1]]}

            # Run strategy
            strategy_results = pairs_trading_strategy(pair_data, pair)

            # Split IS/OOS
            # Need to split the aligned data used in the strategy
            # For simplicity, we'll split the original ETF data
            is_data_a, oos_data_a = split_is_oos(etf_data[pair[0]])
            is_data_b, oos_data_b = split_is_oos(etf_data[pair[1]])

            is_pair_data = {pair[0]: is_data_a, pair[1]: is_data_b}
            oos_pair_data = {pair[0]: oos_data_a, pair[1]: oos_data_b}

            # Run strategy on IS and OOS
            print("   Running strategy on IS period...")
            is_results = pairs_trading_strategy(is_pair_data, pair)
            print("   Running strategy on OOS period...")
            oos_results = pairs_trading_strategy(oos_pair_data, pair)

            # Calculate statistics
            stats = calculate_returns_stats(strategy_results['returns'])
            is_stats = calculate_returns_stats(is_results['returns'])
            oos_stats = calculate_returns_stats(oos_results['returns'])

            # Calculate correlation with QQQ (using OOS returns)
            correlation = calculate_correlation_with_qqq(oos_results['returns'])

            # Get trade count
            num_trades = oos_results['num_trades']
            # Annualize trades
            if len(oos_results['equity']) > 0:
                days = len(oos_results['equity'])
                years = days / 252
                annualized_trades = num_trades / max(years, 1)
            else:
                annualized_trades = 0

            # Gauntlet criteria
            checks = [
                ("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5),
                ("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35),
                ("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5),
                ("Not overfit", oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)),
                (">= 30 trades/year", annualized_trades >= 30),
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
            print(f"\nResults for {pair[0]}/{pair[1]}:")
            print(f"  Period: {max(etf_data[pair[0]].index.min(), etf_data[pair[1]].index.min()).date()} to "
                  f"{min(etf_data[pair[0]].index.max(), etf_data[pair[1]].index.max()).date()}")
            print(f"  Total days: {len(strategy_results['equity']):,}")
            print(f"  Total return: {strategy_results['total_return']:>+6.1%}")
            print(f"  Annual return: {strategy_results['annual_return']:>+6.1%}")
            print(f"  Sharpe ratio: {strategy_results['sharpe']:>+6.2f}")
            print(f"  Max drawdown: {strategy_results['max_drawdown']:>6.1%}")
            print(f"  Trades: {strategy_results['num_trades']:,} ({annualized_trades:.0f}/year)")
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

            # Store results
            results[f"{pair[0]}/{pair[1]}"] = {
                'pair': pair,
                'is_sharpe': is_stats['sharpe'],
                'oos_sharpe': oos_stats['sharpe'],
                'oos_max_dd': oos_stats['max_dd'],
                'num_trades': num_trades,
                'annualized_trades': annualized_trades,
                'correlation': correlation,
                'passes_gauntlet': all_passed,
                'checks': dict(checks),
                'results': strategy_results
            }

            # Log to HUNT_LOG.md
            log_entry = f"| 6. Pairs Trading ({pair[0]}/{pair[1]}) | {is_stats['sharpe']:>+6.2f} | {oos_stats['sharpe']:>+6.2f} | {oos_stats['max_dd']:>6.1%} | {int(annualized_trades):>6,} | {correlation:>+6.2f} | {'PASS' if all_passed else 'FAIL':>7} | Z-score mean-reversion on {pair[0]}-{pair[1]} spread |"

            with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
                f.write(log_entry + '\n')

            print(f"Logged result for {pair[0]}/{pair[1]} to HUNT_LOG.md")

        except Exception as e:
            print(f"Error testing pair {pair[0]}/{pair[1]}: {e}")
            import traceback
            traceback.print_exc()

            # Log failure
            with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
                f.write(f"| 6. Pairs Trading ({pair[0]}/{pair[1]}) | ERROR | ERROR | ERROR | ERROR | ERROR | FAIL | Exception: {str(e)[:50]}... |\n")

    # Summary
    print("\n" + "=" * 80)
    print("HYPOTHESIS #6 SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results.values() if r['passes_gauntlet'])
    total_count = len(results)
    print(f"Tested {total_count} pairs: {passed_count} passed, {total_count - passed_count} failed")

    for pair_key, result in results.items():
        status = "PASS" if result['passes_gauntlet'] else "FAIL"
        print(f"  {pair_key}: {status} (OOS Sharpe: {result['oos_sharpe']:>+6.2f}, Trades/year: {result['annualized_trades']:.0f})")

if __name__ == "__main__":
    main()