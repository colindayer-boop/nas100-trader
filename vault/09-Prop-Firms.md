# 09 Prop Firms

Goal: pass a challenge for supplementary income. Optimize for SURVIVAL, not Sharpe.

## Book that ports to prop (CFD, cross-asset)
US100 (sweep/ORB) + XAUUSD (gold) + BTC. US single stocks do NOT trade on prop.

## FundedNext / FTMO math (`prop_sim.py`)
- Rules: +8% target, 10% max DD, 5% daily, consistency rule, min days.
- Dominant failure = **timeout** (not blow-up) at safe sizing.
- Consistency rule costs ~5 pts.
- Pass odds @16% vol, Sharpe 1.2: 1mo ~13%, 2mo ~35%, 3mo ~50%, 6mo ~70%.
- Sweet spot ~16-20% vol (best pass net of blow-up).

## Plan
2-3 **parallel** $25-50k Stellar 2-Step challenges at ~2x -> ~68-82% funded within
~3-4 months, <$1k total fees. Fund ONLY after live edge confirms ([[10 Roadmap]]).

Related: [[04 Risk Engine]], [[01 Trading Philosophy]]
