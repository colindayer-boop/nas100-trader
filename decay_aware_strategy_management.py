"""
Decay-Aware Strategy Management for nas100-trader
Integrates insights from "Three channels of AI-driven alpha decay" (arXiv:2605.23905)

This script provides:
1. Strategy half-life estimation based on OOS performance decay
2. Decay resistance scoring incorporating crowding sensitivity
3. Adaptive position sizing based on decay estimates
4. Enhanced strategy evaluation with decay-aware checks

Designed to be integrated into existing workflow (live_trader.py, backtesters, etc.)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import yaml
import json
from datetime import datetime, timedelta

class DecayMonitor:
    """
    Monitors and estimates strategy alpha decay using rolling performance metrics.
    Based on the half-life formula: h(φ) = ln(2) / [θ + δ(φ)]
    """

    def __init__(self, half_life_window_months: int = 12):
        """
        Initialize decay monitor.

        Args:
            half_life_window_months: Window for calculating decay trends (months)
        """
        self.half_life_window = half_life_window_months
        self.strategy_metrics = {}  # Stores historical metrics per strategy

    def update_strategy_performance(self, strategy_name: str,
                                  returns: pd.Series,
                                  timestamp: datetime) -> None:
        """
        Update performance history for a strategy.

        Args:
            strategy_name: Identifier for the strategy
            returns: Series of returns (indexed by timestamp)
            timestamp: Current timestamp for this update
        """
        if strategy_name not in self.strategy_metrics:
            self.strategy_metrics[strategy_name] = {
                'returns': [],
                'timestamps': [],
                'rolling_sharpe': [],
                'half_life_estimates': []
            }

        # Store new data
        self.strategy_metrics[strategy_name]['returns'].extend(returns.tolist())
        self.strategy_metrics[strategy_name]['timestamps'].extend([timestamp] * len(returns))

        # Calculate rolling Sharpe (annualized, assuming 252 trading days)
        if len(returns) >= 21:  # At least ~1 month of data
            excess_ret = returns - 0.0001  # Approx risk-free rate
            rolling_mean = excess_ret.rolling(21).mean()
            rolling_std = excess_ret.rolling(21).std()
            rolling_sharpe = np.sqrt(252) * rolling_mean / rolling_std
            # Store last valid value
            valid_sharpe = rolling_sharpe.dropna()
            if len(valid_sharpe) > 0:
                self.strategy_metrics[strategy_name]['rolling_sharpe'].append(valid_sharpe.iloc[-1])

    def estimate_half_life(self, strategy_name: str) -> Optional[float]:
        """
        Estimate strategy half-life in months based on Sharpe decay.

        Returns:
            Estimated half-life in months, or None if insufficient data
        """
        if strategy_name not in self.strategy_metrics:
            return None

        metrics = self.strategy_metrics[strategy_name]
        if len(metrics['rolling_sharpe']) < 3:  # Need minimum points
            return None

        # Convert to time series
        sharpe_series = pd.Series(metrics['rolling_sharpe'],
                                 index=metrics['timestamps'][-len(metrics['rolling_sharpe']):])

        # Calculate decay rate using linear regression on log Sharpe
        # Assume: Sharpe(t) = Sharpe0 * exp(-λt) => log(Sharpe) = log(Sharpe0) - λt
        # Half-life = ln(2)/λ

        # Clean data: remove NaN and infinite values
        valid_idx = (~sharpe_series.isna()) & (sharpe_series > 0)
        if valid_idx.sum() < 3:
            return None

        clean_sharpe = sharpe_series[valid_idx]
        if len(clean_sharpe) < 3:
            return None

        # Convert timestamps to numeric (months since start)
        start_time = clean_sharpe.index[0]
        time_months = [(ts - start_time).days / 30.44 for ts in clean_sharpe.index]

        # Linear regression on log(Sharpe)
        log_sharpe = np.log(clean_sharpe.values)
        if np.any(np.isinf(log_sharpe)) or np.any(np.isnan(log_sharpe)):
            return None

        try:
            # λ = -slope of log(Sharpe) vs time
            slope, intercept = np.polyfit(time_months, log_sharpe, 1)
            decay_rate = -slope  # Positive decay rate means decreasing Sharpe

            if decay_rate <= 0:  # No decay or improvement
                return float('inf')  # Infinite half-life (no decay)

            half_life = np.log(2) / decay_rate
            return max(0.1, half_life)  # Minimum 0.1 month to avoid division by zero)
        except:
            return None

    def get_decay_resistance_score(self, strategy_name: str) -> float:
        """
        Calculate decay resistance score (0-1, higher = more resistant).

        Combines:
        - Estimated half-life (normalized)
        - Crowding sensitivity (simulated)
        - Performative impact resistance

        Returns:
            Score between 0 and 1
        """
        half_life = self.estimate_half_life(strategy_name)
        if half_life is None or half_life == float('inf'):
            # No decay detected or insufficient data - assign moderate score
            base_score = 0.5
        else:
            # Normalize half-life: assume 36 months (3 years) is excellent, 6 months is poor
            base_score = min(1.0, max(0.0, (half_life - 3) / (36 - 3)))

        # TODO: Implement crowding sensitivity simulation
        # For now, use placeholder based on strategy characteristics
        crowding_sensitivity = self._estimate_crowding_sensitivity(strategy_name)

        # TODO: Implement performative impact resistance
        performative_resistance = self._estimate_performative_resistance(strategy_name)

        # Weighted combination (can be adjusted)
        score = 0.5 * base_score + 0.3 * (1 - crowding_sensitivity) + 0.2 * performative_resistance
        return max(0.0, min(1.0, score))

    def _estimate_crowding_sensitivity(self, strategy_name: str) -> float:
        """
        Estimate how sensitive strategy is to crowding (0-1, higher = more sensitive).
        In practice, this would involve:
        - Simulating strategy performance with increasing numbers of similar strategies
        - Measuring Sharpe decay as a function of strategy popularity
        """
        # Placeholder implementation - should be customized per strategy
        # Strategies based on structural factors (e.g., funding carry) less sensitive
        # Pure statistical patterns more sensitive
        structural_indicators = ['funding', 'overnight', 'turn_of_month', 'carry']
        pattern_indicators = ['orb', 'breakout', 'momentum', 'mean_reversion']

        name_lower = strategy_name.lower()
        structural_score = sum(1 for ind in structural_indicators if ind in name_lower)
        pattern_score = sum(1 for ind in pattern_indicators if ind in name_lower)

        if structural_score > 0 and pattern_score == 0:
            return 0.2  # Low crowding sensitivity
        elif pattern_score > 0 and structural_score == 0:
            return 0.8  # High crowding sensitivity
        else:
            return 0.5  # Mixed

    def _estimate_performative_resistance(self, strategy_name: str) -> float:
        """
        Estimate resistance to performative signal erosion (0-1, higher = more resistant).
        Strategies that trade less liquid instruments or have longer holding periods
        are typically more resistant.
        """
        # Placeholder - should be customized based on actual strategy logic
        liquidity_indicators = ['future', 'etf', 'large_cap']
        low_liquidity_indicators = ['small_cap', 'exotic', 'bond', 'commodity']

        name_lower = strategy_name.lower()
        liquidity_score = sum(1 for ind in liquidity_indicators if ind in name_lower)
        low_liq_score = sum(1 for ind in low_liquidity_indicators if ind in name_lower)

        if low_liq_score > 0 and liquidity_score == 0:
            return 0.8  # High resistance (trades less liquid markets)
        elif liquidity_score > 0 and low_liq_score == 0:
            return 0.3  # Low resistance (trades highly liquid markets)
        else:
            return 0.5  # Moderate

def adjust_position_sizing(base_risk_scale: float,
                          strategy_decay_scores: Dict[str, float],
                          min_scale: float = 0.5,
                          max_scale: float = 2.0) -> Dict[str, float]:
    """
    Adjust position sizing based on strategy decay resistance.

    Args:
        base_risk_scale: Base risk scale from conformal DD-throttle
        strategy_decay_scores: Dict of strategy names to decay resistance scores (0-1)
        min_scale: Minimum position size multiplier
        max_scale: Maximum position size multiplier

    Returns:
        Dict of strategy names to adjusted risk scales
    """
    adjusted_scales = {}
    for strategy, score in strategy_decay_scores.items():
        # Map score [0,1] to scale [min_scale, max_scale]
        # Higher decay resistance -> larger position size
        adjusted = min_scale + (max_scale - min_scale) * score
        adjusted_scales[strategy] = base_risk_scale * adjusted
    return adjusted_scales

def enhance_gauntlet_with_decay_checks(gauntlet_results: Dict,
                                     decay_monitor: DecayMonitor) -> Dict:
    """
    Enhance strategy gauntlet results with decay-aware checks.

    Args:
        gauntlet_results: Existing gauntlet evaluation results
        decay_monitor: Initialized DecayMonitor instance

    Returns:
        Enhanced results with decay metrics
    """
    enhanced = gauntlet_results.copy()

    # Add decay metrics for each strategy that passed initial gauntlet
    for strategy_name, results in enhanced.items():
        if isinstance(results, dict) and results.get('verdict') == 'PASS':
            # Estimate half-life
            half_life = decay_monitor.estimate_half_life(strategy_name)
            decay_score = decay_monitor.get_decay_resistance_score(strategy_name)

            # Add decay-aware fields
            results['estimated_half_life_months'] = half_life
            results['decay_resistance_score'] = decay_score

            # Decay-aware verdict: fail if half-life too short (<6 months)
            # unless strategy has exceptionally high OOS Sharpe to compensate
            if half_life is not None and half_life < 6.0:
                # Check if high Sharpe compensates (similar to existing gauntlet rule)
                oos_sharpe = results.get('OOS', 0)
                if oos_sharpe < 1.0:  # Arbitrary threshold - can be tuned
                    results['verdict'] = 'FAIL'
                    results['decay_why'] = f'Short half-life ({half_life:.1f} months) with moderate OOS Sharpe ({oos_sharpe:.2f})'
                else:
                    results['decay_why'] = f'Short half-life but high OOS Sharpe ({oos_sharpe:.2f}) - monitoring recommended'
            else:
                results['decay_why'] = f'Half-life: {half_life if half_life else "Insufficient data"} months'

    return enhanced

def load_strategy_performance_from_file(filepath: str) -> pd.DataFrame:
    """
    Load strategy performance data from CSV/backtest results.
    Expected format: timestamp, strategy_name, return
    """
    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def main():
    """
    Example usage of decay-aware strategy management.
    """
    # Initialize decay monitor
    monitor = DecayMonitor(half_life_window_months=12)

    # Example: Load strategy performance (replace with actual data source)
    try:
        perf_df = load_strategy_performance_from_file('strategy_performance.csv')

        # Update monitor with performance data
        for strategy in perf_df['strategy_name'].unique():
            strategy_data = perf_df[perf_df['strategy_name'] == strategy]
            for _, row in strategy_data.iterrows():
                monitor.update_strategy_performance(
                    strategy_name=strategy,
                    returns=pd.Series([row['return']]),
                    timestamp=row['timestamp']
                )
    except FileNotFoundError:
        print("No performance data file found. Using example data.")
        # Create example data for demonstration
        dates = pd.date_range(start='2023-01-01', end='2024-12-31', freq='D')
        example_strategies = ['S1_sweep', 'S2_gold', 'S3_vol', 'S4_multi', 'S5_orb']

        for strategy in example_strategies:
            # Generate returns with different decay characteristics
            np.random.seed(hash(strategy) % 2**32)
            base_return = 0.0005  # 0.05% daily
            decay_factor = np.exp(-np.linspace(0, 0.5, len(dates)))  # Decay over time
            returns = base_return * decay_factor + np.random.normal(0, 0.01, len(dates))

            for date, ret in zip(dates, returns):
                monitor.update_strategy_performance(strategy, pd.Series([ret]), date)

    # Get decay scores for all strategies
    strategy_names = list(monitor.strategy_metrics.keys())
    decay_scores = {name: monitor.get_decay_resistance_score(name) for name in strategy_names}
    half_lives = {name: monitor.estimate_half_life(name) for name in strategy_names}

    # Print results
    print("\n=== DECAY-AWARE STRATEGY ANALYSIS ===")
    print(f"{'Strategy':<15} {'Half-Life (mo)':<15} {'Decay Score':<12} {'Status'}")
    print("-" * 50)
    for name in strategy_names:
        hl = half_lives[name]
        score = decay_scores[name]
        hl_str = f"{hl:.1f}" if hl is not None else "Insuff"
        status = "PASS" if (score > 0.6 and (hl is None or hl > 6)) else "REVIEW"
        print(f"{name:<15} {hl_str:<15} {score:<12.3f} {status}")

    # Example position sizing adjustment
    base_risk_scale = 1.0  # From conformal DD-throttle
    adjusted_scales = adjust_position_sizing(base_risk_scale, decay_scores)
    print("\n=== ADJUSTED POSITION SIZING ===")
    print(f"{'Strategy':<15} {'Base Scale':<12} {'Adjusted Scale':<15}")
    print("-" * 40)
    for name in strategy_names:
        print(f"{name:<15} {base_risk_scale:<12.3f} {adjusted_scales[name]:<15.3f}")

if __name__ == "__main__":
    main()