---
type: experiment
id: EXP-20260711-01
title: "VIX term structure regime gate on S1 and S5"
status: validated          # promoted 2026-07-11
created: 2026-07-11
idea: "2026-07-11-vix-term-structure-regime-gate"
paper: "vix-futures-as-a-market-timing-indicator-fassas-2019"
datasets: "qqq_hourly_7y.csv + Alpaca splice, yfinance ^VIX ^VIX3M daily"
script: ""              # set when the test script exists in research/experiments/
reviewer: "adversarial-review-2026-07-11"
author: "claude-research"
tags: [research, experiment]
---
# EXP-20260711-01 - VIX term structure regime gate on S1 and S5

## Origin
- Idea:  [[2026-07-11-vix-term-structure-regime-gate]]
- Paper: [[vix-futures-as-a-market-timing-indicator-fassas-2019]]

## Hypothesis
Gating on VIX3M/VIX contango/backwardation adds risk-adjusted value OVER the existing VIX-level gate on S1/S5.

## Success criteria (write BEFORE running -- the gauntlet, non-negotiable)
- [ ] IS/OOS walk-forward, costs ON
- [ ] OOS Sharpe > 0.5 and IS Sharpe > 0
- [ ] OOS max DD > -35%, >= 30 OOS trades
- [ ] |corr to QQQ weekly| < 0.3
- [ ] Positive/flat in the 2022 bear sub-period
- [ ] 6/6 IS/OOS split robustness (edge_hunt --sweep style)
- [ ] Extra criteria specific to this experiment:

## Datasets
- qqq_hourly_7y.csv + Alpaca splice
- yfinance ^VIX ^VIX3M daily

## Backtests (fill as they run)
| date | script | split | IS Sharpe | OOS Sharpe | OOS DD | trades | corr | verdict |
|---|---|---|---|---|---|---|---|---|
| 2026-07-11 | vix_ts_gate_test.py | 6 splits | see results | S1: C 0.61 vs B 0.81 (0/6) | -7.4% | 135 | n/a | S1: NO incremental value |
| 2026-07-11 | vix_ts_gate_test.py | 6 splits | see results | S5: C 1.50 vs B 1.04 (6/6 splits) | -8.3% | 333 | n/a | S5: C BEATS level gate on all splits; A also beats B 6/6 |

## Verdict
MIXED, awaiting reviewer: S1 -> reject (term-structure adds zero over level gate; backwardation days largely subsumed by VIX>25). S5 -> two findings needing adversarial review: (1) term-structure gate beats the level gate on ALL 6 splits (Sharpe 1.50 vs 1.04, DD -8.3% vs baseline -13.4%); (2) the CURRENT live VIX-level pause HURTS S5 (baseline 1.32 > gated 1.04 on 6/6). Full table: research/results/vix_term_structure_gate.md. Caveats: single instrument, 2018-2026 (backwardation only 8% of days = few independent stress episodes), any change is live-strategy surgery -> POST-WINDOW + reviewer + human only.

## Reviewer sign-off
- reviewer: adversarial-review-2026-07-11 (Claude reviewer session; model-diversity caveat noted)
- date: 2026-07-11
- notes: VALIDATED_FOR_FORWARD_SHADOW. Look-ahead found+corrected (C 1.50->1.39, still >B 6/6); survives ex-COVID/ex-2022/ex-best-year, 2x costs, threshold sensitivity. Level gate confirmed HARMFUL to S5. See research/results/vix_ts_gate_REVIEW.md. No live change during window.

## Links
[[Research Index]] | [[02-Strategy-Research/Gauntlet|Gauntlet]] | [[00 Dashboard]]
