# LIVE_RESEARCH_PARITY_REPORT — PHASE 601 Stage 10

Replays historical live/demo trades through the **same** rewired production gate (`authorize()`) and
classifies divergences. The decisive test: would the new system have taken the trades the old one did?

## The 3 real BTCUSD positions (magic 770001)
| ticket | symbol | entry | old-system action | rewired decision | reason |
|--|--|--|--|--|--|
| 346174109 | BTCUSD | 65,621 | opened (live) | **BLOCK** | `NO_CONTRACT` |
| 344793765 | BTCUSD | 66,220 | opened (live) | **BLOCK** | `NO_CONTRACT` |
| 344259068 | BTCUSD | 64,836 | opened (live) | **BLOCK** | `NO_CONTRACT` |

**3/3 historical BTC trades are BLOCKED by the rewired gate.** With a contract present they would still
have been blocked at `SYMBOL_NOT_PERMITTED`, `NO_APPROVED_TRIAL`, and `STOP_DISTANCE_IMPLAUSIBLE`
(the ~20% stop) — four independent gates, any one sufficient.

## Divergence classification
- All three: **UNKNOWN_ATTRIBUTION → now attributed** (magic 770001 = `mt5_broker.py:205`), and
  **BLOCKED_BY_REWIRE**. No `SIGNAL/VERSION/DATA/SIZING/STOP/BROKER` divergence needed to be resolved
  because the trades never clear the first gate (no approved contract).

## Interpretation
The old path could open a position from raw strategy code with no contract, no trial, no version
check, and an implausible stop. The rewired path makes each of those a hard block. **The exact failure
that started this recovery cannot recur through the new pathway.** (The legacy `live_trader.py` path
still exists and must be retired/routed through `authorize()` — see readiness risks.)
