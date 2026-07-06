# The Gauntlet

Every candidate must clear ALL of these (see `edge_hunt.py`, `EDGE_HUNT_BRIEF.md`):

1. IS/OOS walk-forward split, never optimize on OOS
2. Costs ON (equities ~4bps, crypto ~10bps, commodities ~15bps)
3. OOS Sharpe > 0.5
4. OOS max drawdown > -35%
5. OOS Sharpe < 2.5 (higher = look-ahead bug, find it)
6. Not overfit: OOS <= IS*1.3 + 0.5
7. >= 30 OOS trades
8. IS Sharpe > 0 (works in BOTH periods)
9. |corr to QQQ weekly| < 0.3 (real diversifier)
10. **Robustness: passes 6/6 IS/OOS split dates** (`--sweep`). 4/6 = split-luck = reject.

Anti-overfitting: a-priori params only; report ALL param sets, not the winner;
conditional averages lie, only tradeable strategies with costs count.

Back: [[02-Strategy-Research/_index|Strategy Research]]
