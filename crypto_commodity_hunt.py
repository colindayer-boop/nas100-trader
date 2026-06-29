"""
crypto_commodity_hunt.py — Record of the 2026-06-29 edge hunt beyond equities.
Findings (all tested with costs, IS/OOS, gauntlet):

  BTC Donchian trend (20/10 daily, 2017-26): REAL edge — OOS +119% through the
    2022 bear (not bull-beta). BUT maxDD -38% (-41% in 2022) → fails DD filter,
    unusable for prop. Candidate only for own-capital, vol-targeted down to ~10% DD.

  Natgas seasonal (long Oct-Dec / short Feb-Apr, NG=F 2000-26): DEAD. OOS -80%.
    The academic edge is in calendar SPREADS (curve), not flat price → needs paid
    curve data.

  Oil carry / term-structure (USO/USL proxy, long when backwardated): REAL but
    WEAK. Positive both periods (OOS +85%, Sharpe 0.36), crushes buy-hold on
    return AND drawdown (-30% vs -85%). Below the 0.5 Sharpe bar in this crude
    single-commodity ETF proxy. Proper version = cross-sectional carry on the
    curve (paid data), ~0.6-0.8 Sharpe in the literature.

  XS commodity momentum: raw yfinance futures = ROLL-ARTIFACT GARBAGE (-0.70).
    Clean-ETF version = flat (OOS Sharpe 0.20). Inconclusive — free commodity
    data is too dirty (futures) or too short/decayed (ETFs) to judge the factors.

VERDICT: the commodity factor space (carry especially) is the most promising
direction, but testing it properly is GATED ON PAID FUTURES-CURVE DATA. The free
proxies are suggestive (oil carry) but can't clear the bar. This is the one place
where buying data is genuinely justified — IF building a market-neutral commodity
sleeve is a real goal.

(This file documents the hunt. Re-running fetches fresh data; numbers move slightly.)
"""
print(__doc__)
