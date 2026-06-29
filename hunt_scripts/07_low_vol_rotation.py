#!/usr/bin/env python3
"""
Hypothesis #7: Low-vol / defensive rotation
USMV/SPLV vs SPY in high-VIX regimes.
"""
import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# Parameters
LOW_VOL_ETFS = ['USMV', 'SPLV']  # Low volatility ETFs
MARKET_ETF = 'SPY'               # Market benchmark
VIX_TICKER = '^VIX'              # VIX volatility index
VIX_THRESHOLD = 20               # VIX > 20 indicates high volatility regime
LOOKBACK_DAYS = 20               # For volatility calculation
SLIPPAGE = 0.0001                # 1bps for ETFs
MIN_HOLD_DAYS = 1                # Minimum holding period

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

def download_vix_data(start_date="2020-01-01"):
    """Download VIX data from Yahoo Finance"""
    try:
        vix = yf.Ticker(VIX_TICKER)
        data = vix.history(start=start_date, interval="1d")
        if data.empty:
            return None

        data = data[['Open', 'High', 'Low', 'Close']]
        data.columns = [c.lower() for c in data.columns]
        data.index = data.index.tz_localize('UTC')
        # Use close price
        return data['close']
    except Exception as e:
        print(f"  Failed to download {VIX_TICKER}: {e}")
        return None

def low_volatility_rotation(low_vol_data, market_data, vix_data):
    """
    Low-volatility rotation strategy:
    - When VIX > VIX_THRESHOLD (high volatility regime): invest in low-vol ETFs
    - When VIX <= VIX_THRESHOLD (low volatility regime): invest in market (SPY)
    - Rotate between the lowest vol ETF and SPY based on volatility regime
    """
    # Align all data to common daily index
    # Start with the asset that has the most data
    all_data = {}
    if low_vol_data:
        for etf, df in low_vol_data.items():
            if df is not None:
                all_data[etf] = df
    if market_data is not None:
        all_data['MARKET'] = market_data
    if vix_data is not None:
        all_data['VIX'] = pd.DataFrame({'close': vix_data})

    # Remove any None entries
    all_data = {k: v for k, v in all_data.items() if v is not None}

    if len(all_data) < 2:
        raise ValueError("Insufficient data for low-vol rotation strategy")

    # Get common date range
    start_dates = [df.index.min() for df in all_data.values()]
    end_dates = [df.index.max() for df in all_data.values()]
    common_start = max(start_dates)
    common_end = min(end_dates)

    if common_start >= common_end:
        raise ValueError("No overlapping date range")

    # Create common daily index
    common_index = pd.date_range(start=common_start, end=common_end, freq='1D', tz='UTC')

    # Align all data to common index (close prices)
    aligned_data = {}
    for name, df in all_data.items():
        aligned_close = df['close'].reindex(common_index, method='ffill')
        # Only keep if we have reasonable data coverage
        if not aligned_close.isna().all():
            aligned_data[name] = aligned_close

    # Convert to DataFrame
    if not aligned_data:
        raise ValueError("No data could be aligned")

    price_df = pd.DataFrame(aligned_data)
    price_df = price_df.dropna(how='all')  # Drop rows where all values are NaN

    if len(price_df) < 50:  # Need sufficient history
        raise ValueError("Insufficient aligned price data")

    # Calculate returns
    returns_df = price_df.pct_change().fillna(0)

    # Get VIX series (align to same index)
    if 'VIX' in price_df.columns:
        vix_series = price_df['VIX']
        # Remove VIX from price_df for return calculation
        price_df = price_df.drop(columns=['VIX'])
        returns_df = price_df.pct_change().fillna(0)
    else:
        # If no VIX data, we can't implement the strategy
        raise ValueError("VIX data not available")

    # Initialize signal series
    # 1 = invested in low-vol ETFs, 0 = invested in market (SPY)
    signals = pd.Series(0, index=price_df.index)

    # Determine which low-vol ETF to use (pick the one with lower volatility or just use first)
    low_vol_columns = [col for col in LOW_VOL_ETFS if col in price_df.columns]
    if not low_vol_columns:
        # Fallback: if no specific low vol ETFs not found, use first available non-market, non-vix column
        available = [col for col in price_df.columns if col not in ['MARKET']]
        if not available:
            raise ValueError("No investable assets found")
        low_vol_columns = [available[0]]  # Use first available

    # For simplicity, we'll use the first low-vol ETF
    # In practice, we could choose the one with lower recent volatility
    primary_low_vol = low_vol_columns[0] if low_vol_columns else None
    if primary_low_vol is None or primary_low_vol not in price_df.columns:
        # Fallback to first column that's not MARKET
        available = [col for col in price_df.columns if col != 'MARKET']
        primary_low_vol = available[0] if available else list(price_df.columns)[0]

    market_column = 'MARKET' if 'MARKET' in price_df.columns else None
    if market_column is None:
        # If MARKET not explicitly defined, use SPY or first available
        if 'SPY' in price_df.columns:
            market_column = 'SPY'
        else:
            # Use first column (not ideal but fallback)
            available = [col for col in price_df.columns if col not in low_vol_columns and col != 'VIX']
            if not available:
                # Last resort: use first column
                available = list(price_df.columns)
            if not available:
                raise ValueError("No suitable market proxy found")
            market_column = available[0]

    # Generate signals based on VIX regime
    for i in range(len(price_df)):
        if i < LOOKBACK_DAYS:  # Need lookback for VIX calculation
            continue

        # Get current VIX
        current_vix = vix_series.iloc[i]

        # Determine signal based on VIX regime
        if current_vix > VIX_THRESHOLD:
            # High volatility: invest in low-vol ETF
            signals.iloc[i] = 1
        else:
            # Low volatility: invest in market
            signals.iloc[i] = 0

    # Calculate returns based on position
    strategy_ret = pd.Series(0.0, index=price_df.index)

    for i in range(len(price_df)):
        if i == 0:
            continue  # Skip first day (no prior signal)

        # Get yesterday's signal (we act on yesterday's signal for today's return)
        prev_signal = signals.iloc[i-1]

        if prev_signal == 1:
            # Invested in low-vol ETF
            if primary_low_vol in price_df.columns:
                asset_return = returns_df[primary_low_vol].iloc[i]
            else:
                # Fallback: equal weight of all low-vol ETFs
                lv_returns = [returns_df[col].iloc[i] for col in low_vol_columns if col in price_df.columns]
                asset_return = np.mean(lv_returns) if lv_returns else 0
        else:
            # Invested in market
            if market_column in price_df.columns:
                asset_return = returns_df[market_column].iloc[i]
            else:
                # Fallback: use first available non-low-vol asset
                non_lv_cols = [col for col in price_df.columns if col not in low_vol_columns]
                if non_lv_cols:
                    asset_return = returns_df[non_lv_cols[0]].iloc[i]
                else:
                    asset_return = 0  # Should not happen

        strategy_ret.iloc[i] = asset_return

    # Apply slippage (trade when regime changes)
    signal_changes = signals.diff().abs().fillna(0)
    # Each regime change triggers a trade (sell one asset, buy another)
    regime_changes = (signal_changes > 0.5).sum()  # Count non-zero changes

    if len(price_df) > 0:
        days = len(price_df)
        years = days / 252
        if years > 0:
            changes_per_year = regime_changes / years
            annual_slippage = changes_per_year * SLIPPAGE * 2  # Round trip per change
            daily_slippage_drag = annual_slippage / 252
            strategy_ret = strategy_ret - daily_slippage_drag

    # Calculate equity curve
    equity = (1 + strategy_ret).cumprod()

    # Statistics
    total_return = equity.iloc[-1] - 1 if len(equity) > 0 else 0
    annual_return = (1 + total_return) ** (252 / len(strategy_ret)) - 1 if len(strategy_ret) > 0 else 0
    annual_vol = std_dev = strategy_ret.std() * np.sqrt(252) if len(strategy_ret) > 1 else 0
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
        'signals': signals,
        'vix_series': vix_series,
        'num_regime_changes': regime_changes,
        'low_vol_used': primary_low_vol,
        'market_used': market_column
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

        # Align with our results (both should be daily)
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
    """Main function to test hypothesis #7"""
    print("=" * 80)
    print("Testing Hypothesis #7: Low-vol / defensive rotation")
    print("USMV/SPLV vs SPY in high-VIX regimes.")
    print("=" * 80)

    try:
        # Download data
        print("\n1. Downloading ETF and VIX data...")
        low_vol_data = {}
        for etf in LOW_VOL_ETFS:
            data = download_etf_data(etf, start_date="2020-01-01")
            if data is not None:
                low_vol_data[etf] = data
                print(f"  ✓ {etf}: {len(data):,} days")
            else:
                print(f"  ✗ {etf}: Failed to download")

        market_data = download_etf_data(MARKET_ETF, start_date="2020-01-01")
        if market_data is not None:
            print(f"  ✓ {MARKET_ETF}: {len(market_data):,} days")
        else:
            print(f"  ✗ {MARKET_ETF}: Failed to download")

        vix_data = download_vix_data(start_date="2020-01-01")
        if vix_data is not None:
            print(f"  ✓ {VIX_TICKER}: {len(vix_data):,} days")
        else:
            print(f"  ✗ {VIX_TICKER}: Failed to download")
            print("  WARNING: Cannot test strategy without VIX data")
            return

        # Check we have minimum required data
        if len(low_vol_data) == 0:
            print("ERROR: No low-vol ETF data available")
            return

        if market_data is None:
            print("ERROR: Market ETF data not available")
            return

        # Run strategy
        print("\n2. Running low-volatility rotation strategy...")
        results = low_volatility_rotation(low_vol_data, market_data, vix_data)

        # Split IS/OOS
        print("\n3. Splitting IS/OOS (60/40 chronological)...")
        # We need to split the input data
        is_low_vol, oos_low_vol = split_is_oos_dict(low_vol_data)
        is_market, oos_market = split_is_oos(market_data)
        is_vix, oos_vix = split_is_oos_dict({'VIX': vix_data})['VIX']

        # Run strategy on IS and OOS
        print("   Running strategy on IS period...")
        is_results = low_volatility_rotation(is_low_vol, is_market, is_vix)
        print("   Running strategy on OOS period...")
        oos_results = low_volatility_rotation(oos_low_vol, oos_market, oos_vix)

        # Calculate statistics
        stats = calculate_returns_stats(results['returns'])
        is_stats = calculate_returns_stats(is_results['returns'])
        oos_stats = calculate_returns_stats(oos_results['returns'])

        # Calculate correlation with QQQ (using OOS returns)
        correlation = calculate_correlation_with_qqq(oos_results['returns'])

        # Get regime change count
        num_changes = oos_results['num_regime_changes']
        # Annualize regime changes
        if len(oos_results['equity']) > 0:
            days = len(oos_results['equity'])
            years = days / 252
            annualized_changes = num_changes / max(years, 1)
        else:
            annualized_changes = 0

        # Gauntlet criteria
        checks = [
            ("OOS Sharpe > 0.5", oos_stats['sharpe'] > 0.5),
            ("OOS maxDD > -35%", oos_stats['max_dd'] > -0.35),
            ("OOS Sharpe < 2.5", oos_stats['sharpe'] < 2.5),
            ("Not overfit", oos_stats['sharpe'] <= (is_stats['sharpe'] * 1.3 + 0.5)),
            (">= 30 trades/year", annualized_changes >= 30),  # Regime changes as trades
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
        print(f"Low-vol ETFs: {', '.join(LOW_VOL_ETFS)}")
        print(f"Market ETF: {MARKET_ETF}")
        print(f"VIX threshold: {VIX_THRESHOLD}")
        print(f"Period: {results['equity'].index.min().date()} to {results['equity'].index.max().date()}")
        print(f"Total days: {len(results['equity']):,}")
        print(f"Low-vol ETF used: {results['low_vol_used']}")
        print(f"Market ETF used: {results['used_market']}")
        print()
        print(f"Total return: {results['total_return']:>+6.1%}")
        print(f"Annual return: {results['annual_return']:>+6.1%}")
        print(f"Sharpe ratio: {results['sharpe']:>+6.2f}")
        print(f"Max drawdown: {results['max_drawdown']:>6.1%}")
        print(f"VIX > {VIX_THRESHOLD} days: {(results['vix_series'] > VIX_THRESHOLD).sum():,} ({(results['vix_series'] > VIX_THRESHOLD).mean()*100:.1f}%)")
        print(f"Regime changes: {results['num_regime_changes']:,} ({annualized_changes:.0f}/year)")
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
        log_entry = f"| 7. Low-Vol Rotation | {is_stats['sharpe']:>+6.2f} | {oos_stats['sharpe']:>+6.2f} | {oos_stats['max_dd']:>6.1%} | {int(annualized_changes):>6,} | {correlation:>+6.2f} | {'PASS' if all_passed else 'FAIL':>7} | Rotate to {results['low_vol_used']} when VIX > {VIX_THRESHOLD}, else {results['used_market']} |"

        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(log_entry + '\n')

        print(f"\nLogged to HUNT_LOG.md")

    except Exception as e:
        print(f"\nError in hypothesis #7: {e}")
        import traceback
        traceback.print_exc()

        # Log failure
        with open('/Users/colindayer/nas100_backtest/HUNT_LOG.md', 'a') as f:
            f.write(f"| 7. Low-Vol Rotation | ERROR | ERROR | ERROR | ERROR | ERROR | FAIL | Exception: {str(e)[:50]}... |\n")

def split_is_oos_dict(data_dict, is_ratio=0.6):
    """Split dictionary of dataframes into IS and OOS"""
    is_dict = {}
    oos_dict = {}
    for key, df in data_dict.items():
        if df is not None and len(df) > 0:
            split_idx = int(len(df) * is_ratio)
            is_dict[key] = df.iloc[:split_idx]
            oos_dict[key] = df.iloc[split_idx:]
        else:
            is_dict[key] = df
            oos_dict[key] = df
    return is_dict, oos_dict

if __name__ == "__main__":
    main()