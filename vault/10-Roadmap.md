# 10 Roadmap

## Now (do nothing but watch)
- [ ] Let the core book accumulate a **clean month** on demo (execution now faithful).
- [ ] Weekly `status.py`; watch Telegram; S5 should be the first live trader.
- [ ] ~3-4 weeks: compare live vs backtest Sharpe -> **go/no-go for funding**.

## If edge confirms
- [ ] Fund 2-3 parallel FundedNext challenges ([[09 Prop Firms]]).
- [ ] Add Alpaca bracket orders; give BTCTREND/XSMOM broker stops.

## V2 engineering ([[ARCHITECTURE_V2]])
- [ ] `sessions.yaml` single source for schedulers.
- [ ] Strategy plugin contract (loader forbids naked).
- [ ] `MAX_OPEN_RISK` cap; CI gauntlet gate.

## Optional research
- [ ] DIX dark-pool regime filter (one CSV, gauntlet it).
- [ ] Futures data bridge: Databento (history) + Rithmic (live) for real NQ session.

## Do NOT
- Fund on unconfirmed edge. Add strategies while the well is dry. Tinker for its own sake.
