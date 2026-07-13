# STRATEGY VALIDATION AUDIT #2 -- Weekend Exposure

_2026-07-13. Read-only. No production/strategy/exit change. A = current (hold to
stop/target/time-exit across Friday). B = force-close every position at Friday
15:59 ET, no new exit invented, re-enter only on a fresh signal. Full 7y QQQ
history. Archetypes measured: S1/S5 = bracket-hold (QQQ hourly), S3 = time-exit
(QQQ daily). Costs: 3 bps/side slippage both; CFD financing overlay 3 bps/day on
notional INCLUDING the weekend (ETF long = no financing)._

## Results (A hold vs B Friday-close)

| strat/mode | CAGR | Sharpe | PF | MaxDD | Win | AvgR | N | wknd-held | wknd-gap P&L | CFD fin (7y) |
|---|---|---|---|---|---|---|---|---|---|---|
| **S5 A hold** | **+8.7%** | **0.88** | **1.67** | -14.5% | 35.8% | +0.432 | 380 | 179 | **+15,894** | 5,673 |
| S5 B fri-close | +6.2% | 0.72 | 1.49 | -12.2% | 47.3% | +0.227 | 526 | 0 | 0 | 2,480 |
| **S1 A hold** | +1.1% | 0.23 | 1.52 | -10.2% | 33.6% | +0.342 | 146 | 105 | +5,903 | 2,224 |
| S1 B fri-close | +0.0% | 0.03 | 1.22 | -7.1% | 52.5% | +0.081 | 284 | 0 | 0 | 721 |
| S3 A hold | -0.4% | -0.20 | 1.03 | -6.2% | 53.4% | +0.020 | 73 | 58 | +892 | 259 |
| **S3 B fri-close** | **+0.1%** | **+0.06** | **1.24** | -5.2% | 57.7% | +0.109 | 78 | 21 | -32 | 166 |

## Weekend-gap breach tail (prop 5% daily limit, at each strategy's notional)
| strat | notional/eq | worst adverse Fri->Mon gap | >5% daily breaches in 7y | mean weekend gap |
|---|---|---|---|---|
| S5 | ~75% | **-4.09% equity** | **0 / 373 weekends** | +0.00% (edge from selection, not drift) |
| S1 | ~47% | -2.56% equity | 0 / 373 | +0.00% |

Raw QQQ Fri->Mon gap over 7y: mean -0.008%, median **+0.069%**, worst -5.46% (COVID
Feb-2020), best +4.02%. Unconditional weekend drift is ~zero; S5's +15,894 gap P&L
is CONDITIONAL -- it only holds over weekends when already in a bullish breakout, so
its held-weekend gaps inherit up-momentum. The edge is selection, not free drift.

## Findings

**Benefits from weekend exposure -- S5 (bracket momentum).** Holding across Friday
is the difference between Sharpe 0.88 and 0.72; the weekend contributes +15,894 of
P&L. Force-closing churns the book (380 -> 526 trades, avg R halves) and discards
the momentum-continuation edge. Statistically and economically meaningful.

**Marginally benefits -- S1 (and by archetype S4, same bracket structure).** Weekend
gap adds +5,903 and the hold version dominates, but S1 itself is weak (CAGR ~1%);
the weekend effect is real-signed but not strongly meaningful on a thin base.

**Harmed by weekend exposure -- S3 (time-exit).** Force-closing Friday flips S3 from
dead (Sharpe -0.20, PF 1.03) to marginally alive (+0.06, PF 1.24). But S3 is near-
zero either way and already under a provenance-drift review; this is not a standalone
weekend result -- fold into the existing S3 committee decision, do not act alone.

**Does CFD financing change the conclusion?** No, not for S5/S1. Weekend financing
adds ~3,200 (S5) / ~1,500 (S1) of cost over 7y, but the weekend GAP contribution
(+15,894 / +5,903) exceeds it several-fold -- net weekend exposure stays positive on
CFD. For S3, financing reinforces force-close (cost with zero offsetting edge).

**ETF vs CFD.** ETF long positions carry NO daily financing, so weekend holding is
strictly more favorable on Alpaca than on MT5. The financing drag only exists on the
CFD (MT5) side, and even there it does not flip S5/S1. The two venues AGREE on the
direction for every strategy; they differ only in magnitude.

## Recommendation (evidence only -- production frozen, window running)
- **S5: KEEP weekend exposure.** Benefit is meaningful; breach tail acceptable
  (worst historical weekend -4.09% eq, 0/373 breaches of the 5% limit -- but note a
  gap worse than the 7y max could breach; it is the single largest weekend risk in
  the book and belongs on the committee's risk sheet).
- **S1 / S4: KEEP current (no change).** Weekend effect positive but not strongly
  meaningful; force-closing would cost a little for no robustness gain.
- **S3: defer to the existing S3 committee decision** (already flagged for provenance
  drift); weekend force-close is a point in favor of retiring/revising, not a
  separate action.
- **S2 (daily-FVG gold): NOT separately measured.** Bracket archetype, but gold
  weekend gaps are geopolitically driven and differ from equity -- do not generalize
  the QQQ result; measure before any decision.
- **Crypto (BTC/BTCTREND/XSMOM): out of scope.** 24/7 with continuous financing and
  no discrete Friday close; "force-close Friday" is an arbitrary exposure cut, not a
  gap-risk fix.

No production change. Any action waits for the 2026-08-16 committee.
