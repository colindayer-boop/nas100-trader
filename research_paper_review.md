# Academic Research Paper Review: Trading Strategies (2021–2026)

**Search methodology:** 12 queries across Google Scholar, arXiv (q-fin), SSRN, Springer, MDPI, IEEE, PLoS, Taylor & Francis, Wiley, Elsevier.  
**Filtering criteria:** Rigorous OOS testing + transaction costs required. Papers lacking either are rejected or flagged.

---

## ▶ QUALIFYING PAPERS (Meet Minimum Bar)

---

### PAPER 1: Sharpe-Optimal Volatility Futures Carry

| Field | Detail |
|---|---|
| **Title** | Sharpe-optimal volatility futures carry |
| **Authors** | Benedikt Uhl |
| **Year** | 2024 |
| **Source** | Journal of Asset Management (Springer) |
| **Asset class** | VIX futures (volatility) |
| **Trading horizon** | Daily rebalancing |
| **Entry logic** | Carry signal from VIX futures term structure; Markowitz-optimization (Pedersen et al. 2021 framework) to find Sharpe-optimal portfolio across full VIX term structure |
| **Exit logic** | Dynamic rebalancing when carry forecasts change; positions adjusted daily |
| **Risk management** | Volatility targeting; Markowitz shrinkage to avoid overfitting; robust parameter choices |
| **Holding period** | Variable (daily turnover) |
| **Markets tested** | VIX futures (UX1–UXn), 2006–2023 |
| **Sample period** | ~2006–2023 |
| **Number of trades** | Not explicitly stated (daily rebalancing) |
| **Sharpe ratio** | ~1.0–1.3 (net of costs, OOS) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated but described as moderate vs. short-VIX buy-and-hold |
| **Transaction costs** | **Y** — 10 bps per trade (tick-based estimate), roll costs included |
| **Walk-forward** | Y (OOS with rolling window) |
| **Out-of-sample** | **Y** — extensive OOS tests |
| **Cross-validation** | N (robustness via parameter sensitivity) |
| **Code available** | **N** |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 4/10 (VIX futures only; prop firms often restrict vol products) |
| **Live-trading suitability** | 6/10 (liquid VIX futures, but tail risk extreme) |
| **Main weaknesses** | VIX can spike violently (Volmageddon-type events); correlation with equity drawdowns; only one asset class |
| **Why it might fail** | Extreme contango-to-backwardation regime shifts; VIX futures liquidity under stress |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 8/10 | 32 |
| Replication Quality | 20% | 6/10 | 12 |
| Economic Plausibility | 15% | 8/10 | 12 |
| Implementation Simplicity | 10% | 6/10 | 6 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 4/10 | 2 |
| **TOTAL** | | | **70/100** |

---

### PAPER 2: Carry Momentum (Combined Factor Strategy)

| Field | Detail |
|---|---|
| **Title** | Carry Momentum |
| **Authors** | James Davis, Miles Dorsten, Nicolas Gillmann, Jeffrey Tsai |
| **Year** | 2022 |
| **Source** | Financial Analysts Journal (Taylor & Francis) |
| **Asset class** | 21 commodity futures (aluminum, Brent oil, copper, corn, gold, etc.) |
| **Trading horizon** | Monthly rebalancing |
| **Entry logic** | Combines time-series momentum signal with carry signal (roll yield); long assets with positive momentum + positive carry, short negative |
| **Exit logic** | Monthly rebalance reverses positions when signals flip |
| **Risk management** | Volatility scaling; robustness section examines transaction cost impact |
| **Holding period** | ~1 month (monthly rebalancing) |
| **Markets tested** | 21 commodity futures |
| **Sample period** | ~1990–2020 |
| **Number of trades** | Not stated (monthly) |
| **Sharpe ratio** | ~1.0–1.2 (net of transaction costs) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated |
| **Transaction costs** | **Y** — robustness section with explicit cost analysis |
| **Walk-forward** | Partial (OOS tests) |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 5/10 |
| **Prop-firm compatibility** | 6/10 (commodity futures are common at prop firms) |
| **Live-trading suitability** | 7/10 (liquid markets, monthly frequency) |
| **Main weaknesses** | Monthly frequency misses intraday opportunities; momentum crashes in regime shifts; well-known factor so alpha may decay |
| **Why it might fail** | Factor crowding; commodity-specific regime where momentum and carry simultaneously fail |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 8/10 | 32 |
| Replication Quality | 20% | 7/10 | 14 |
| Economic Plausibility | 15% | 9/10 | 13.5 |
| Implementation Simplicity | 10% | 8/10 | 8 |
| Execution Robustness | 10% | 7/10 | 7 |
| Prop-Firm Compatibility | 5% | 6/10 | 3 |
| **TOTAL** | | | **77.5/100** |

---

### PAPER 3: Deep Momentum Networks with Market Trend Dynamics

| Field | Detail |
|---|---|
| **Title** | Deep Momentum Networks with Market Trend Dynamics |
| **Authors** | Jaemin Song, Jaegi Jeon |
| **Year** | 2025 |
| **Source** | PLoS ONE (open access) |
| **Asset class** | 99 continuous futures contracts (equities, currencies, commodities, bonds) |
| **Trading horizon** | Weekly rebalancing |
| **Entry logic** | LSTM-based deep momentum network enhanced with XGBoost-generated Market Trend Dynamic Point (MTDP) scores; combines short-term (4–20 week) and long-term (52 week) momentum signals |
| **Exit logic** | Model-driven position sizing; positions adjust based on LSTM output |
| **Risk management** | 15% annual target volatility; volatility scaling per asset |
| **Holding period** | Variable (weekly) |
| **Markets tested** | 99 continuous futures (CHRIS/Quandl data) |
| **Sample period** | 1995–2021 |
| **Number of trades** | Not stated |
| **Sharpe ratio** | ~1.3–1.5 (OOS, net of costs); best during stable periods with 8-week lookback |
| **Sortino** | Not explicitly reported but "lowest maximum drawdown" noted |
| **Maximum drawdown** | Reported as improved vs. baseline DMN; specific value in paper |
| **Transaction costs** | **Y** — explicit transaction cost formula (Eq. 3), tested at multiple cost levels |
| **Walk-forward** | **Y** (rolling OOS) |
| **Out-of-sample** | **Y** — includes COVID-19 stress test |
| **Cross-validation** | Y (5 experiment sets) |
| **Code available** | **N** (data from CHRIS/Quandl, but no code repo) |
| **Implementation difficulty** | 8/10 (requires LSTM + XGBoost infrastructure) |
| **Prop-firm compatibility** | 5/10 (ML-based, opacity concern; weekly cadence) |
| **Live-trading suitability** | 5/10 (model complexity, retraining burden, regime sensitivity) |
| **Main weaknesses** | Deep learning overfitting risk; hyperparameter sensitivity; requires proprietary data (CHRIS); black-box nature; ⚠️ Sharpe ~1.5 for futures momentum is suspiciously high — possible data snooping |
| **Why it might fail** | ML overfitting; look-ahead via ratio-adjusted continuous futures (known issue); model degradation; transaction costs underestimated for less liquid contracts |

**⚠️ Too good to be true flag:** Sharpe ratios of 1.3–1.5 on 99 futures with ML momentum are above industry norms. Treat with caution.

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 4/10 | 8 |
| Economic Plausibility | 15% | 5/10 | 7.5 |
| Implementation Simplicity | 10% | 3/10 | 3 |
| Execution Robustness | 10% | 4/10 | 4 |
| Prop-Firm Compatibility | 5% | 5/10 | 2.5 |
| **TOTAL** | | | **53/100** |

---

### PAPER 4: Managing Volatility in Commodity Momentum

| Field | Detail |
|---|---|
| **Title** | Managing Volatility in Commodity Momentum |
| **Authors** | Qunfeng Xu, You Wang |
| **Year** | 2021 |
| **Source** | Journal of Futures Markets (Wiley) |
| **Asset class** | Commodity futures |
| **Trading horizon** | Weekly/monthly |
| **Entry logic** | Volatility-managed momentum: scales commodity momentum positions by inverse volatility; goes long winners, short losers |
| **Exit logic** | Signal reversal or volatility-triggered de-risking |
| **Risk management** | Central innovation: volatility scaling reduces drawdowns |
| **Holding period** | Weekly to monthly |
| **Markets tested** | Broad commodity futures |
| **Sample period** | Pre-2021 (multi-decade) |
| **Sharpe ratio** | 0.8 (gross); ~13% annualized return |
| **Sortino** | Not reported |
| **Maximum drawdown** | Reduced vs. unmanaged momentum |
| **Transaction costs** | **Y** — discussed and incorporated |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 5/10 |
| **Prop-firm compatibility** | 7/10 (commodity futures, straightforward signal) |
| **Live-trading suitability** | 7/10 |
| **Main weaknesses** | Sharpe of 0.8 is modest; momentum crashes; commodity-cycle dependence |
| **Why it might fail** | Extended commodity bear markets; correlation spikes between commodities |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 6/10 | 12 |
| Economic Plausibility | 15% | 8/10 | 12 |
| Implementation Simplicity | 10% | 8/10 | 8 |
| Execution Robustness | 10% | 7/10 | 7 |
| Prop-Firm Compatibility | 5% | 7/10 | 3.5 |
| **TOTAL** | | | **70.5/100** |

---

### PAPER 5: Mean-Reverting Statistical Arbitrage Strategies in Crude Oil Markets

| Field | Detail |
|---|---|
| **Title** | Mean-Reverting Statistical Arbitrage Strategies in Crude Oil Markets |
| **Authors** | Vincenzo Fanelli |
| **Year** | 2024 |
| **Source** | Risks (MDPI) — open access |
| **Asset class** | Crude oil futures (WTI, Brent) |
| **Trading horizon** | Daily |
| **Entry logic** | Pairs trading on cointegrated crude oil futures; enter when spread deviates by threshold |
| **Exit logic** | Reversion to mean or stop-loss |
| **Risk management** | Position limits; spread threshold triggers |
| **Holding period** | Days to weeks |
| **Markets tested** | WTI and Brent crude oil futures |
| **Sample period** | Multi-year (pre-2024) |
| **Sharpe ratio** | Varies; ~0.8–1.2 in OOS |
| **Sortino** | Not reported |
| **Maximum drawdown** | Reported but specific value in paper |
| **Transaction costs** | **Y** — included in OOS backtest |
| **Walk-forward** | **Y** |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 4/10 |
| **Prop-firm compatibility** | 7/10 (energy futures, liquid) |
| **Live-trading suitability** | 6/10 (spread execution risk) |
| **Main weaknesses** | Only two instruments (WTI-Brent); cointegration can break during supply shocks; limited capacity |
| **Why it might fail** | OPEC shocks, pipeline disruptions decouple WTI-Brent; spread execution slippage |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 6/10 | 24 |
| Replication Quality | 20% | 7/10 | 14 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 8/10 | 8 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 7/10 | 3.5 |
| **TOTAL** | | | **66/100** |

---

### PAPER 6: Memory-Enhanced Momentum in Commodity Futures Markets

| Field | Detail |
|---|---|
| **Title** | Memory-Enhanced Momentum in Commodity Futures Markets |
| **Authors** | Jonas S. Mehlitz, Bruno R. Auer |
| **Year** | 2024 |
| **Source** | European Journal of Finance (Taylor & Francis) |
| **Asset class** | Commodity futures |
| **Trading horizon** | Weekly/monthly |
| **Entry logic** | Enhanced momentum signal incorporating long-memory effects; uses fractional differencing to preserve information while achieving stationarity |
| **Exit logic** | Signal reversal |
| **Risk management** | Standard momentum risk controls |
| **Holding period** | Weekly to monthly |
| **Markets tested** | Broad commodity futures |
| **Sample period** | Multi-decade |
| **Sharpe ratio** | Improved over standard momentum (reported in paper) |
| **Sortino** | Not explicitly reported |
| **Maximum drawdown** | Not explicitly reported |
| **Transaction costs** | **Y** — discussed and incorporated |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** — strong in- and out-of-sample support |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 6/10 (fractional differencing complexity) |
| **Prop-firm compatibility** | 6/10 |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | Incremental improvement over standard momentum; fractional differencing adds complexity; marginal alpha |
| **Why it might fail** | Memory parameter overfitting; same regime sensitivity as standard momentum |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 5/10 | 10 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 5/10 | 5 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 6/10 | 3 |
| **TOTAL** | | | **62.5/100** |

---

### PAPER 7: Optimal Carry Trade Portfolio Choice Under Regime Shifts

| Field | Detail |
|---|---|
| **Title** | Optimal Carry Trade Portfolio Choice Under Regime Shifts |
| **Authors** | Chia-Ning Chen, Chien-Ho Lin |
| **Year** | 2022 |
| **Source** | Review of Quantitative Finance and Accounting (Springer) |
| **Asset class** | FX (currency pairs) |
| **Trading horizon** | Monthly |
| **Entry logic** | Carry trade with regime-switching model; goes long high-yield / short low-yield currencies adjusted for regime |
| **Exit logic** | Regime change triggers position adjustment |
| **Risk management** | Regime-aware position sizing |
| **Holding period** | Monthly |
| **Markets tested** | Developed and emerging market currencies |
| **Sample period** | Multi-decade |
| **Sharpe ratio** | Improved over naive carry; ~0.6–0.9 OOS |
| **Sortino** | Not reported |
| **Maximum drawdown** | Reduced vs. naive carry |
| **Transaction costs** | **Y** — explicitly incorporated |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 6/10 (regime-switching econometrics) |
| **Prop-firm compatibility** | 5/10 (FX spot/forwards) |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | Carry trades suffer in risk-off episodes; regime model misspecification; bid-ask spreads in EM FX |
| **Why it might fail** | Sudden risk-off events (carry unwinds); central bank surprises; EM liquidity crisis |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 5/10 | 10 |
| Economic Plausibility | 15% | 8/10 | 12 |
| Implementation Simplicity | 10% | 5/10 | 5 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 5/10 | 2.5 |
| **TOTAL** | | | **63.5/100** |

---

### PAPER 8: Factor Momentum in Commodity Futures Markets

| Field | Detail |
|---|---|
| **Title** | Factor Momentum in Commodity Futures Markets |
| **Authors** | Yujun Qian, Yong Jiang, Xin Liu |
| **Year** | 2025 |
| **Source** | Journal of Futures Markets (Wiley) |
| **Asset class** | Commodity futures |
| **Trading horizon** | Monthly |
| **Entry logic** | Time-series momentum applied to commodity factors (basis, momentum, skewness, etc.); exploits autocorrelation in factor returns |
| **Exit logic** | Factor momentum reversal |
| **Risk management** | Portfolio construction across factors |
| **Holding period** | Monthly |
| **Markets tested** | Global commodity futures |
| **Sample period** | Multi-decade |
| **Sharpe ratio** | Higher Sharpe than individual factors (specific values in paper) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated |
| **Transaction costs** | **Y** — accounted for |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 6/10 |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | Multi-factor combinations can be unstable; factor decay; overfitting risk |
| **Why it might fail** | Factor crowding; commodity super-cycle overriding factor signals |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 5/10 | 10 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 5/10 | 5 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 6/10 | 3 |
| **TOTAL** | | | **62.5/100** |

---

### PAPER 9: The Best Strategies for FX Hedging

| Field | Detail |
|---|---|
| **Title** | The Best Strategies for FX Hedging |
| **Authors** | Pablo Castro, Connor Hamill, James Harber, Campbell R. Harvey |
| **Year** | 2025 |
| **Source** | SSRN Working Paper |
| **Asset class** | FX (developed market currencies) |
| **Trading horizon** | Monthly |
| **Entry logic** | Compares carry, momentum, PPP, value signals for FX hedging; combines signals for optimal hedging |
| **Exit logic** | Signal-driven monthly rebalancing |
| **Risk management** | Signal diversification; hedging framework |
| **Holding period** | Monthly |
| **Markets tested** | Developed market FX |
| **Sample period** | Multi-decade |
| **Sharpe ratio** | ~0.5–0.8 for individual signals; higher combined |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated |
| **Transaction costs** | **Y** — incorporated |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 5/10 |
| **Prop-firm compatibility** | 4/10 (designed for hedging, not speculation) |
| **Live-trading suitability** | 5/10 (hedging context, lower return potential) |
| **Main weaknesses** | Primarily a hedging study; modest Sharpe; developed-market focus |
| **Why it might fail** | Signal decay; central bank intervention; structural break in FX regimes |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 8/10 | 32 |
| Replication Quality | 20% | 6/10 | 12 |
| Economic Plausibility | 15% | 8/10 | 12 |
| Implementation Simplicity | 10% | 7/10 | 7 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 4/10 | 2 |
| **TOTAL** | | | **71/100** |

---

### PAPER 10: An Innovative High-Frequency Statistical Arbitrage in Chinese Futures Market

| Field | Detail |
|---|---|
| **Title** | An Innovative High-Frequency Statistical Arbitrage in Chinese Futures Market |
| **Authors** | Chao He, Tao Wang, Xin Liu, Kai Huang |
| **Year** | 2023 |
| **Source** | Journal of Innovation & Knowledge (Elsevier) — open access |
| **Asset class** | Chinese commodity futures |
| **Trading horizon** | High-frequency (intraday) |
| **Entry logic** | Unique pairs trading framework using machine learning for pair selection in Chinese futures |
| **Exit logic** | Mean reversion or time-based close |
| **Risk management** | Position limits; stop-loss |
| **Holding period** | Intraday |
| **Markets tested** | Chinese commodity futures |
| **Sample period** | Multi-year |
| **Sharpe ratio** | High (specific in paper); strong OOS results |
| **Sortino** | Not reported |
| **Maximum drawdown** | "Excellent" OOS drawdown reported |
| **Transaction costs** | **Y** — included |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | Y |
| **Code available** | **N** |
| **Implementation difficulty** | 8/10 (HF infrastructure needed) |
| **Prop-firm compatibility** | 3/10 (Chinese market access restrictions; HF infrastructure) |
| **Live-trading suitability** | 4/10 (market-specific, regulatory risk, latency requirements) |
| **Main weaknesses** | China-specific; HF infrastructure barrier; regulatory changes; limited market access for non-Chinese firms |
| **Why it might fail** | Regulatory crackdowns; exchange rule changes; latency arms race; capacity constraints |

**⚠️ Caution:** High-frequency stat arb in Chinese futures is niche; results may not transfer to Western markets.

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 6/10 | 24 |
| Replication Quality | 20% | 3/10 | 6 |
| Economic Plausibility | 15% | 6/10 | 9 |
| Implementation Simplicity | 10% | 2/10 | 2 |
| Execution Robustness | 10% | 3/10 | 3 |
| Prop-Firm Compatibility | 5% | 3/10 | 1.5 |
| **TOTAL** | | | **45.5/100** |

---

### PAPER 11: Trend Following Strategies — A Practical Guide

| Field | Detail |
|---|---|
| **Title** | Trend Following Strategies: A Practical Guide |
| **Authors** | Chao Shi, Xinyu Lian |
| **Year** | 2025 |
| **Source** | SSRN Working Paper #5140633 |
| **Asset class** | Diversified futures (equities, commodities, rates, FX) |
| **Trading horizon** | Daily/weekly |
| **Entry logic** | Systematic trend following with multiple signal speeds; breakout and moving average crossover variants |
| **Exit logic** | Signal reversal |
| **Risk management** | Volatility targeting; diversification across markets |
| **Holding period** | Weeks to months |
| **Markets tested** | Global futures |
| **Sample period** | Multi-decade |
| **Sharpe ratio** | ~0.6–0.8 (net of costs, realistic) |
| **Sortino** | Not reported |
| **Maximum drawdown** | ~30% for individual contracts; lower diversified |
| **Transaction costs** | **Y** — included |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 4/10 |
| **Prop-firm compatibility** | 7/10 (futures, systematic) |
| **Live-trading suitability** | 7/10 (well-understood, liquid markets) |
| **Main weaknesses** | 30% drawdowns on individual contracts; trend-following has long flat periods; post-2008 correlation issues |
| **Why it might fail** | Extended choppy markets; correlation spikes; capacity erosion in trend following |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 6/10 | 24 |
| Replication Quality | 20% | 6/10 | 12 |
| Economic Plausibility | 15% | 8/10 | 12 |
| Implementation Simplicity | 10% | 8/10 | 8 |
| Execution Robustness | 10% | 7/10 | 7 |
| Prop-Firm Compatibility | 5% | 7/10 | 3.5 |
| **TOTAL** | | | **66.5/100** |

---

### PAPER 12: Gold-Silver Pair Trading — Mean Reversion Strategy Using Machine Learning

| Field | Detail |
|---|---|
| **Title** | Gold Silver Pair Trading — Mean Reversion Strategy Using Machine Learning |
| **Authors** | Vinod K. Mittal, Rajeev Mittal |
| **Year** | 2025 |
| **Source** | Authorea Preprints |
| **Asset class** | Precious metals (gold, silver futures) |
| **Trading horizon** | Daily |
| **Entry logic** | ML-enhanced pairs trading on gold-silver ratio; uses integrated ML model to predict reversion timing |
| **Exit logic** | Reversion to mean or ML-based exit |
| **Risk management** | Stop-loss; position sizing |
| **Holding period** | Days to weeks |
| **Markets tested** | COMEX gold and silver futures |
| **Sample period** | Multi-year |
| **Sharpe ratio** | 0.71 |
| **Sortino** | Not reported |
| **Maximum drawdown** | Reported (improved vs. naive) |
| **Transaction costs** | **Y** — incorporated |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** — OOS performance analyzed |
| **Cross-validation** | Y (ML cross-validation) |
| **Code available** | **N** |
| **Implementation difficulty** | 5/10 |
| **Prop-firm compatibility** | 6/10 (liquid metals futures) |
| **Live-trading suitability** | 5/10 (only 2 instruments, capacity limited) |
| **Main weaknesses** | Only gold-silver pair; modest Sharpe (0.71); ML complexity for marginal gain; preprint (not peer-reviewed) |
| **Why it might fail** | Structural break in gold-silver relationship (mining tech, industrial demand shifts); ML overfitting |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 5/10 | 20 |
| Replication Quality | 20% | 5/10 | 10 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 6/10 | 6 |
| Execution Robustness | 10% | 6/10 | 6 |
| Prop-Firm Compatibility | 5% | 6/10 | 3 |
| **TOTAL** | | | **55.5/100** |

---

### PAPER 13: Curve Momentum in China (Commodity Futures)

| Field | Detail |
|---|---|
| **Title** | Curve Momentum in China |
| **Authors** | Ziyi Zheng, Yifu Liu, Yifan Wu, Rui Chen |
| **Year** | 2026 |
| **Source** | Journal of Futures Markets (Wiley) |
| **Asset class** | Chinese commodity futures |
| **Trading horizon** | Monthly |
| **Entry logic** | Curve momentum: exploits term structure shape (contango/backwardation) as predictor of returns, unique to China's seasonal maturity structure |
| **Exit logic** | Signal reversal |
| **Risk management** | Standard |
| **Holding period** | Monthly |
| **Markets tested** | Chinese commodity futures |
| **Sample period** | Multi-year |
| **Sharpe ratio** | "Significantly positive" (specific values in paper) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated |
| **Transaction costs** | Discussed |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 3/10 (Chinese market access) |
| **Live-trading suitability** | 4/10 (China-specific, regulatory risk) |
| **Main weaknesses** | China-specific term structure dynamics; regulatory risk; limited transferability |
| **Why it might fail** | Exchange rule changes; unique Chinese seasonal maturity structure may not persist |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 7/10 | 28 |
| Replication Quality | 20% | 4/10 | 8 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 5/10 | 5 |
| Execution Robustness | 10% | 4/10 | 4 |
| Prop-Firm Compatibility | 5% | 3/10 | 1.5 |
| **TOTAL** | | | **57/100** |

---

### PAPER 14: Trading Signals in VIX Futures (Avellaneda et al.)

| Field | Detail |
|---|---|
| **Title** | Trading Signals in VIX Futures |
| **Authors** | Marco Avellaneda, Tom Na-Lun Li, Andrew Papanicolaou, Guangyang Wang |
| **Year** | 2021 |
| **Source** | Applied Mathematical Finance (Taylor & Francis) |
| **Asset class** | VIX futures |
| **Trading horizon** | Daily |
| **Entry logic** | Markov model for VIX futures term structure; uses carry/roll yield signals and term structure state to predict returns |
| **Exit logic** | Markov state transition |
| **Risk management** | Position sizing based on model confidence |
| **Holding period** | Days |
| **Markets tested** | VIX futures |
| **Sample period** | 2006–2020 |
| **Sharpe ratio** | ~1.0+ (reported in paper) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated |
| **Transaction costs** | **Y** — included |
| **Walk-forward** | Y |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** |
| **Implementation difficulty** | 7/10 (Markov model + term structure calibration) |
| **Prop-firm compatibility** | 4/10 (VIX futures restrictions) |
| **Live-trading suitability** | 5/10 (tail risk, VIX-specific) |
| **Main weaknesses** | Only VIX futures; tail risk from volatility spikes; Markov assumption oversimplified |
| **Why it might fail** | Volmageddon-type events; VIX futures microstructure changes; exchange rule changes |

**Score:**
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 8/10 | 32 |
| Replication Quality | 20% | 5/10 | 10 |
| Economic Plausibility | 15% | 7/10 | 10.5 |
| Implementation Simplicity | 10% | 4/10 | 4 |
| Execution Robustness | 10% | 5/10 | 5 |
| Prop-Firm Compatibility | 5% | 4/10 | 2 |
| **TOTAL** | | | **63.5/100** |

---

## ❌ REJECTED PAPERS (Did Not Meet Bar)

| Paper | Reason for Rejection |
|---|---|
| "Virtual Barrels: Quantitative Trading in the Oil Market" (Bouchouev, 2023, Springer) | Book, not peer-reviewed paper; primarily in-sample; no downloadable code |
| "Following the Trend" (Clenow, 2023) | Book, not academic paper; no OOS metrics; no transaction cost analysis |
| "Revisiting Statistical Arbitrage" (Stephenson et al., 2021, Bond U.) | Sharpe of 1.34 seems inflated; thesis not peer-reviewed; static hedge ratio assumptions questionable |
| "Regime-Aware Statistical Arbitrage" (Wong, 2026, SSRN) | **Sharpe of 2.998 is almost certainly overfit** — far too high for pairs trading; no code; no transaction costs specified; single author preprint |
| "Statistical Arbitrage in Commodity Markets through PCA and OPTICS" (Cuschieri, 2024, Malta) | Sharpe of 2.69 is suspicious; thesis not peer-reviewed; small commodity universe |
| "Machine Learning in Commodity Futures" (Guida, 2025, CFA Institute) | Sharpe of 3.6 and 2.9 reported — **far too good to be true**; likely look-ahead or overfitting |
| "ETF Mispricing" (Kellerbach, 2023, UNL) | Thesis; in-sample only; no robust OOS |
| "VIX Futures Term-Structure and Currency Returns" (Kaebi) | Not primarily a trading strategy paper; limited OOS |
| "Currency Speculation" (SSRN, 2025) | Abstract reports SR 0.95 but methodology details inaccessible (paywall); cannot verify |
| "Core-Satellite FX Carry" (Feeney, 2026, Veda Trading) | Industry whitepaper, not peer-reviewed; SR ~1.3 claimed but marketing bias |

---

## 📊 SUMMARY RANKING

| Rank | Paper | Score | Asset Class | Best For |
|---|---|---|---|---|
| 1 | **Carry Momentum** (Davis et al., 2022) | **77.5** | Commodity futures | Best overall: simple, liquid, robust |
| 2 | **Best Strategies for FX Hedging** (Castro et al., 2025) | **71.0** | FX | FX signal diversification, Campbell Harvey co-author |
| 3 | **Managing Volatility in Commodity Momentum** (Xu & Wang, 2021) | **70.5** | Commodity futures | Vol-managed momentum, practical |
| 4 | **Sharpe-Optimal Volatility Futures Carry** (Uhl, 2024) | **70.0** | VIX futures | Vol-specific carry, rigorous |
| 5 | **Trend Following: Practical Guide** (Shi & Lian, 2025) | **66.5** | Diversified futures | Classic approach, transparent |
| 6 | **Mean-Reverting Stat Arb in Crude Oil** (Fanelli, 2024) | **66.0** | Energy futures | Oil spread trading |
| 7 | **Trading Signals in VIX Futures** (Avellaneda et al., 2021) | **63.5** | VIX futures | Academic rigor, Markov approach |
| 8 | **Optimal Carry Trade Under Regime Shifts** (Chen & Lin, 2022) | **63.5** | FX currencies | Regime-aware FX |
| 9 | **Factor Momentum in Commodities** (Qian et al., 2025) | **62.5** | Commodity futures | Factor-based approach |
| 10 | **Memory-Enhanced Momentum** (Mehlitz & Auer, 2024) | **62.5** | Commodity futures | Fractional differencing |
| 11 | **Curve Momentum in China** (Zheng et al., 2026) | **57.0** | Chinese commodities | China-specific |
| 12 | **Gold-Silver Pair Trading ML** (Mittal & Mittal, 2025) | **55.5** | Precious metals | Gold-silver spread |
| 13 | **Deep Momentum Networks** (Song & Jeon, 2025) | **53.0** | 99 futures | ML approach (high risk) |
| 14 | **HF Stat Arb in Chinese Futures** (He et al., 2023) | **45.5** | Chinese futures | HF/China-specific (niche) |

---

## 🔑 KEY FINDINGS & CAVEATS

### Honest Assessment

1. **No paper with code + walk-forward + transaction costs + OOS was found across all four asset classes.** This is the unfortunate reality of academic finance — most researchers don't publish code.

2. **Sharpe ratios above ~1.2 should be treated with deep suspicion.** Papers claiming 2.5–3.6 are almost certainly overfit, suffer from look-ahead bias, or use unrealistic execution assumptions. The rejected papers section lists the worst offenders.

3. **The most implementable strategies are the simplest:** Carry Momentum (#1), Volatility-Managed Commodity Momentum (#3), and Trend Following (#5) — all use well-known signals on liquid futures with reasonable Sharpes of 0.6–1.2.

4. **FX strategies are underrepresented in recent top-tier work.** The Castro et al. (2025) paper with Campbell Harvey is the strongest, but it's framed as hedging rather than speculation.

5. **VIX/volatility strategies are well-researched but production-risky.** The Uhl (2024) and Avellaneda et al. (2021) papers are rigorous but face catastrophic tail risk (Volmageddon).

6. **Index arbitrage / ETF premium strategies** have very little recent academic work meeting the bar. Most papers are theses or lack transaction costs. This area is dominated by industry practitioners who don't publish.

7. **Prop-firm compatibility is generally low across all papers.** Prop firms typically need intraday strategies on index futures (NQ, ES) — academic papers focus on daily/weekly frequencies on broader asset classes.

### What Would Actually Work for a NAS100 Backtest

Based on this review, the most promising approaches for a NAS100/NQ backtest would be:
- **Time-series momentum** applied to NQ futures (well-supported, simple, robust)
- **Volatility-managed position sizing** (Xu & Wang framework)
- **VIX-based regime overlay** (use VIX term structure as a filter for NQ positions)
- **None of these papers directly test NAS100** — you'd need to adapt the methodology
