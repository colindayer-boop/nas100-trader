# MONTHLY EVIDENCE COMMITTEE REPORT -- 2026-07-12

_Clean window day 2 (anchor 2026-07-09 / parity 236abe3). Shadow days: 1. Host: local Mac -- MT5 fills live on the VPS ledger; cells that need VPS data say so. NOTHING is promoted while the 30-day window runs (clock rule) -- PROMOTE is structurally unavailable until the window closes._

## Committee inputs
1. Research backtests: validated lineage (master_backtest/full_yearly) + etf_streams.csv
2. Forward shadow: research/results/shadow_signals.csv
3. Live fills: logs/fills.csv + FILL log lines (this host)
4. Execution quality: slippage no data | spread no data | latency: not instrumented per-order; hourly polling bounds decision->submission at <=1h by design
5. Parity: docs/LIVE_TRADING_PARITY.md (3 fixed bugs; open: one-entry-per-day, S3-on-MT5 exits, fill-timing approximation)

## Per-strategy table (live book)
| strategy | expected trades (window) | actual (this host) | missed | avg R | expectancy | Sharpe | maxDD | gates observed | live-vs-research notes | RECOMMENDATION |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 0.1 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| S2 | 0.1 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| S3 | 0.1 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | Alpaca-only exits (open blocker) | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| S4 | 0.3 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| S5 | 1.6 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | mid-bar entry approximation (measured via fills.csv) | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| SWEEP | 0.2 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| BTC | 0.2 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| OVN | 0.8 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | time-exit + 5% cat-stop (intentional) | CONTINUE (expected count in window still <3 -- sparsity, not silence) |
| BTCTREND | 0.1 | 0 | VPS data needed | insufficient closed trades | - | - | - | lvl=1.0 ts=1.0 | parity clean | CONTINUE (expected count in window still <3 -- sparsity, not silence) |

## Shadow candidates
| candidate | research rate/day | shadow rate/day | shadow days | RECOMMENDATION |
|---|---|---|---|---|
| S1_GLD | 0.05 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S1_SMH | 0.09 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S1_XLK | 0.07 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_DIA | 0.13 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_QQQ | 0.19 | 1.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_SMH | 0.26 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_SPY | 0.15 | 1.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_XLE | 0.22 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| S5_XLF | 0.16 | 0.00 | 1 | CONTINUE SHADOW (insufficient days) |
| VIX term-structure gate | n/a (gate) | see ledger | 1 | CONTINUE SHADOW (needs a backwardation episode to differentiate) |

## Committee rules applied
- PROMOTE: unavailable during the 30-day window, and additionally requires reviewer!=author sign-off + human decision (pipeline gates).
- REJECT: forward shadow < 40% of research rate with >=15 shadow days, or adversarial-review failure (see ATR compression precedent).
- INVESTIGATE: expected>=3 trades in the clean window with zero observed.
- CONTINUE SHADOW: everything else -- the honest default this early.

_Regenerate anytime: python scripts/ops/evidence_report.py --committee_
