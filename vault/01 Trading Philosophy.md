# 01 Trading Philosophy

The non-negotiables. Everything else is implementation.

## Edge
- **Small, uncorrelated, validated edges beat one big idea.** Combined Sharpe scales
  ~0.8*sqrt(N) with diversification, not with leverage.
- **Reject almost everything.** A research night that kills 20 ideas honestly is a
  success. See [[02-Strategy-Research/Gauntlet|the Gauntlet]].
- **Backtests overstate.** OOS + costs + correlation + regime, or it doesn't count.
- **Sparsity is fine.** S1 fires ~11x/yr; a quiet week is normal, not a bug.

## Risk
- **The broker enforces the stop, never the bot.** Proven by the 6-day outage
  ([[08-Incidents-and-Postmortems/2026-07-06 Emoji Crash|emoji crash]]).
- **Optimize for survival, not Sharpe** during a prop challenge.
- **Never fund a challenge on an unconfirmed edge.**

## Engineering
- Fail loud. ASCII logs. Single source of truth. One strategy definition for
  backtest and live. See [[ARCHITECTURE_V2]].

## Honesty
- "The system is alive" (signals fire) is NOT "the edge is profitable." Keep them separate.
