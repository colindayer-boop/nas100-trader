# Challenge vs Funded vs Live: Mode Comparison

This document outlines the key differences between the three risk modes: **Challenge**, **Funded**, and **Live**. Each mode is designed for a specific stage of a trader's journey with proprietary trading firms and personal capital.

## Overview

| Aspect               | Challenge Mode                          | Funded Mode                             | Live Mode                               |
|----------------------|-----------------------------------------|-----------------------------------------|-----------------------------------------|
| **Primary Goal**     | Pass the prop firm evaluation           | Safely grow the funded account          | Long-term capital growth                |
| **Account Type**     | Evaluation account (e.g., FTMO trial)   | Funded account (after passing challenge)| Personal trading account                |
| **Risk Tolerance**   | Very low (capital preservation)         | Moderate (growth with protection)       | Higher (focus on risk-adjusted returns) |
| **Profit Target**    | Must hit target to pass (e.g., 8-10%)   | No formal target; focus on consistency  | No target; compound growth              |
| **Loss Limits**      | Strict (often 10% max DD, 5% daily)     | Defined by funder's rules (e.g., 5% DD) | Set by trader's risk tolerance          |

## Detailed Comparison

### Challenge Mode
- **Purpose**: Survive the evaluation period and meet the profit target without violating any rules.
- **Key Constraints**:
  - **Max Daily Loss**: Typically 5% (must not exceed)
  - **Max Drawdown**: Typically 10% (absolute or trailing, depending on firm)
  - **Consistency**: Often requires trading on a minimum number of days.
  - **No Overtrading**: Strict limit on number of trades per day.
  - **Strategy Selection**: Only the most reliable, low-variance strategies are allowed.
  - **Profit Lock**: Early profit-taking to lock in gains and reduce risk.
  - **Position Size**: Significantly reduced (e.g., 50% of normal) to avoid large drawdowns.
- **Typical Settings** (from `risk_profiles.yaml`):
  - `risk_multiplier`: 0.5
  - `max_daily_trades`: 15
  - `max_consecutive_losses`: 2
  - `daily_profit_lock_threshold`: 0.01 (1% of equity)
  - `allowed_strategies`: ["S1", "S2", "S3"] (most reliable sessions)
  - `emergency_drawdown_threshold`: 0.10 (10%)

### Funded Mode
- **Purpose**: Generate consistent returns while staying within the funder's risk limits and avoiding disqualification.
- **Key Constraints**:
  - **Max Drawdown**: Defined by the funder (e.g., 6% max drawdown for some firms).
  - **Daily Loss Limit**: Often similar to challenge (e.g., 5%) but may be slightly relaxed.
  - **Consistency**: Still important, but less rigid than challenge.
  - **Growth Focus**: Aim for steady equity growth without large drawdowns.
  - **Strategy Selection**: A broader set of strategies can be traded (but still avoids the highest variance).
  - **Position Size**: Moderately reduced (e.g., 75% of normal) to balance growth and safety.
- **Typical Settings**:
  - `risk_multiplier`: 0.75
  - `max_daily_trades`: 30
  - `max_consecutive_losses`: 3
  - `daily_profit_lock_threshold`: 0.015 (1.5% of equity)
  - `allowed_strategies`: ["S1", "S2", "S3", "S4", "S5"] (all sessions, excluding BTC for some setups)
  - `emergency_drawdown_threshold`: 0.15 (15%)

### Live Mode
- **Purpose**: Maximize long-term, risk-adjusted returns on personal capital.
- **Key Constraints**:
  - **Drawdown Tolerance**: Higher, as there is no external authority imposing limits (though prudent risk management is still advised).
  - **No External Rules**: Only self-imposed risk limits.
  - **Growth Focus**: Compound returns over time; can accept higher volatility for higher expected returns.
  - **Strategy Selection**: All available strategies, including higher-variance ones like BTC or exotic pairs.
  - **Position Size**: Full size (1.0x) based on validated strategy parameters.
  - **Flexibility**: Can enable a "reduced risk mode" manually during high volatility or drawdown periods.
- **Typical Settings**:
  - `risk_multiplier`: 1.0
  - `max_daily_trades`: 50 (high, but effectively limited by signal frequency)
  - `max_consecutive_losses`: 5
  - `daily_profit_lock_threshold`: 0.02 (2% of equity)
  - `allowed_strategies`: ["S1", "S2", "S3", "S4", "S5", "BTC"] (all strategies)
  - `emergency_drawdown_threshold`: 0.20 (20% - a personal circuit breaker)
  - `reduced_risk_mode`: Can be set to `True` to automatically halve size during tough periods.

## When to Use Which Mode

### Use Challenge Mode When:
- You are currently in a prop firm evaluation (e.g., FTMO, FundedNext, MyForexFunds).
- Your primary goal is to pass the evaluation *safely* (not necessarily maximally).
- You need to adhere strictly to the firm's daily loss limit, max drawdown, and consistency rules.
- You want to minimize the chance of a breach due to overtrading or a large loss.

### Use Funded Mode When:
- You have successfully passed the evaluation and now have a funded account.
- You must adhere to the funder's ongoing risk rules (which may be similar to or slightly more lenient than the challenge).
- You aim to build a track record with the funder to potentially gain scaling or higher allocations.
- You want to avoid breaching the funder's max drawdown or daily loss limits.

### Use Live Mode When:
- You are trading your own personal capital.
- There are no external profit targets or loss limits (only those you set for yourself).
- Your focus is on long-term wealth compounding.
- You are comfortable with higher drawdowns in exchange for higher expected returns (within reason).
- You want the flexibility to trade all strategies in your arsenal.

## Risk Parameter Rationale

### Risk Multiplier
- **Challenge (0.5)**: Halves the position size to drastically reduce the chance of a large drawdown that could break the challenge rules.
- **Funded (0.75)**: Reduces size by 25% to provide a buffer against the funder's drawdown limit while still allowing meaningful growth.
- **Live (1.0)**: Uses the full, validated position size because the trader is responsible for their own risk limits.

### Max Daily Trades
- **Challenge (15)**: Severely limits trading to avoid overtrading and ensure only the best setups are taken.
- **Funded (30)**: Allows more trading opportunities while still preventing excessive churn.
- **Live (50)**: Set high because the limiting factor is signal frequency, not a rule; but still provides a sanity check.

### Max Consecutive Losses
- **Challenge (2)**: After two losses in a row, risk is reduced (e.g., by 50%) to prevent a streak from blowing the account.
- **Funded (3)**: Allows a slightly longer losing streak before reducing size.
- **Live (5)**: Accepts that longer losing streaks can occur in a high-edge system and only reduces size after five losses.

### Daily Profit Lock
- **Threshold**: The profit level at which we start to reduce risk to lock in gains.
- **Challenge (1%)**: Very aggressive profit locking to ensure we stay positive each day.
- **Funded (1.5%)**: Slightly more lenient, allowing the trade to run a bit more before protecting profits.
- **Live (2%)**: Even more lenient, letting winners run longer in pursuit of higher returns.

### Allowed Strategies
- **Challenge**: Only the core sessions (S1, S2, S3) which have been historically the most reliable and lowest variance.
- **Funded**: Adds S4 and S5 (additional sessions) which have good edges but slightly higher variance.
- **Live**: Adds BTC (or other high-volatility instruments) for those who wish to trade them, acknowledging the higher risk.

### Emergency Drawdown Threshold
- **Challenge (10%)**: Matches typical challenge max drawdown; if we hit this, we stop new trades to avoid breach.
- **Funded (15%)**: Provides a buffer before hitting the funder's limit (which might be higher, e.g., 20% for some).
- **Live (20%)**: A personal circuit breaker; if we lose 20% from peak, we stop and reassess.

## Important Notes

1. **Broker-side SL/TP is Mandatory in All Modes**: Every order must have a stop-loss and take-profit attached at the broker level. This is non-negotiable and enforced by the existing broker adapters.

2. **No Changes to Strategy Logic**: The entry and exit signals, as well as the validated stop-loss and take-profit distances (e.g., `STOP_S1`, `RR_S1`), remain exactly the same across all modes. Only the position size (number of shares/contracts) is adjusted.

3. **Dynamic Adjustments**: The risk mode does not just set a static multiplier; it also adjusts for consecutive losses and daily profit lock in real time.

4. **Funder Rules Trump Settings**: Always consult your specific prop firm's rulebook. The settings in `risk_profiles.yaml* are starting points and may need to be tuned to match your exact challenge or funded account terms.

5. **Live Mode Responsibility**: In live mode, you are solely responsible for your risk settings. The provided `live` profile is a suggestion; feel free to adjust it to match your personal risk tolerance.

## Example Usage

To run the system in challenge mode:
```bash
export RISK_MODE=challenge
python live_trader.py --broker alpaca
```

Or, set it in `config.ini`:
```ini
[risk]
risk_mode = challenge
```

To switch to funded mode later (after passing the challenge):
```bash
export RISK_MODE=funded
```
or edit `config.ini` accordingly.

Remember to restart the application after changing the mode.

## Conclusion

By clearly defining and separating the risk parameters for each stage of a trader's journey, this system helps traders:
- Pass challenges more consistently by removing emotion and overtrading.
- Grow funded accounts without breaching fragile rules.
- Grow personal capital with a clear, adjustable risk framework.

The mode-based approach ensures that the same core trading engine can be used across all stages of a trader's career, with only the risk parameters changing to match the context.
