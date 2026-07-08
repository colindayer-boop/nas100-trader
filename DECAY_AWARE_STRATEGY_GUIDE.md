# DECAY-AWARE STRATEGY MANAGEMENT FOR NAS100-TRADER

## Overview
This implementation integrates insights from the paper "Three channels of AI-driven alpha decay" (arXiv:2605.23905) into your existing trading framework. It provides tools to monitor, measure, and adapt to strategy decay caused by:
1. Signal crowding (correlated AI predictions)
2. Performative signal erosion (trading degrades signal quality)
3. Red Queen dynamics (competitive AI investment accelerates decay)

## Files Created

### 1. `decay_aware_strategy_management.py`
Core implementation containing:
- `DecayMonitor`: Estimates strategy half-life from performance decay
- Decay resistance scoring (combines half-life, crowding sensitivity, performative resistance)
- Position sizing adjustment based on decay resistance
- Enhanced gauntlet evaluation with decay-aware checks

## How to Integrate

### Step 1: Install Dependencies (if needed)
```bash
pip install numpy pandas pyyaml
```

### Step 2: Integrate with Existing Workflow

#### Option A: Enhance Strategy Evaluation (Recommended)
Modify your strategy evaluation process (e.g., in `EDGE_HUNT_BRIEF.md` workflow or `HUNT_LOG.md` generation):

```python
# In your strategy evaluation script
from decay_aware_strategy_management import DecayMonitor, enhance_gauntlet_with_decay_checks

# After running your standard gauntlet tests...
gauntlet_results = {
    'strategy_name': {
        'IS': is_sharpe,
        'OOS': oos_sharpe,
        'OOS_DD': max_drawdown,
        # ... other gauntlet metrics
        'verdict': 'PASS' or 'FAIL'
    }
}

# Enhancer
decay_monitor = DecayMonitor()
# (Optionally load historical performance data here)
enhanced_results = enhance_gauntlet_with_decay_checks(gauntlet_results, decay_monitor)

# Log enhanced results to HUNT_LOG.md
```

#### Option B: Adaptive Position Sizing
Modify your position sizing logic in `live_trader.py` or risk management module:

```python
# In your risk management code
from decay_aware_strategy_management import adjust_position_sizing

# Get base risk scale from your conformal DD-throttle
base_risk_scale = get_current_risk_scale()  # Your existing function

# Get decay scores for active strategies (maintain decay monitor state)
strategy_decay_scores = {
    'S1_sweep': decay_monitor.get_decay_resistance_score('S1_sweep'),
    'S2_gold': decay_monitor.get_decay_resistance_score('S2_gold'),
    # ... etc
}

# Apply decay-adjusted scaling
adjusted_scales = adjust_position_sizing(base_risk_scale, strategy_decay_scores)

# Use adjusted_scales[position] instead of base_risk_scale for each position
```

#### Option C: Monitoring Dashboard
Create a simple monitoring script to track strategy decay over time:

```python
# decay_monitor_dashboard.py
from decay_aware_strategy_management import DecayMonitor
import pandas as pd

def generate_decay_report():
    monitor = DecayMonitor()
    # Load your strategy performance history
    # monitor.update_strategy_performance(...) for all strategies
    
    report = []
    for strategy in monitor.strategy_metrics.keys():
        half_life = monitor.estimate_half_life(strategy)
        decay_score = monitor.get_decay_resistance_score(strategy)
        
        report.append({
            'strategy': strategy,
            'half_life_months': half_life,
            'decay_score': decay_score,
            'status': 'HEALTHY' if (decay_score > 0.7 and (not half_life or half_life > 12)) 
                     else 'WATCH' if (decay_score > 0.4 and (not half_life or half_life > 6))
                     else 'AT_RISK'
        })
    
    df = pd.DataFrame(report)
    print(decay_report_df.to_string(index=False))
    # Or save to file: df.to_csv('decay_monitor_report.csv', index=False)

if __name__ == "__main__":
    generate_decay_report()
```

## Key Parameters to Tune

### In `DecayMonitor.__init__()`
- `half_life_window_months`: Lookback window for decay estimation (default 12 months)
  - Shorter = more responsive to recent changes
  - Longer = more stable estimate

### In `adjust_position_sizing()`
- `min_scale`: Minimum position size multiplier (default 0.5)
- `max_scale`: Maximum position size multiplier (default 2.0)
  - Adjust based on your risk tolerance

### In Heuristic Functions
- `_estimate_crowding_sensitivity()`: Customize per strategy type
- `_estimate_performative_resistance()`: Customize per strategy type

## Recommended Next Steps

### 1. Immediate Actions (This Week)
```bash
# 1. Copy the script to your repository
cp decay_aware_strategy_management.py /path/to/your/nas100_backtest/

# 2. Run the demo to see how it works
python decay_aware_strategy_management.py

# 3. Integrate with your strategy evaluation process
#    Add decay metrics to your HUNT_LOG.md template:
#    | when | edge | IS | OOS | OOS_DD | corr | half_life | decay_score | verdict | why |
```

### 2. Medium-Term Implementation (2-4 Weeks)
```bash
# 1. Modify your backtester to save detailed performance history
#    (timestamp, strategy, returns) for decay monitoring

# 2. Create a decay monitoring cron job
#    * 0 * * * * cd /path/to/nas100_backtest && python decay_monitor_dashboard.py >> decay.log

# 3. Enhance your strategy retirement logic
#    Strategies with half-life < 6 months get automatic review flag
```

### 3. Long-Term Strategy Evolution
```bash
# 1. Bias strategy development toward decay-resistant patterns:
#    - Structural market inefficiencies (funding, carry, calendar)
#    - Less liquid instruments (where crowding is harder)
#    - Longer holding periods (reduces performative impact)
#    - Truly alternative data (less likely to be AI-modeled)

# 2. Consider ensemble approaches:
#    - Combine strategies with uncorrelated decay patterns
#    - Use decay scoring as a meta-signal for strategy allocation

# 3. Implement crowding simulation:
#    - For candidate strategies, simulate performance with N copies
#    - Measure Sharpe decay as function of strategy popularity
```

## How This Complements Your Existing Framework

| Your Existing Strength | How Decay Awareness Enhances It |
|------------------------|----------------------------------|
| Strict OOS requirements | Adds temporal dimension to OOS validation |
| Focus on uncorrelated strategies | Provides quantitative decay resistance scoring |
| Gauntlet mindset ("REJECT almost everything") | Adds decay-aware failure modes |
| Simple, a-priori parameters | Validates preference for structural over complex AI models |
| 3 uncorrelated asset classes for prop trading | Helps maintain decorrelation as AI increases factor crowding |

## Important Notes

1. **Half-life estimation is statistical**: Requires sufficient performance history. New strategies will show "Insufficient data" until they have enough observations.

2. **Decay score is heuristic**: The crowding sensitivity and performative resistance estimates are simplifications. Refine these based on your specific strategy knowledge.

3. **Integration is gradual**: Start by monitoring and logging decay metrics before using them for position sizing or strategy retirement.

4. **Paper insight to remember**: The alpha half-life formula `h(φ)=ln2/[θ+δ(φ)]` shows decay accelerates nonlinearly with AI adoption (φ). Your decay monitoring helps estimate your effective φ for each strategy.

5. **Complements your edge hunt**: The paper validates your focus on:
   - Crypto funding carry (Priority #1) - structural, less crowded
   - Overnight drift (Priority #2) - structural/temporal
   - Avoiding overly crowded factors (like pure equity momentum)

---

*This implementation provides a foundation for decay-aware trading. As you gather more data and experience, refine the heuristics to match your specific strategies and market observations.*