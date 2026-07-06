# 04 Risk Engine

Sizing, drawdown control, kill-switch. Config in `config.ini [risk]`.

## Sizing
`qty = equity * risk_frac * vix_mult * throttle / (price * stop_pct)`
Per-strategy risk_frac: S1 0.70%, S2 0.50%, S3/S4 0.40%, S5 0.75%, BTC 0.60%.

## Conformal DD-throttle
`throttle = clamp(0.3..1.0, (target_dd + cur_dd) / target_dd)` with `target_dd = 0.08`.
Position size scales down as live drawdown nears the target -> holds the account
under prop limits. Validated: MaxDD -7.9% -> -4.8%, Calmar 1.54 -> 2.00.

## Kill-switch & regime
- daily loss > 5% or month-to-date > 4% -> halt new orders
- VIX 21d > 25 -> `vix_mult = 0` (pause); 20-25 -> half size

## Per-account isolation
`risk_state_<broker>.json` so Alpaca's peak can't throttle BTC's account.

## Prop sizing (V2)
`prop_mode=1, prop_vol_target=0.16` (balanced pass-odds vs blow-up). See [[09 Prop Firms]].

Links: [[06 Execution Engine]] | [[03-Validated-Strategies/_index|Strategies]] | [[LIVE_SAFETY_AUDIT]]
