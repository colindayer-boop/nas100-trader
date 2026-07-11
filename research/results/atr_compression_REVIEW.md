# ADVERSARIAL REVIEW — 'ATR compression filter' (claim: S1 compressed_only 2.04 vs 1.12)

_All thresholds reported (0.25 was selected post-hoc by the original analysis;
its report simultaneously found compression is NOT a breakout signal, ratio 0.83x).
atr_pctl LAGGED one day here (original used same-day). Base engine = validated S1._

Baseline S1 (no compression filter): Sharpe 0.65, trades 136

## T2/T3 — threshold sweep + trade counts (full sample, 3 bps)
| threshold pctl | Sharpe | trades | trades kept % |
|---|---|---|---|
| <10% | 0.05 | 22 | 16% |
| <15% | 0.35 | 29 | 21% |
| <20% | 0.59 | 32 | 24% |
| <25% | 0.35 | 39 | 29% |
| <30% | 0.25 | 42 | 31% |
| <35% | 0.30 | 44 | 32% |
| <40% | 0.35 | 46 | 34% |
| <50% | 0.33 | 57 | 42% |

## T1 — rolling walk-forward (expanding 6 tail-splits), compressed<0.25 vs baseline
| split | base OOS | filt OOS |
|---|---|---|
| 0.45 | 0.59 | 0.47 |
| 0.50 | 0.62 | 0.54 |
| 0.55 | 0.79 | 0.74 |
| 0.60 | 0.70 | 0.52 |
| 0.65 | 0.88 | 0.64 |
| 0.70 | 0.64 | 0.41 |
filter beats baseline on 0/6 splits

## T4/T5 — interaction & incremental information (Sharpe after existing gates, 3 bps)
| combo | Sharpe | trades |
|---|---|---|
| VIX level gate only | 0.55 | 90 |
| VIX + compression<0.25 | 0.38 | 28 |
| TS gate only | 0.65 | 133 |
| TS + compression<0.25 | 0.35 | 39 |
| GEX gate only (to 2023-12) | 0.63 | 68 |
| GEX + compression (to 2023-12) | 0.61 | 23 |
(HighVol gate is already inside S1 -- compression is tested on top of it by construction.)

## T6 — leave-one-year-out (compressed<0.25 minus baseline Sharpe)
| excluded year | base | filt | delta |
|---|---|---|---|
| 2019 | 0.48 | 0.35 | -0.13 |
| 2020 | 0.71 | 0.38 | -0.32 |
| 2021 | 0.70 | 0.42 | -0.28 |
| 2022 | 0.78 | 0.45 | -0.33 |
| 2023 | 0.61 | 0.19 | -0.42 |
| 2024 | 0.53 | 0.45 | -0.08 |
| 2025 | 0.68 | 0.22 | -0.46 |
| 2026 | 0.70 | 0.38 | -0.32 |

## T7 — doubled costs (6 bps/side), compressed<0.25 vs baseline
baseline 0.57 (136 tr) vs filtered 0.30 (39 tr)

## Verdict: **REJECT**

Every falsification test failed the claim:
1. With LAGGED (information-correct) ATR percentile, compression HURTS at ALL 8
   thresholds (best <20% = 0.59 vs baseline 0.65); the claimed 2.04 is unreproducible.
2. Walk-forward: 0/6 splits beat baseline.
3. Trade counts collapse to 16-42% of baseline (starves the edge).
4. Interaction: compression REDUCES Sharpe after every existing gate
   (VIX 0.55->0.38, TS 0.65->0.35, GEX 0.63->0.61) -- zero incremental information.
5. Leave-one-year-out: delta NEGATIVE in all 8 exclusions (-0.08 to -0.46) --
   the harm is uniform, not episode-driven.
6. Doubled costs: gap widens (0.57 vs 0.30).

Root causes of the original 2.04-vs-1.12: same-day (look-ahead) ATR percentile,
post-hoc selection of "best filter" among candidates, and per-trade bucketing
instead of portfolio Sharpe. Its own report contradicted itself (compression NOT
a breakout signal, ratio 0.83x) -- the contradiction was correct; the
recommendation was not. Do not adopt. Do not re-test (graveyard).
