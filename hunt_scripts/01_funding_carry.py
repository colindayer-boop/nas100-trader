#!/usr/bin/env python3
"""
Hypothesis #1: Crypto perp funding-rate carry
Long spot / short perp when funding is persistently positive, collect funding.
"""
import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# Parameters
FUNDING_THRESHOLD = 0.0002  # 0.02% per 8h funding to consider "persistently positive"
PERSISTENCE_HOURS = 8       # Require funding to be positive for this many consecutive hours
REBALANCE_HOURS = 1         # How often to check/rebalance
SLIPPAGE = 0.0004           # 4bps round-trip (taker fee + slippage)
RISK_PER_TRADE = 0.01       # 1% risk per trade (for position sizing)

# Directories
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunt_scripts")

def download_btc_spot(start_date="2020-01-01"):
    """Download BTC spot price data from Yahoo Finance"""
    print("Downloading BTC spot data (BTC-USD)...")
    ticker = yf.Ticker("BTC-USD")
    # Get hourly data
    data = ticker.history(start=start_date, interval="1h")
    if data.empty:
        # Try downloading daily and resample
        data = ticker.history(start=start_date, interval="1d")
        data = data.resample('1h').ffill()
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.columns = [c.lower() for c in data.columns]
    data.index = data.index.tz_localize('UTC')
    print(f"  Downloaded {len(data):,} hourly spot bars")
    return data

def load_perp_data(years):
    """Load BTC perpetual data from parquet files"""
    frames = []
    for y in years:
        p = os.path.join(DATA_DIR, f"btcusdt_perp_1m_{y}.parquet")
        if os.path.exists(p):
            df = pd.read_parquet(p)
            # Resample to hourly
            df_h = df.resample("1h").agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna(subset=['open'])
            frames.append(df_h)
    if not frames:
        raise FileNotFoundError("No perpetual data found")
    h = pd.concat(frames).sort_index()
    h = h[~h.index.duplicated(keep='first')]
    h.columns = [c.lower() for c in h.columns]
    return h

def load_funding_rate():
    """Load funding rate data"""
    path = os.path.join(DATA_DIR, "btcusdt_funding.parquet")
    if os.path.exists(path):
        df = pd.read_parquet(path)
        # Funding rate is already in decimal (e.g., 0.0001 = 0.01%)
        if isinstance(df, pd.DataFrame):
            funding = df.iloc[:, 0]  # Take first column if DataFrame
        else:
            funding = df.squeeze()
        funding.index = funding.index.tz_localize('UTC')
        return funding
    else:
        raise FileNotFoundError("Funding rate data not found. Run btc_funding_reversal.py first")

def align_data(spot, perp, funding):
    """Align spot, perp, and funding data to common hourly index"""
    # Start with the intersection of all three
    start_idx = max(spot.index.min(), perp.index.min(), funding.index.min())
    end_idx = min(spot.index.max(), perp.index.max(), funding.index.max())

    # Create common hourly index
    common_index = pd.date_range(start=start_idx, end=end_idx, freq='1h', tz='UTC')

    # Align each dataset
    spot_aligned = spot.reindex(common_index, method='ffill')
    perp_aligned = perp.reindex(common_index, method='ffill')
    funding_aligned = funding.reindex(common_index, method='ffill')

    # Drop any rows where data is missing
    valid_idx = (~spot_aligned.isna().any(axis=1)) & \
                (~perp_aligned.isna().any(axis=1)) & \
                (~funding_aligned.isna())

    spot_aligned = spot_aligned[valid_idx]
    perp_aligned = perp_aligned[valid_idx]
    funding_aligned = funding_aligned[valid_idx]

    print(f"Aligned data: {len(spot_aligned):,} hourly bars from {spot_aligned.index.min()} to {spot_aligned.index.max()}")

    return spot_aligned, perp_aligned, funding_aligned

def calculate_persistence(funding_series, threshold, lookback_hours):
    """Calculate when funding has been persistently above/below threshold"""
    # Convert to boolean: True if funding > threshold
    above_threshold = funding_series > threshold
    # Rolling sum of consecutive hours above threshold
    # We need to count consecutive True values
    persistence = above_threshold.rolling(
        window=lookback_hours,
        min_periods=lookback_hours
    ).sum() == lookback_hours
    return persistence

def run_funding_carry(spot, perp, funding,
                      funding_threshold=FUNDING_THRESHOLD,
                      persistence_hours=PERSISTENCE_HOURS):
    """Run the funding carry strategy: long spot/short perp when funding persistently positive"""

    # Calculate persistence signal
    persistently_positive = calculate_persistence(funding, funding_threshold, persistence_hours)

    # We are LONG spot, SHORT perp when signal is True
    # When short perp and funding is positive, we RECEIVE funding (positive P&L)
    # When short perp and funding is negative, we PAY funding (negative P&L)

    # Calculate hourly returns
    spot_ret = spot['close'].pct_change()
    perp_ret = perp['close'].p['close'].pct_change()

    # For delta-neutral position (long spot, short perp):
    # Price return = spot_ret - perp_ret (we profit when spot outperforms perp)
    # Funding return: we receive funding rate when we are short perp
    #   funding is paid every 8 hours, so we need to convert to hourly
    #   funding rate is per 8 hours, so hourly funding = funding_rate / 8

    # Actually, let's think about this more carefully:
    # When we are short perp:
    #   If funding rate > 0: longs pay shorts → we RECEIVE |funding_rate| * position_size
    #   If funding rate < 0: shorts pay longs → we PAY |funding_rate| * position_size
    # So funding P&L = -funding_rate * position_size (since we're short)

    # But funding rate is quoted as the rate that longs pay to shorts
    # So if funding = 0.0002 (0.02%), longs pay 0.02% to shorts every 8 hours
    # Therefore, as shorts, we RECEIVE 0.02% every 8 hours
    # So our funding P&L = +funding_rate (when we are short perp)

    # Convert 8-hour funding rate to hourly equivalent
    hourly_funding = funding / 3  # Approximate: 8 hours ≈ 3 trading hours in crypto? No, 8 hours is 8 hours
    # Actually, funding is paid every 8 hours exactly, so we should account for it at those intervals

    # Simpler approach: calculate P&L at each funding timestamp
    # But for simplicity in backtesting, let's assume we can hedge continuously
    # and accrue funding hourly at rate = funding_rate / 8

    hourly_funding_accrual = funding / 8  # Per hour funding accrual for being short perp

    # Position sizing: we'll use volatility targeting
    # For simplicity, use fixed $10k capital, 100% long spot, 100% short perp (delta neutral)

    capital = 10000.0
    position_size = capital  # $10k long spot, $10k short perp

    # Initialize tracking
    equity = [capital]
    in_position = persistently_positive.iloc[0] if len(persistently_positive) > 0 else False
    cumulative_funding = 0.0

    # Iterate through time
    for i in range(1, len(spot)):
        prev_equity = equity[-1]

        # Calculate price P&L from spot and perp positions
        if in_position:
            # Long spot: profit = spot_ret * position_size
            # Short perp: profit = -perp_ret * position_size (we profit when perp goes down)
            price_pnl = (spot_ret.iloc[i] - perp_ret.iloc[i]) * position_size

            # Funding P&L: we accrue funding hourly when short perp
            funding_pnl = hourly_funding_accrual.iloc[i] * position_size

            # Total gross P&L
            gross_pnl = price_pnl + funding_pnl
        else:
            gross_pnl = 0.0

        # Apply slippage on rebalancing (when position changes)
        if i > 0 and persistently_positive.iloc[i] != persistently_positive.iloc[i-1]:
            # We're changing position - apply slippage on both legs
            slippage_cost = position_size * SLIPPAGE * 2  # Enter/exit spot + enter/exit perp
            gross_pnl -= slippage_cost

        new_equity = prev_equity + gross_pnl
        equity.append(new_equity)

        # Update position for next period
        if i < len(persistently_positive):
            in_position = persistently_positive.iloc[i]

    # Convert equity series to returns
    equity_series = pd.Series(equity, index=spot.index)
    returns = equity_series.pct_change().fillna(0)

    # Calculate statistics
    total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1
    annual_return = (1 + total_return) ** (252 * 6.5 / len(returns)) - 1  # Approx 6.5 hr trading days
    annual_vol = returns.std() * np.sqrt(252 * 6.5)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0

    # Calculate max drawdown
    roll_max = equity_series.cummax()
    drawdown = (equity_series - roll_max) / roll_max
    max_drawdown = drawdown.min()

    # Count trades (position changes)
    position_changes = (persistently_positive != persistently_positive.shift()).fillna(False)
    num_trades = position_changes.sum() // 2  # Each round trip is 2 changes (enter + exit)

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_vol': annual_vol,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'num_trades': num_trades,
        'equity_series': equity_series,
        'returns': returns,
        'persistently_positive': persistently_positive
    }

def split_is_oos(data, is_ratio=0.6):
    """Split data into IS and OOS periods (chronological split)"""
    split_idx = int(len(data) * is_ratio)
    is_data = data.iloc[:split_idx]
    oos_data = data.iloc[split_idx:]
    return is_data, oos_data

def calculate_returns_stats(returns, is_returns=None, oos_returns=None):
    """Calculate return statistics for a returns series"""
    if len(returns) == 0:
        return {'sharpe': 0, 'max_dd': 0, 'periods': 0}

    # Calculate equity curve
    equity = (1 + returns).cumprod()

    # Sharpe ratio (annualized)
    if returns.std() > 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 6.5)  # Approx annual
    else:
        sharpe = 0

    # Max drawdown
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    max_dd = drawdown.min()

    return {
        'sharpe': sharpe,
        'max_dd': max_dd,
        'periods': len(returns)
    }

def calculate_correlation_with_qqq(returns_series):
    """Calculate correlation with QQQ weekly returns"""
    try:
        # Download QQQ data
        qqq = yf.Ticker("QQQ")
        qqq_data = qqq.history(period="max", interval="1wk")
        if qqq_data.empty:
            return 0.0
        qqq_returns = qqq_data['Close'].pct_change().dropna()

        # Align with our returns (convert to weekly)
        # Our returns are hourly, need to resample to weekly
        equity = (1 + returns_series).cumprod()
        weekly_equity = equity.resample('W').last()
        weekly_returns = weekly_equity.pct_change().dropna()

        # Align indices
        aligned_idx = weekly_returns.index.intersection(qqq_returns.index)
        if len(aligned_idx) < 10:
            return 0.0

        our_weekly = weekly_returns.loc[aligned_idx]
        qqq_weekly = qqq_returns.loc[aligned_idx]

        correlation = np.corrcoef(our_weekly, qqq_weekly)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    except:
        return 0.0

def run_gauntlet_test(strategy_name, returns, is_returns, oos_returns, qqq_returns=None):
    """Run the full gauntlet of tests"""

    # Calculate IS and OOS stats
    is_stats = calculate_returns_stats(is_returns) if len(is_returns) > 0 else {'sharpe': 0, 'max_dd': 0, 'periods': 0}
    oos_stats = calculate_returns_stats(oos_returns) if len(oos_returns) > 0 else {'sharpe': 0, 'max_dd': 0, 'periods': 0}

    # Calculate correlation with QQQ (using OOS returns for correlation test)
    correlation = calculate_correlation_with_qqq(oos_returns) if len(oos_returns) > 0 else 0.0

    # Gauntlet criteria
    checks = []

    # 1. OOS Sharpe > 0.5
    checks.append(("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5))

    # 2. OOS max drawdown > -35%
    checks.append(("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35))

    # 3. OOS Sharpe < 2.5 (not too high = likely real)
    checks.append(("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5))

    # 4. Not overfit: OOS Sharpe <= IS Sharpe * 1.3 + 0.5
    not_overfit = oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)
    checks.append(("Not overfit", not_overfit))

    # 5. >= 30 trades in OOS (we'll approximate with periods for now)
    # For hourly data, 30 trades is very few, so we'll use a higher bar
    # Actually, let's count actual trades from the strategy
    # We'll need to pass trade count from the strategy function
    checks.append(("Sufficient trades", False))  # Placeholder

    # 6. IS Sharpe > 0 (must work in both periods)
    checks.append(("IS Sharpe > 0", is_stats['sharpe'] > 0))

    # 7. |correlation to QQQ weekly| < 0.3
    checks.append(("|Corr to QQQ| < 0.3", abs(correlation) < 0.3))

    # 8. Regime check: positive in bull AND bear sub-periods
    # We'll simplify: check if OOS Sharpe > 0 in first and second half of OOS
    if len(oos_returns) > 0:
        mid_point = len(oos_returns) // 2
        oos_first_half = oos_returns.iloc[:mid_point]
        oos_second_half = oos_returns.iloc[mid_point:]

        first_half_stats = calculate_returns_stats(oos_first_half)
        second_half_stats = calculate_returns_stats(oos_second_half)

        regime_check = (first_half_stats['sharpe'] > 0) and (second_half_stats['sharpe'] > 0)
    else:
        regime_check = False

    checks.append(("Positive in bull/bear regimes", regime_check))

    # Overall pass/fail
    all_passed = all(check[1] for check in checks)

    return {
        'is_sharpe': is_stats['sharpe'],
        'oos_sharpe': oos_stats['sharpe'],
        'oos_max_dd': oos_stats['max_dd'],
        'num_trades': 0,  # Placeholder - would need to pass from strategy
        'correlation': correlation,
        'passes_gauntlet': all_passed,
        'checks': dict(checks)
    }

def main():
    """Main function to test hypothesis #1"""
    print("=" * 80)
    print("Testing Hypothesis #1: Crypto perp funding-rate carry")
    print("Long spot / short perp when funding is persistently positive, collect funding")
    print("=" * 80)

    try:
        # Download/load data
        print("\n1. Loading data...")
        spot_data = download_btc_spot(start_date="2020-01-01")
        perp_data = load_perp_data(years=[2021, 2022, 2023, 2024])
        funding_data = load_funding_rate()

        # Align data
        print("\n2. Aligning data...")
        spot_aligned, perp_aligned, funding_aligned = align_data(spot_data, perp_data, funding_data)

        # Calculate hourly returns for price series
        spot_returns = spot_aligned['close'].pct_change().fillna(0)
        perp_returns = perp_aligned['close'].pct_change().fillna(0)

        # Run strategy
        print("\n3. Running funding carry strategy...")
        strategy_results = run_funding_carry(
            spot_aligned,
            perp_aligned,
            funding_aligned,
            funding_threshold=FUNDING_THRESHOLD,
            persistence_hours=PERSISTENCE_HOURS
        )

        # Split IS/OOS
        print("\n4. Splitting IS/OOS (60/40 chronological)...")
        is_spot, oos_spot = split_is_oos(spot_aligned)
        is_perp, oos_perp = split_is_oos(perp_aligned)
        is_funding, oos_funding = split_is_oos(funding_aligned)

        # Calculate IS and OOS returns from strategy
        # We need to re-run strategy on IS and OOS separately to avoid look-ahead
        print("   Running strategy on IS period...")
        is_strategy_results = run_funding_carry(
            is_spot, is_perp, is_funding,
            funding_threshold=FUNDING_THRESHOLD,
            persistence_hours=PERSISTENCE_HOURS
        )

        print("   Running strategy on OOS period...")
        oos_strategy_results = run_funding_carry(
            oos_spot, oos_perp, oos_funding,
            funding_threshold=FUNDING_THRESHOLD,
            persistence_hours=PERSISTENCE_HOURS
        )

        # Get returns series
        is_returns = is_strategy_results['returns']
        oos_returns = oos_strategy_results['returns']

        # For trade count, we can approximate from position changes
        # In the OOS period
        oos_persistency = calculate_persistence(oos_funding, FUNDING_THRESHOLD, PERSISTENCE_HOURS)
        position_changes = (oos_persistency != oos_persistency.shift()).fillna(False)
        num_trades_oos = position_changes.sum() // 2  # Round trips

        # Run gauntlet tests
        print("\n5. Running gauntlet tests...")
        gauntlet_results = run_gauntlet_test(
            "Funding Rate Carry",
            strategy_results['returns'],  # Full period returns for reference
            is_returns,
            oos_returns
        )

        # Override trade count with actual count
        gauntlet_results['num_trades'] = int(num_trades_oos)
        gauntlet_results['checks']['Sufficient trades'] = num_trades_oos >= 30
        # Recalculate overall pass
        gauntlet_results['passes_gauntlet'] = all(gauntlet_results['checks'].values())

        # Display results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Period: {spot_aligned.index.min().date()} to {spot_aligned.index.max().date()}")
        print(f"Total bars: {len(spot_aligned):,}")
        print(f"IS period: {is_spot.index.min().date()} to {is_spot.index.max().date()} ({len(is_spot):,} bars)")
        print(f"OOS period: {oos_spot.index.min().date()} to {oos_spot.index.max().date()} ({len(oos_spot):,} bars)")
        print()
        print(f"Strategy: Long spot/short perp when funding > {FUNDING_THRESHOLD*100:.3f}%/8h for {PERSISTENCE_HOURS}+ consecutive hours")
        print()
        print(f"IS Sharpe: {gauntlet_results['is_sharpe']:>+6.2f}")
        print(f"OOS Sharpe: {gauntlet_results['oos_sharpe']:>+6.2f}")
        print(f"OOS Max DD: {gauntlet_results['oos_max_dd']:>6.1%}")
        print(f"OOS Trades: {gauntlet_results['num_trades']:>6,.0f}")
        print(f"Corr to QQQ: {gauntlet_results['correlation']:>+6.2f}")
        print()
        print("Gauntlet Checks:")
        for check_name, passed in gauntlet_results['checks'].items():
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {check_name}")
        print()
        print(f"OVERALL: {'PASS' if gauntlet_results['passes_gauntlet'] else 'FAIL'}")

        # Log to HUNT_LOG.md
        log_entry = f"| 1. Funding Rate Carry | {gauntlet_results['is_sharpe']:>+6.2f} | {gauntlet_results['oos_sharpe']:>+6.2f} | {gauntlet_results['oos_max_dd']:>6.1%} | {gauntlet_results['num_trades']:>6,.0f} | {gauntlet_results['correlation']:>+6.2f} | {'PASS' if gauntlet_results['passes_gauntlet'] else 'FAIL':>7} | Long spot/short perp when funding persistently > {FUNDING_THRESHOLD*100:.2f}%/8h for {PERSISTENCE_HOURS}h |"

        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(log_entry + '\n')

        print(f"\nLogged to HUNT_LOG.md")

        # Save script (already saved)
        print(f"Script saved as: hunt_scripts/01_funding_carry.py")

    except Exception as e:
        print(f"\nError in hypothesis #1 ERROR: {e}")
        import traceback
        traceback.print_exc()

        # Log failure
        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(f"| 1. Funding Rate Carry | ERROR | ERROR | ERROR | ERROR | ERROR | FAIL | Exception: {str(e)[:50]}... |\n")

if __name__ == "__main__":
    main()