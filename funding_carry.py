"""
funding_carry.py — Crypto perp funding-rate carry. THE one real edge the hunt found.
Delta-neutral (long spot / short perp) collects funding (positive ~85% of time,
~12%/yr on BTC). REAL and uncorrelated — BUT the idealized Sharpe (~17-25) is
frictionless fantasy. After fees/basis/execution, realistic Sharpe ~2-4, ~5-10%/yr.
Toggling on/off fails (costs eat carry) — must run CONTINUOUSLY.

CRITICAL RISKS (why carry traders blow up):
  - Exchange/counterparty (FTX 2022 wiped delta-neutral traders)
  - Liquidation on the perp short; basis blowups in crashes
  - Two-leg operational complexity, margin management
  - Perp access restricted in some jurisdictions (CH/EU/US)
Data: Binance fapi /fapi/v1/fundingRate (free). See conversation 2026-06-30.
"""
print(__doc__)
