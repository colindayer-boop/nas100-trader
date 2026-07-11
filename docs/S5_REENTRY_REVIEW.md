# S5 SAME-DAY RE-ENTRY REVIEW -- the last unquantified live/research divergence

_2026-07-12. Full 7.5-year S5 replay (QQQ hourly + fresh splice), identical engine,
identical sizing/exits/costs; ONLY the entry cap differs. Run A = research (one
entry/day). Run B = live semantics (re-enter whenever flat and a new valid
breakout bar prints -- covers both after-stop and after-target)._

## Head-to-head

| metric | A (1/day) | B (live re-entry) | delta |
|---|---|---|---|
| trades/yr | 50 | 52 | **+1.6/yr** |
| win rate | 35.4% | 35.2% | -0.2pp |
| avg R / expectancy | +0.418 | +0.409 | -0.009 |
| profit factor | 1.65 | 1.63 | -0.02 |
| Sharpe | 1.32 | 1.31 | -0.01 |
| CAGR | +14.0% | +14.0% | ~0 |
| MaxDD (3 bps) | -13.4% | **-11.8%** | re-entry path slightly SHALLOWER here |
| MaxDD (6 bps) | -14.1% | -14.7% | slightly deeper -- i.e., DD delta is path noise, not signal |

Cost sensitivity: at 6 bps/side the ordering is unchanged (1.11 vs 1.09).

## The extra trades themselves
- **12 extra entries in 7.5 years** (3% of all trades, ~1.6/yr).
- Their standalone stats: win 25%, **avgR +0.000 -- exactly breakeven**.
- **They DO cluster in volatile periods**: 75% occur on VIX21ma>=20 days (vs 51%
  of all trades) -- concentrated in 2020 (+6 trades, which HELPED: yearly avgR
  0.565->0.600) and 2022 (+3, which hurt slightly: -0.027->-0.065).
- Yearly table shows the effect is confined to those two regimes; all other years
  are trade-for-trade identical.

## Challenge drawdown risk
Worst-day exposure rises only on the rare double-entry days (~1.6/yr), each capped
by the same broker bracket. Max drawdown across both cost settings moves within
path noise (+1.6pp best case, -0.6pp worst case). No material increase in daily-
or max-DD breach probability at challenge sizing.

## Recommendation: **KEEP** (the live behavior; close the divergence as accepted)
The feared divergence quantifies to ~nil: breakeven extra trades, |Sharpe delta|
0.01, unchanged CAGR, DD within noise. A one-entry-per-day guard would be a
production change (clock reset) purchasing nothing measurable. Actions:
1. LIVE_TRADING_PARITY blocker #1 -> reclassified: QUANTIFIED & ACCEPTED (this doc).
2. The committee report keeps counting multi-entry days (evidence continues free).
3. Revisit ONLY if live multi-entry days exceed ~4/yr pace or occur outside
   high-VIX regimes (would indicate behavior drifting from this replay's model).
