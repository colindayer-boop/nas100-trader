# Risk Mode Architecture

## Overview

This document describes the mode-based risk governance layer added to the NAS100 trading system. The system supports three distinct trading modes:

1. **Challenge Mode** - For passing prop firm evaluations (e.g., FTMO, FundedNext)
2. **Funded Mode** - For trading funded accounts after passing the challenge
3. **Live Mode** - For personal live trading accounts

Each mode applies a set of risk parameters that layer on top of the existing risk engine (DD-throttle, kill-switch, etc.) without altering the core strategy logic or validated parameters.

## Design Goals

- **Non-intrusive**: The risk mode layer only gates new entries and adjusts position sizing. It does not modify:
  - Strategy entry/exit logic
  - Validated stop-loss (SL) and take-profit (TP) distances
  - Existing risk systems (daily kill-switch, monthly kill-switch, DD-throttle)
- **Configurable**: Modes are selected via environment variable (`RISK_MODE`) or configuration file.
- **Explicit Requirements**: Every order must still have broker-side SL and TP (enforced by the broker adapters and logged if missing).
- **Clear Separation**: Each mode has distinct priorities and constraints.

## Components

### 1. Configuration (`config/risk_profiles.yaml`)

Defines three profiles (`challenge`, `funded`, `live`) and a `default` section for shared parameters.

Each profile includes:
- `risk_multiplier`: Scales the equity used in position sizing (multiplied by existing `RISK_S*` and broker-specific `RISK_SCALE`)
- `max_daily_trades`: Maximum new trades allowed per day
- `max_consecutive_losses`: After this many losses in a row, reduce risk by `consecutive_loss_reduction`
- `daily_profit_lock_threshold`: When daily profit reaches this fraction of equity, apply `daily_profit_lock_multiplier`
- `allowed_strategies`: List of strategy IDs permitted in this mode (e.g., `["S1", "S2", "S3"]`)
- `reduced_risk_mode`: Boolean flag (can be toggled externally) that applies an additional risk reduction
- `emergency_drawdown_threshold`: If current drawdown exceeds this, trigger emergency stop (no new orders)
- `broker_side_sl_tp_required`: Boolean (always `true` in this system) to enforce broker-side brackets

### 2. Profile Loader (`risk/risk_profile_loader.py`)

- Loads profiles from `config/risk_profiles.yaml`
- Selects the active profile based on:
  1. `risk_mode` key in the `[risk]` section of `config.ini` (if present)
  2. `RISK_MODE` environment variable
  3. Defaults to `live` if neither is set
- Provides `get_active_profile()` function returning the profile dictionary
- Includes a `RiskMode` base class that implements common logic (consecutive losses, profit lock, etc.)

### 3. Mode Implementations (`risk/challenge_mode.py`, `risk/funded_mode.py`, `risk/live_mode.py`)

Each file provides a thin wrapper that instantiates `RiskMode` with the appropriate profile and exposes a `get_instance()` function.

### 4. Integration Point

The risk mode is intended to be called from the main trading loop (e.g., in `live_trader.py`) before placing an order:

```python
from risk.challenge_mode import get_instance as get_challenge_mode   # or funded_mode, live_mode
# Or, dynamically based on config:
# from risk.risk_profile_loader import get_active_profile, RiskMode
# active_profile = get_active_profile()
# risk_mode = RiskMode(active_profile)

# Then, for each potential trade:
risk_mode = get_challenge_mode()  # Example
if not risk_mode.can_trade(today_trade_count, consecutive_losses, daily_pnl, current_drawdown):
    logger.info("Risk mode blocks new trade")
    continue  # Skip this signal

# Adjust position size:
base_risk = equity * RISK_Sx * vix_mult * broker.RISK_SCALE
adjusted_risk = base_risk * risk_mode.get_risk_multiplier()
shares = adjusted_risk / (price * stop_distance)

# Also, the risk mode can signal to reduce risk after consecutive losses or after profit lock:
# (These are already applied via the multiplier returned by get_risk_multiplier())

# Finally, place the order with broker-side SL and TP (as already done in the code)
broker.place_order_safe(symbol, shares, side, tag, sl=stop_price, tp=profit_price)
```

## How It Works

### Risk Multiplier Calculation

The final risk multiplier for a trade is computed as:

```
final_multiplier = base_profile_risk_multiplier
                 * consecutive_loss_adjustment (if applicable)
                 * profit_lock_adjustment (if applicable)
                 * reduced_risk_mode_adjustment (if enabled)
```

Where:
- `base_profile_risk_multiplier` comes from the YAML profile (e.g., 0.5 for challenge)
- `consecutive_loss_adjustment` is `consecutive_loss_reduction` raised to the number of excess losses (e.g., if `max_consecutive_losses=2` and we have 4 losses, apply reduction twice)
- `profit_lock_adjustment` is `daily_profit_lock_multiplier` if daily profit >= threshold
- `reduced_risk_mode_adjustment` is `reduced_risk_multiplier` if the flag is set

### Decision to Trade

The `can_trade` method checks:
1. Have we exceeded `max_daily_trades`?
2. Have we exceeded `max_consecutive_losses` (without yet applying the reduction? Actually, we allow trading but with reduced size; the halt is optional and can be configured via a separate `halt_after_consecutive_losses` if desired, but current design reduces size rather than halting).
3. Is the drawdown beyond `emergency_drawdown_threshold`? (If yes, no new trades.)
4. Is the strategy in `allowed_strategies`?

Note: The current implementation does not halt trading after consecutive losses; it reduces size. If a hard halt is desired, it can be added by extending the profile.

## Extending the System

To add a new mode:
1. Add a new profile to `config/risk_profiles.yaml` (or extend an existing one).
2. Create a new file in `risk/` (e.g., `risk/my_mode.py`) that instantiates `RiskMode` with that profile.
3. Update the documentation.

## Interaction with Existing Systems

### Existing Risk Controls (Unchanged)
- **Daily Kill-switch**: Still halts trading if session loss exceeds `daily_loss_limit` from `config.ini`.
- **Monthly Kill-switch**: Still halts trading if month-to-date loss exceeds `monthly_loss_limit`.
- **DD-throttle**: Continuously scales `broker.RISK_SCALE` based on live drawdown relative to `target_drawdown`.

### Order Submission
All existing `place_order_safe` calls remain unchanged. The risk mode layer computes an adjusted position size (by modifying the effective equity or risk percentage) before calling `place_order_safe`. The stop-loss and take-profit prices are still computed as before (using the strategy's validated SL and TP distances).

### Broker-side SL/TP Requirement
The parameter `broker_side_sl_tp_required` is included for completeness and is set to `true` in all profiles. The existing code already attaches SL and TP to every order (see the `sl=` and `tp=` arguments in `place_order_safe` calls). A future enhancement could add an assertion that these are not `None`.

## Configuration Precedence

The active risk profile is determined by (in order of precedence):

1. **Environment Variable**: `RISK_MODE` (e.g., `export RISK_MODE=challenge`)
2. **Config File**: `risk_mode` key in the `[risk]` section of `config.ini`
3. **Default**: `live`

Example `config.ini` snippet:
```
[risk]
risk_mode = challenge
```

Example environment variable:
```
export RISK_MODE=funded
```

If both are set, the environment variable takes precedence.

## Testing and Validation

Because this layer does not alter strategy signals or validated SL/TP distances, the core strategy behavior remains unchanged. Risk metrics (position size, daily trade count, etc.) can be logged and monitored to ensure the mode is behaving as expected.

## Conclusion

This risk mode architecture provides a clean, configurable way to adapt the trading system to different capital environments (challenge, funded, live) while preserving the integrity of the validated trading strategies and existing risk controls.
