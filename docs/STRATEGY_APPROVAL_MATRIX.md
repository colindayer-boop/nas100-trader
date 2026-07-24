# STRATEGY_APPROVAL_MATRIX — PHASE 601 Stage 13

Conservative by mandate. **No strategy is auto-approved.** `may_trade_demo` requires `PAPER_APPROVED`;
`may_trade_real` requires `LIVE_APPROVED`. Today **every** strategy is below that bar, so the
fail-closed gate blocks all of them.

| strategy_id | family | status | approved trials | may trade demo? | why |
|--|--|--|--|--|--|
| `phase404_ote` | liquidity_sweep | **RESEARCH_ONLY** | none | ❌ | backtest −0.80R / 15k trades; no positive frozen trial |
| `btc_sweep` | liquidity_sweep | **SUSPENDED** | none | ❌ | associated with unattributed BTC trades (Expert 770001); pending audit |
| `btc_trend` | trend | **SUSPENDED** | none | ❌ | same BTC-magic exposure; pending attribution |
| `trend_ema_12_26` | trend | **NEEDS_REPLICATION** | none | ❌ | positive in research (pooled +1.03R) but no *deployable-version* frozen trial linked yet |
| `carry_rank` | carry | **NEEDS_REPLICATION** | none | ❌ | weak-positive (Sharpe ~0.38); needs a frozen executable + trial |

**Path to PAPER_APPROVED (for trend/carry — the only plausible candidates):**
1. Freeze the exact executable version + `code_commit`.
2. Link a pre-registered trial whose scorecard passed (walk-forward, after costs, CI excludes 0).
3. Simulate against the specific prop-firm config (Stage 5).
4. Pass execution-reliability + shadow soak (Stage 11).
5. Human + Review Board approval → status flips to `PAPER_APPROVED`.

Until all five, `authorize()` returns BLOCK. No exceptions, no averaging of weak scores.
