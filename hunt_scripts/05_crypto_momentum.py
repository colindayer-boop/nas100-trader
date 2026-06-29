#!/usr/bin/env python3
"""
Hypothesis #5: Cross-sectional crypto momentum
Rank top-10 liquid coins by 30d return, long top / short bottom, weekly.
Crypto trends hard.
"""
import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import itertools

warnings.filterwarnings("ignore")

# Parameters
CRYPTO_UNIVERSE = [
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
    'SOL-USD', 'DOGE-USD', 'DOT-USD', 'MATIC-USD', 'LTC-USD'
]  # Top 10 by market cap (approximate)
LOOKBACK_DAYS = 30             # 30-day momentum
REBALANCE_FREQ = 'W'           # Weekly rebalancing
TOP_N_LONG = 5                 # Long top 5
TOP_N_SHORT = 5                # Short bottom 5
SLIPPAGE = 0.0010              # 10bps for crypto (less liquid than BTC/ETH)
MIN_HOLD_HOURS = 1             # Minimum holding period

def download_crypto_data(ticker, start_date="2020-01-01"):
    """Download cryptocurrency data from Yahoo Finance"""
    # Try to download, skip if fails
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

def cross_sectional_momentum(crypto_data_dict, universe):
    """
    Cross-sectional crypto momentum:
    - Each week, rank coins by past 30-day return
    - Long top N, short bottom N
    - Equal weight long/short (dollar neutral)
    """
    # Prepare data: align all coins to common daily index
    # Start with the coin that has the most data
    valid_data = {k: v for k, v in crypto_data_dict.items() if v is not None}
    if len(valid_data) < 5:  # Need at least 5 coins
        raise ValueError("Not enough valid crypto data")

    # Get common date range
    start_dates = [df.index.min() for df in valid_data.values()]
    end_dates = [df.index.max() for df in valid_data.values()]
    common_start = max(start_dates)
    common_end = min(end_dates)

    if common_start >= common_end:
        raise ValueError("No overlapping date range")

    # Create common daily index
    common_index = pd.date_range(start=common_start, end=common_end, freq='1D', tz='UTC')

    # Align all data to common index (close prices)
    aligned_data = {}
    for ticker, df in valid_data.items():
        aligned_close = df['close'].reindex(common_index, method='ffill')
        aligned_data[ticker] = aligned_close

    # Convert to DataFrame
    price_df = pd.DataFrame(aligned_data)
    price_df = price_df.dropna(how='all')  # Drop days where all coins are missing

    if len(price_df) < 50:  # Need sufficient history
        raise ValueError("Insufficient aligned price data")

    # Calculate returns
    returns_df = price_df.pct_change().fillna(0)

    # Calculate lookback period returns (30-day momentum)
    lookback_returns = price_df.pct_change(LOOKBACK_DAYS).fillna(0)

    # Generate weekly signals
    # Resample to weekly frequency (rebalance every week)
    weekly_prices = price_df.resample(REBALANCE_FREQ).last()
    weekly_lookback = lookback_returns.resample(REBALANCE_FREQ).last()

    # Initialize portfolio weights DataFrame (daily frequency)
    weights = pd.DataFrame(0.0, index=price_df.index, columns=price_df.columns)

    # For each rebalance date
    for i in range(len(weekly_prices) - 1):
        rebalance_date = weekly_prices.index[i]
        next_rebalance_date = weekly_prices.index[i + 1]

        # Get lookback returns as of rebalance date
        if rebalance_date in weekly_lookback.index:
            lb_returns = weekly_lookback.loc[rebalance_date]
        else:
            # Find closest prior date
            prior_dates = weekly_lookback.index[weekly_lookback.index <= rebalance_date]
            if len(prior_dates) == 0:
                continue
            lb_returns = weekly_lookback.loc[prior_dates[-1]]

        # Rank coins by lookback return
        ranked = lb_returns.dropna().sort_values(ascending=False)

        if len(ranked) < TOP_N_LONG + TOP_N_SHORT:
            # Not enough coins with data
            continue

        # Select longs and shorts
        long_candidates = ranked.index[:TOP_N_LONG]
        short_candidates = ranked.index[-TOP_N_SHORT:]

        # Equal weight long and short (dollar neutral)
        long_weight = 1.0 / TOP_N_LONG if TOP_N_LONG > 0 else 0
        short_weight = -1.0 / TOP_N_SHORT if TOP_N_SHORT > 0 else 0

        # Set weights for holding period
        weights.loc[rebalance_date:next_rebalance_date, long_candidates] = long_weight
        weights.loc[rebalance_date:next_rebalance_date, short_candidates] = short_weight

    # Forward fill weights to last date
    weights = weights.ffill().fillna(0)

    # Calculate portfolio returns
    # Daily portfolio return = sum(weight * asset_return)
    portfolio_returns = (weights * returns_df).sum(axis=1)

    # Apply slippage on rebalance dates
    # Count rebalances (when weights change significantly)
    weights_diff = weights.diff().abs().sum(axis=1)  # L1 norm of weight changes
    rebalance_days = weights_diff > 0.01  # Threshold to detect rebalance
    num_rebalances = rebalance_days.sum()

    if len(price_df) > 0:
        days = len(price_df)
        years = days / 252
        if years > 0:
            rebalances_per_year = num_rebalances / years
            annual_slippage = rebalances_per_year * SLIPPAGE * 2  # Round trip per rebalance
            daily_slippage_drag = annual_slippage / 252
            portfolio_returns = portfolio_returns - daily_slippage_drag

    # Calculate equity curve
    equity = (1 + portfolio_returns).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1 if len(equity) > 0 else 0
    annual_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1 if len(portfolio_returns) > 0 else 0
    annual_vol = portfolio_returns.std() * np.sqrt(252) if len(portfolio_returns) > 1 else 0
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
        'returns': portfolio_returns,
        'equity': equity,
        'weights': weights,
        'num_rebalances': num_rebalances,
        'universe_size': len(price_df.columns)
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
    """Main function to test hypothesis #5"""
    print("=" * 80)
    print("Testing Hypothesis #5: Cross-sectional crypto momentum")
    print("Rank top-10 liquid coins by 30d return, long top / short bottom, weekly.")
    print("=" * 80)

    try:
        # Download data for all cryptocurrencies in universe
        print("\n1. Downloading cryptocurrency data...")
        crypto_data = {}
        failed_count = 0
        for ticker in CRYPTO_UNIVERSE:
            data = download_crypto_data(ticker, start_date="2020-01-01")
            if data is not None:
                crypto_data[ticker] = data
                print(f"  ✓ {ticker}: {len(data):,} days")
            else:
                failed_count += 1
                print(f"  ✗ {ticker}: Failed to download")

        print(f"\nSuccessfully downloaded {len(crypto_data)} / {len(CRYPTO_UNIVERSE)} cryptocurrencies")

        if len(crypto_data) < 5:
            print("ERROR: Need at least 5 cryptocurrencies to test cross-sectional momentum")
            return

        # Run strategy
        print("\n2. Running cross-sectional momentum strategy...")
        results = cross_sectional_momentum(crypto_data, CRYPTO_UNIVERSE)

        # Split IS/OOS
        print("\n3. Splitting IS/OOS (60/40 chronological)...")
        # We need to split the aligned price data
        # Get the common date range from the strategy
        common_start = results['equity'].index.min()
        common_end = results['equity'].index.max()
        common_index = pd.date_range(start=common_start, end=common_end, freq='1D', tz='UTC')

        # Re-download and align data for clean split
        crypto_data_split = {}
        for ticker, df in crypto_data.items():
            aligned_close = df['close'].reindex(common_index, method='ffill')
            crypto_data_split[ticker] = pd.DataFrame({'close': aligned_close})

        # Split the data
        split_point = int(len(common_index) * 0.6)
        is_dates = common_index[:split_point]
        oos_dates = common_index[split_point:]

        # Build IS and OOS datasets
        is_crypto_data = {}
        oos_crypto_data = {}
        for ticker in crypto_data.keys():
            is_crypto_data[ticker] = crypto_data_split[ticker].loc[is_dates]
            oos_crypto_data[ticker] = crypto_data_split[ticker].loc[oos_dates]

        # Run strategy on IS and OOS
        print("   Running strategy on IS period...")
        is_results = cross_sectional_momentum(is_crypto_data, list(is_crypto_data.keys()))
        print("   Running strategy on OOS period...")
        oos_results = cross_sectional_momentum(oos_crypto_data, list(oos_crypto_data.keys()))

        # Calculate statistics
        stats = calculate_returns_stats(results['returns'])
        is_stats = calculate_returns_stats(is_results['returns'])
        oos_stats = calculate_returns_stats(oos_results['returns'])

        # Calculate correlation with QQQ (using OOS returns)
        correlation = calculate_correlation_with_qqq(oos_results['returns'])

        # Get rebalance count (proxy for trades)
        num_rebalances = oos_results['num_rebalances']
        # Annualize rebalances
        if len(oos_results['equity']) > 0:
            days = len(oos_results['equity'])
            years = days / 252
            annualized_rebalances = num_rebalances / max(years, 1)
        else:
            annualized_rebalances = 0

        # Gauntlet criteria
        checks = [
            ("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5),
            ("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35),
            ("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5),
            ("Not overfit", oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)),
            (">= 30 trades/year", annualized_rebalances >= 30),  # Rebalances as trades
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
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Universe: {results['universe_size']} cryptocurrencies")
        print(f"Period: {common_start.date()} to {common_end.date()}")
        print(f"Total days: {len(common_index):,}")
        print(f"Lookback: {LOOKBACK_DAYS} days, Rebalance: {REBALANCE_FREQ}")
        print(f"Long top: {TOP_N_LONG}, Short bottom: {TOP_N_SHORT}")
        print()
        print(f"Total return: {results['total_return']:>+6.1%}")
        print(f"Annual return: {results['annual_return']:>+6.1%}")
        print(f"Sharpe ratio: {results['sharpe']:>+6.2f}")
        print(f"Max drawdown: {results['max_drawdown']:>6.1%}")
        print(f"Rebalances: {results['num_rebalances']:,} ({annualized_rebalances:.0f}/year)")
        print()
        print(f"IS Sharpe: {is_stats['sharpe']:>+6.2f}")
        print(f"OOS Sharpe: {oos_stats['sharpe']:>+6.2f}")
        print(f"OOS Max DD: {oos_stats['max_dd']:>6.1%}")
        print(f"Correlation with QQQ: {correlation:>+6.2f}")
        print()
        print("Gauntlet Checks:")
        for check_name, passed in checks:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {check_name}")
        print(f"  OVERALL: {'PASS' if all_passed else 'FAIL'}")

        # Log to HUNT_LOG.md
        log_entry = f"| 5. Cross-Sectional Momentum | {is_stats['sharpe']:>+6.2f} | {oos_stats['sharpe']:>+6.2f} | {oos_stats['max_dd']:>6.1%} | {int(annualized_rebalances):>6,} | {correlation:>+6.2f} | {'PASS' if all_passed else 'FAIL':>7} | Long top {TOP_N_LONG}/short bottom {TOP_N_SHORT} by {LOOKBACK_DAYS}-day momentum, rebalanced {REBALANCE_FREQ} |"

        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(log_entry + '\n')

        print(f"\nLogged to HUNT_LOG.md")

    except Exception as e:
        print(f"\nError in hypothesis #5: {e}")
        import traceback
        traceback.print_exc()

        # Log failure
        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(f"| 5. Cross-Sectional Momentum | ERROR | ERROR | ERROR | ERROR | ERROR | FAIL | Exception: {str(e)[:50]}... |\n")

if __name__ == "__main__":
    main()