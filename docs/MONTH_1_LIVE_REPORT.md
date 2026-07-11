# MONTH 1 LIVE REPORT -- generated 2026-07-12 01:14

_Single source of truth: research expectation vs forward shadow vs live execution. Verdicts: FAILS_FORWARD_EVIDENCE -> rejected; PASSES -> queued for post-window human review. This script promotes NOTHING to live._

## Candidate: ETF universe expansion (9 survivors, forward shadow)

_1 shadow days._

| stream | research act-rate/day | shadow rate/day | ratio | verdict |
|---|---|---|---|---|
| S1_GLD | 0.05 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S1_SMH | 0.09 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S1_XLK | 0.07 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S5_DIA | 0.13 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S5_QQQ | 0.19 | 1.00 |  | EXTEND (insufficient days or no expectation) |
| S5_SMH | 0.26 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S5_SPY | 0.15 | 1.00 |  | EXTEND (insufficient days or no expectation) |
| S5_XLE | 0.22 | 0.00 |  | EXTEND (insufficient days or no expectation) |
| S5_XLF | 0.16 | 0.00 |  | EXTEND (insufficient days or no expectation) |

## Candidate: VIX term-structure gate (shadow)
- 1 gate-days logged; level-vs-ts agreement 100%; ts blocked 0 day(s), level blocked 0.
- Verdict: EXTEND unless a backwardation episode occurs in-window (no stress episode = shadow cannot differentiate; do not promote on quiet data).

## Live execution vs research costs
_No fills on this host. MT5 fills live on the VPS ledger -- merge logs/fills.csv from the VPS before finalizing the go/no-go._

## Decision inputs (human)
- Ops ledger: docs/EVIDENCE_LEDGER.md
- Parity/monitoring: NEXT_30_DAY_MONITORING_PLAN section 4 criteria
- NOTHING here changes production; promotion requires human sign-off post-window.
