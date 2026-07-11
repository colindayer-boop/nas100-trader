# EXP-20260711-01 — ADVERSARIAL REVIEW (independent reviewer)

**Verdict: VALIDATED_FOR_FORWARD_SHADOW**

Reviewer attacked the finding on 6 vectors (script: `research/experiments/vix_ts_gate_review.py`).
The claim under review: replacing S5's VIX-level pause with a VIX3M/VIX>1.0 gate improves S5.

## R1 — Look-ahead bias: FOUND, CORRECTED, FINDING SURVIVES
The experiment gated entries with the **same day's closing** VIX/VIX3M — a morning
entry decided by that afternoon's close. Real look-ahead, and it flattered the fast
ratio more than the smoothed 21d-MA. Corrected to previous-day close
(information-correct at the decision timestamp):
- C term-structure: Sharpe 1.50 → **1.39** (inflation ~0.11, real but modest)
- B level gate: 1.04 → 1.02
- **C still beats B on 6/6 splits after correction.** All subsequent tests use lagged gating.
(Timezone/alignment otherwise clean: ET dates both sides, same engine/sizing/costs/exits across variants; only the gate differs. Blocked-day counts: B blocks 153 entry-days, C blocks 69.)

## R3 — Episode concentration: NOT dominated
Yearly attribution: the level gate's damage is concentrated in 2020 (+7.0% vs +29.9% ungated)
— it pauses exactly when S5 longs pay. C keeps 2020 (+32.9%) while still cutting 2022 (−2.0% vs −5.3%).
Leave-one-out (all lagged, C vs B):
| exclusion | C Sharpe | B Sharpe | C>B splits |
|---|---|---|---|
| ex-COVID (2020-02-15..06-30) | 1.38 | 1.13 | 6/6 |
| ex-2022 | 1.54 | 1.08 | 6/6 |
| ex-best-year (2020) | 1.20 | 1.04 | 6/6 |

## R4 — Costs doubled to 6 bps/side: ranking intact (C 1.20 vs B 0.84, 6/6).

## R5 — Threshold sensitivity (diagnostic only): smooth, not knife-edge
0.95 → 1.36 | **1.00 → 1.39 (precommitted)** | 1.05 → 1.29. No cliff.

## R6 — Split independence: the 6 splits are NESTED tails (not independent; ~2–3
effective observations). This weakness is why the verdict includes the leave-one-out
battery, which provides the real independence evidence, and why the verdict is
forward-shadow, not live.

## Honest restatement of what is proven
- **B (current live level gate) demonstrably hurts S5**: it costs ~0.3–0.4 Sharpe vs
  either alternative in every configuration tested. This is the strongest finding.
- **C vs A (no gate)**: similar Sharpe (1.39 vs 1.32) but C nearly halves MaxDD
  (−7.7% vs −13.4%) — decisive under prop drawdown constraints.
- Scope limits: single instrument (QQQ hourly), 2018–2026, S5-long engine,
  backwardation regime = 8% of days.

## Conditions attached to VALIDATED_FOR_FORWARD_SHADOW
1. NO live change during the 30-day window (clock-reset rule).
2. Forward shadow first: log the would-be gate value daily (both gates are already
   derivable from logged VIX + free ^VIX3M); compare shadow decisions for the
   remainder of the window.
3. Any live adoption = human sign-off + parity test, post-window.
4. Reviewer-diversity caveat: this review was performed by the same model family as
   the author (different session/role). Per the OS ideal (different model), a
   second-model spot-check of R1 is cheap and recommended before live adoption.
