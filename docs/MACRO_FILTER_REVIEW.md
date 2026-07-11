# MACRO FILTER REVIEW -- incremental value over existing gates (2026-07-12)

_The 5 existing candidates from state/macro_daily.csv, each applied ON TOP of the
existing live gate (VIX-level pause), LAGGED one day, canonical rules, no threshold
search. Engine: S5 on QQQ 2019-2026 (the only strategy frequent enough to
differentiate gates). Baseline: existing gate alone = Sharpe 0.78, 186 trades,
6-split OOS min 0.75. No production changes._

| candidate (risk-ON rule) | Sharpe | trades | beats baseline (6 splits) | regime flips | VERDICT |
|---|---|---|---|---|---|
| VIX term structure (contango>1) | 0.81 | 173 | **6/6** | 113 | **CORROBORATED** -- consistent small increment, keeps 93% of trades. Already VALIDATED_FOR_FORWARD_SHADOW (EXP-20260711-01); this is a third independent confirmation. No new action -- the shadow decides. |
| DXY < 200dMA | 0.91 | 78 | **6/6** | 75 | **NEEDS_MORE_EVIDENCE** -- best Sharpe and 6/6, and NOT redundant (phi vs VIX-calm -0.08, vs contango +0.08; only 44% agreement). BUT: cuts trades 58% (186->78), and the ON-regime is era-lumpy (2020: 70%, 2022: 8%, 2025: 82%) -- the splits are nested, so 6/6 may be one macro era. Requires the full adversarial battery (leave-one-year-out, 2x costs, episode attribution) before even shadow status. Halving trade count also halves prop-challenge pace -- an economic cost even if Sharpe holds. |
| Yield curve > 0 | 0.59 | 119 | 0/6 | 35 | **REJECT** -- degrades baseline everywhere; essentially one inversion era of variation. Redundant with nothing because it adds nothing. |
| Net liquidity rising | 0.82 | 73 | 0/6 | 145 | **REJECT** -- headline Sharpe is a full-sample artifact; loses to baseline on ALL 6 OOS splits while discarding 61% of trades. The Part-B segmentation promise did not survive the gate test (exactly why segmentation != edge). |
| HY credit spread calm | 0.26 | 62 | 0/6 | 30 | **REJECT** -- destroys the strategy (0.78 -> 0.26). The frequency mismatch called out in the macro survey is confirmed empirically. |

## Redundancy findings
- The two 6/6 candidates (ts, DXY) are mutually non-redundant AND non-redundant
  with the existing VIX gate (all pairwise phi < 0.1) -- they carve different days.
- curve / netliq / HY are rejected on performance, making their redundancy moot.

## Net outcome
- **No new gate is adopted or advanced today.** ts-gate: already in forward shadow --
  this review simply corroborates it. DXY: parked as NEEDS_MORE_EVIDENCE with the
  required battery named; it is NOT queued during the evidence month (no new
  experiments per standing directive) -- it goes to the post-window backlog.
- Three candidates move to the graveyard as gates: curve, net liquidity, HY spreads
  (as entry gates on this book -- their segmentation stats in Part B stand as
  descriptive facts, not tradeable filters).
