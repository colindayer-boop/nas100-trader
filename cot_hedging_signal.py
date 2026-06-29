"""
cot_hedging_signal.py — THE breakthrough lead (2026-06-29). Tests the hedging-
pressure intuition with FREE CFTC Commitment-of-Traders data.

FINDING (legacy COT 2000-2022):
  CRUDE OIL: when commercial hedgers are EXTREME LONG (top-20% of 3yr positioning),
    forward 4-week return = +3.44% (67% win, n=58) vs +0.16% when extreme short.
    Spread +3.28% — REAL hedging-pressure signal, exactly as theory predicts.
  NATGAS: inverted (-1.99% spread) — different hedging structure, signal flips.

STATUS: promising SIGNAL, not yet a validated strategy. Next steps:
  1. Extend data to 2026 (newer CFTC feed) — confirm it hasn't decayed.
  2. Build into a tradeable long/flat strategy (long oil when commercials extreme
     long), costs on, full IS/OOS gauntlet.
  3. Check correlation to the equity book (should be ~0 → genuine diversifier).
  4. If it holds, this is a FREE-DATA commodity edge from first-principles intuition.

Data: CFTC Socrata API resource 6dca-aqww (legacy futures-only COT).
See conversation 2026-06-29 for the exploratory run + numbers.
"""
print(__doc__)
