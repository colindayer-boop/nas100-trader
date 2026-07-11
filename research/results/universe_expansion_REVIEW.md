# ETF universe expansion — ADVERSARIAL REVIEW + independence

_11 keeper streams, 2021+. Streams persisted to etf_streams.csv._

## R1/R3/R4 — per-keeper attack table
| stream | Sharpe | 6bps | ex-best-yr | min 6-split OOS | verdict |
|---|---|---|---|---|---|
| S1_QQQ | 0.58 | 0.50 | 0.30 | 0.08 | FAILS review |
| S1_SMH | 0.63 | 0.53 | 0.38 | 0.63 | SURVIVES |
| S1_XLK | 0.88 | 0.80 | 0.73 | 0.66 | SURVIVES |
| S1_GLD | 0.67 | 0.60 | 0.46 | 0.88 | SURVIVES |
| S5_QQQ | 1.10 | 0.88 | 0.92 | 1.44 | SURVIVES |
| S5_SPY | 0.76 | 0.56 | 0.55 | 0.64 | SURVIVES |
| S5_DIA | 0.81 | 0.63 | 0.67 | 0.67 | SURVIVES |
| S5_SMH | 2.04 | 1.80 | 1.96 | 2.36 | SURVIVES |
| S5_SOXX | 1.41 | 1.16 | 1.15 | 1.16 | SURVIVES |
| S5_XLF | 0.76 | 0.56 | 0.58 | 0.34 | SURVIVES |
| S5_XLE | 1.28 | 1.05 | 1.11 | 1.24 | SURVIVES |

## R2 — keeper-pairwise correlation (independence measurement)
- survivors: 10 | avg pairwise corr **0.13** | pairs >0.5: S5_SMH~S5_SOXX (0.56)
- de-duplicated set (9): ['S1_SMH', 'S1_XLK', 'S1_GLD', 'S5_QQQ', 'S5_SPY', 'S5_DIA', 'S5_SMH', 'S5_XLF', 'S5_XLE'] | dropped: ['S5_SOXX']

## R5 — honest pooled portfolio (de-duplicated survivors)
- pooled Sharpe (equal weight, zero on inactive days): **2.26** | active days 100% | MaxDD -3.4%
- pooled 6-split OOS Sharpe: 2.77 3.13 3.00 3.00 2.92 2.82 | min 2.77

## Verdict: **VALIDATED_FOR_FORWARD_SHADOW**
Conditions: forward-shadow every survivor (no live orders); 2021+ sample and OOS>IS tilt remain open concerns that only forward evidence resolves; CFD-mapped subset (QQQ/SPY/DIA/GLD) is the only prop-relevant portion.
