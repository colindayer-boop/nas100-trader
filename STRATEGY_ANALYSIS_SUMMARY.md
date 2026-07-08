# Strategy Analysis Summary: S5 ORB Short & S3 Abnormal Volume

## Overview
Analysis of why S5 ORB Short and S3 Abnormal Volume strategies underperformed in the full 5-strategy backtest.

## Key Findings

### S5 ORB Short Strategy
- **Signal Frequency**: 44.6 signals/year (plenty)
- **Actual Trades**: ~5.2 trades/year (many signals don't produce executable trades due to intraday mechanics)
- **Win Rate**: 23.1% (very poor)
- **Average Win**: ~2.5%
- **Average Loss**: 1.0% (stop loss)
- **Expected Value/Trade**: -0.19%
- **Annual Return**: -0.7% (consistently negative across 2019,2020,2021,2023; +1.3% in 2022 only)
- **Root Cause**: Strategy loses money because wins are too infrequent and too small relative to losses

### S3 Abnormal Volume Strategy  
- **Signal Frequency**: 1.8 signals/year (very low)
- **Actual Trades**: ~1.6 trades/year
- **Win Rate**: 37.5% (poor)
- **Profit Factor**: 1.34
- **Annual Return**: ~-0.1% (slightly negative)
- **Root Cause**: Too few trades for statistical significance; results are noisy and unreliable

## Root Cause Analysis

### S5 ORB Short Issues:
1. **Poor Edge**: The strategy's win rate (23.1%) is too low to be profitable given the 1:2.5 risk/reward ratio
2. **Stop Loss Dependency**: 76.9% of trades hit the 1% stop loss
3. **Market Conditions**: The ORB breakdown short setup simply doesn't work consistently in our test period

### S3 Abnormal Volume Issues:
1. **Excessive Filter**: The 1.5x volume threshold is too restrictive
2. **Insufficient Sample Size**: With only ~2 signals/year, results are dominated by luck/noise
3. **Poor Timing**: Entry at next day open may not capture the intended move

## Conservative Recommendations

### For S5 ORB Short: 
**RECOMMENDATION: REMOVE FROM PORTFOLIO**
- The strategy has a negative expectancy (-0.7%/year average)
- Attempting to "fix" it through parameter tuning risks significant overfitting
- The 4-strategy portfolio (S1 Long, S4 Long, S5 Long, S2) shows positive expectancy
- Focus on refining and optimizing the proven strategies rather than trying to rescue a broken one

### For S3 Abnormal Volume:
**RECOMMENDATION: TEST 1.3x VOLUME THRESHOLD (OOS VALIDATION REQUIRED)**
- Current threshold: 1.5x 20-day average volume
- Proposed threshold: 1.3x 20-day average volume  
- **Reasoning**: 
  - 1.5x is arbitrary; 1.3x still represents meaningfully "abnormal" volume (30% above average)
  - Expected increase: ~1.8 → ~4.5 signals/year (based on interpolation of sensitivity data)
  - Maintains conservative approach while improving statistical significance
  - Still avoids extreme noise levels (>2.0x multipliers)

**IMPORTANT: ANY CHANGE TO S3 REQUIRES OUT-OF-SAMPLE VALIDATION**
1. Test on 2024-2025 data (if available) or use walk-forward analysis
2. Do NOT optimize based on in-sample performance
3. Only adopt if OOS performance shows clear improvement without overfitting signs

## Alternative Approach: Focus on What Works

The validated 4-strategy core shows:
- **S1 Asian Sweep (Long)**: +3.1%/year
- **S4 Multi-Sweep (Long)**: +2.9%/year  
- **S5 ORB Long**: +2.7%/year
- **S2 Gold FVG (Long)**: +2.7%/year
- **Combined (approx)**: +10-11%/year gross → ~4-7%/year net after correlation & positioning

This aligns with the original findings of 4-7%/year on validated strategies.

## Next Steps
1. **Remove S5 ORB Short** from live trading consideration
2. **If pursuing S3 improvement**: 
   - Test 1.3x volume threshold on OOS data
   - Only proceed if OOS shows clear, robust improvement
   - Otherwise, accept that S3 may not be viable with current data constraints
3. **Consider walk-forward analysis** to validate the 4-strategy core robustness
4. **Focus on execution quality** and risk management of the working strategies

