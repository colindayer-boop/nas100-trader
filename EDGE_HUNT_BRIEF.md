# OVERNIGHT EDGE-HUNT BRIEF

You are an autonomous quant researcher. Goal: find **ONE** new trading edge that
**passes the gauntlet below** and is **uncorrelated** to the existing book.
Expect to REJECT almost everything — that is correct. A night that rejects 20
ideas honestly is a SUCCESS. Do NOT return an exciting result that fails the
gauntlet. Do NOT loosen the gauntlet to make something pass.

Work in `/Users/colindayer/nas100_backtest`. Write each test as a `.py` script,
run it, log the result to `HUNT_LOG.md` (one row per idea). Commit scripts.

## THE GAUNTLET (every candidate must pass ALL of these)
1. Split data IS (older ~60%) vs OOS (newer ~40%). **NEVER optimize on OOS.**
2. Costs ON (equities/ETF ~0.04% round trip; crypto ~0.10%; commodities ~0.15%).
3. OOS Sharpe > 0.5
4. OOS max drawdown > -35%
5. OOS Sharpe < 2.5 (above this = a bug or look-ahead — find it)
6. Not overfit: OOS Sharpe <= IS Sharpe * 1.3 + 0.5
7. >= 30 trades in OOS
8. **IS Sharpe > 0** (must work in BOTH periods — kills regime-dependent illusions)
9. **|correlation to QQQ weekly returns| < 0.3** (must be a real diversifier)
10. **Regime check:** must be positive (or flat) in BOTH a bull sub-period AND a
    bear sub-period (e.g. 2022). If it only works in bulls, REJECT — it's beta.

## ANTI-OVERFITTING RULES (hard-won — violate none)
- Use **a-priori parameters** (canonical values: RSI-2, 20/10 Donchian, 12-1
  momentum, top/bottom tercile). Do NOT grid-search params then report the best.
- If you test N parameter sets, the bar rises — report ALL, not the winner.
- A signal that looks great as a *conditional average* (e.g. "+3% after signal X")
  must be rebuilt as an actual *tradeable strategy* with entries/exits/costs/OOS.
  Conditional averages lie; tradeable strategies don't.
- In-sample stats (bootstrap/MC/permutation) do NOT validate — only walk-forward
  OOS does. A great in-sample log on an optimized strategy proves nothing.
- Tiny samples (<30 trades) = noise. Do not trust.

## DATA SOURCES THAT WORK (and traps)
- Equities/ETFs: `yfinance` daily/hourly (hourly = last 730d only). CLEAN.
- Crypto: Binance public klines `api.binance.com/api/v3/klines` (no key). CLEAN,
  back to 2017. Also funding rates: `fapi.binance.com/fapi/v1/fundingRate`.
- COT: CFTC `publicreporting.cftc.gov` (free). Disaggregated = resource 72hh-3qpy.
- **TRAP:** raw futures continuous (`CL=F` etc.) from yfinance have ROLL ARTIFACTS
  that corrupt returns. Use ETFs (clean) or skip. We already proved this fails.
- **TRAP:** commodity COT factor — already exhausted, decayed OOS. Skip it.

## EXISTING BOOK (what to be uncorrelated to)
Intraday long-biased Nasdaq momentum (Asian sweep, ORB, abnormal-volume on QQQ/
SPY/gold) + BTC Asian sweep. New edge should NOT be another Nasdaq breakout.

## PRIORITIZED HYPOTHESIS LIST (test in this order — best mechanisms first)
1. **Crypto perp funding-rate carry** — long spot / short perp when funding is
   persistently positive, collect funding. REAL, persistent, retail-accessible.
   Binance funding history is free. THIS IS THE TOP CANDIDATE.
2. **Overnight-drift anomaly** — buy SPY/QQQ at close, sell at next open vs the
   reverse (intraday). Documented: most equity return is overnight. Free, daily.
3. **Turn-of-month effect** — long equity index last 1-2 + first 3 trading days
   of month, flat else. Documented calendar anomaly. Free.
4. **Crypto time-of-day / weekend effect** — systematic return patterns by UTC
   hour / weekend on BTC/ETH. Free hourly data.
5. **Cross-sectional crypto momentum** — rank top-10 liquid coins by 30d return,
   long top / short bottom, weekly. Crypto trends hard.
6. **Pairs / stat-arb** — z-score mean-reversion on cointegrated ETF pairs
   (e.g. GLD/GDX, XLE/USO, EWA/EWC). Market-neutral.
7. **Low-vol / defensive rotation** — USMV/SPLV vs SPY in high-VIX regimes.

## OUTPUT
- `HUNT_LOG.md`: table — idea | IS Sharpe | OOS Sharpe | OOS DD | trades | corr |
  PASS/FAIL | one-line why.
- For any PASS: write a clear summary, the script, and **flag it for human
  re-verification** (be suspicious of your own passes — re-run with different
  IS/OOS split dates to confirm it's not split-luck).
- End with an honest summary: "Tested N, rejected M, K candidates survived
  (flagged for review)." If K=0, say so plainly — that is a valid, good result.
