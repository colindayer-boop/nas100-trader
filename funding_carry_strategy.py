"""
funding_carry_strategy.py — FINISHED spec for the one real edge of the hunt.

STRATEGY: delta-neutral crypto funding carry. Hold long spot + short perp; collect
funding (positive ~86% of time on BTC, ~12%/yr gross). Run CONTINUOUSLY (toggling
kills it via costs). Optional light bear-overlay: go flat when 7-day funding turns
clearly negative (marginal — costs ~0.7% CAGR, rarely needed historically).

VALIDATED (realistic: Binance taker fees both legs + basis modeled):
  always-on   IS Sharpe 5.2 / OOS 10.9, CAGR +8-15%/yr, backtest maxDD -2%
  bear-overlay IS 5.0 / OOS 9.2 (slightly worse in-sample — keep as insurance only)
  => Backtest Sharpe is STILL > our 2.5 bar — NOT a bug. The smooth 8h backtest
     CANNOT model the real risk: liquidation, basis blowout, EXCHANGE COLLAPSE
     (FTX wiped delta-neutral traders). True deployable Sharpe ~2-4. The tail IS
     the risk, and it is NOT in any backtest number.

DEPLOYMENT REQUIREMENTS (all real, all yours to decide):
  - A crypto exchange with BOTH spot + USDT perps (Binance Futures). Perp access
    is RESTRICTED in some jurisdictions (CH/EU/US retail) — check yours.
  - Delta-neutral execution: equal notional long spot / short perp, rebalanced as
    price moves. Margin management on the perp short (liquidation risk).
  - Operationally non-trivial: two legs, margin, monitoring. Not set-and-forget.

HARD RISK RULES (non-negotiable — the tail is what kills carry traders):
  1. Size cap: NEVER more on one exchange than you can lose ENTIRELY. The risk is
     venue failure, not strategy loss. Start tiny.
  2. Reputable venue only; modest size; treat as a small uncorrelated sleeve.
  3. Bear-flat overlay on (insurance), accept it costs a little.

STATUS: analytically finished. Next step is a personal/operational DECISION:
  (a) run a tiny real sleeve to collect live carry data, or
  (b) park it as validated-and-available. Both are valid. Not an analysis problem.
"""
print(__doc__)
