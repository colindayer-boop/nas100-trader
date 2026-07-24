# PROMOTION_CRITERIA — the rule before any strategy qualifies

Defined and enforced in `execution_safety/promotion_gate.py` (`can_promote`). A strategy may move
`NEEDS_REPLICATION → PAPER_APPROVED` **only** if it meets **every** criterion. Fail closed: missing
evidence ⇒ not eligible. No strategy is promoted for being exciting.

| criterion | threshold |
|--|--|
| independent time periods replicated | ≥ 2 |
| Sharpe (after costs) | ≥ 0.5 |
| effect CI excludes zero | required |
| validated after realistic costs | required |
| shadow signals observed | ≥ 100 |
| shadow calendar days | ≥ 30 |
| unresolved operational issues | 0 |
| frozen deployable `code_commit` | required |
| prop-firm simulation for target firm | required |

The rule is versioned in code and change-controlled; lowering a threshold is itself a reviewable event.

## GSR today → NOT eligible
```
independent periods: 1  (need ≥2)   shadow signals: 0 (need ≥100)   shadow days: 0 (need ≥30)
frozen code_commit: none            prop-firm simulation: none
```
GSR is a real replicated edge (Sharpe 1.43, internal) but stays `NEEDS_REPLICATION` until it clears
all of the above — and note it is a ~2-trade/year compounder that structurally cannot pass a prop
challenge, so any prop-firm simulation must reflect that.

## The full pipeline (no exceptions)
Research → Belief Graph → Shadow → **Promotion rule** → Capital Allocation → Demo → Live.
