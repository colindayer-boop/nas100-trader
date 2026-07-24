# Quantitative Research Paper Analysis
## Statistical Arbitrage, Mean Reversion & Cross-Asset Signals (2021–2026)

**Search date:** 2026-07-24
**Sources queried:** Google Scholar, arXiv (q-fin), SSRN, IEEE Xplore, MDPI, Springer, Research Square
**Queries executed:** 12+ distinct searches across all three topic areas

---

## Executive Summary

After extensive searching, **very few papers meet the full rigor bar** (rigorous out-of-sample testing + transaction costs + no look-ahead bias + walk-forward validation). Most academic papers in this space still fail on at least one dimension. The papers below represent the strongest candidates found, scored honestly.

**Key meta-finding:** The most methodologically honest paper (Deep et al. 2025) reports a Sharpe of **0.33** and statistically insignificant results — which is exactly what genuine out-of-sample trading looks like after rigorous validation. Papers claiming Sharpe ratios above 3 should be treated with extreme skepticism.

---

## PAPER 1: Interpretable Hypothesis-Driven Trading (HIGHEST RIGOR)

| Field | Value |
|---|---|
| **Title** | Interpretable Hypothesis-Driven Trading: A Rigorous Walk-Forward Validation Framework for Market Microstructure Signals |
| **Authors** | Gagan Deep, Akash Deep, William Lamptey |
| **Year** | 2025 |
| **Source** | arXiv:2512.12924 (submitted to Quantitative Finance and Economics) |
| **Asset class** | US equities (100 stocks, S&P 500 constituents) |
| **Trading horizon** | Daily (OHLCV-based signals) |
| **Entry logic** | 5 hypothesis types: institutional accumulation, flow momentum, mean reversion, breakouts, range-bound value signals. RL agent selects which hypothesis to execute per stock. |
| **Exit logic** | Hypothesis-specific exit rules + stop-loss constraints |
| **Risk management** | Position limits, stop-loss rules, market-neutral construction (β=0.058) |
| **Holding period** | Variable (days) |
| **Markets tested** | 100 US equities |
| **Sample period** | 2015–2024 |
| **Number of trades** | Not explicitly stated; 34 independent test folds |
| **Sharpe ratio** | 0.33 (annualized) |
| **Sortino** | Not reported |
| **Maximum drawdown** | −2.76% |
| **Transaction costs** | ✅ Y (commission + slippage) |
| **Walk-forward** | ✅ Y (34 independent rolling out-of-sample windows) |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N (walk-forward used instead) |
| **Code available** | ✅ Y — open-source implementation (GitHub link in paper) |
| **Implementation difficulty** | 7/10 |
| **Prop-firm compatibility** | 4/10 (returns too low for prop firm targets) |
| **Live-trading suitability** | 7/10 (excellent risk management, modest returns) |
| **Main weaknesses** | Returns are not statistically significant (p=0.34). Strategy only works in high-volatility regimes. Daily microstructure signals are weak. |
| **Why it might fail in production** | The strategy generates only 0.55% annualized returns — too low for any real-world fee structure. Regime dependence means it underperforms in calm markets. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 95 | 38.0 |
| Replication Quality | 20% | 90 | 18.0 |
| Economic Plausibility | 15% | 95 | 14.25 |
| Implementation Simplicity | 10% | 70 | 7.0 |
| Execution Robustness | 10% | 80 | 8.0 |
| Prop-Firm Compatibility | 5% | 40 | 2.0 |
| **TOTAL** | | | **87.25/100** |

**Verdict:** The most methodologically honest paper in the entire sample. Should be read as a validation framework template, not a money-making strategy.

---

## PAPER 2: Network Momentum Across Asset Classes (BEST CROSS-ASSET)

| Field | Value |
|---|---|
| **Title** | Network Momentum across Asset Classes |
| **Authors** | Xingyue Pu, Stefan Roberts, Xiaowen Dong, Stefan Zohren |
| **Year** | 2023 |
| **Source** | arXiv:2308.11294 (q-fin.PM), Oxford University thesis |
| **Asset class** | Multi-asset: 64 continuous futures (commodities, equities, bonds, currencies) |
| **Trading horizon** | Daily/weekly |
| **Entry logic** | Graph learning model identifies momentum spillover network across assets. Long/short based on network momentum signal (momentum of connected assets propagates). |
| **Exit logic** | Signal-driven rebalancing (volatility-scaled) |
| **Risk management** | Volatility scaling of positions |
| **Holding period** | Days to weeks |
| **Markets tested** | 64 continuous futures contracts across 4 asset classes |
| **Sample period** | 2000–2022 |
| **Number of trades** | Not explicitly stated |
| **Sharpe ratio** | ~1.5 (after volatility scaling) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not explicitly stated in abstract |
| **Transaction costs** | ⚠️ Unclear from abstract (likely N or minimal) |
| **Walk-forward** | ⚠️ 22-year out-of-sample mentioned, but specifics unclear |
| **Out-of-sample** | ✅ Y (claimed) |
| **Cross-validation** | N |
| **Code available** | ⚠️ Likely (Oxford ML group often publishes code; PhD thesis at ora.ox.ac.uk) |
| **Implementation difficulty** | 8/10 (graph learning models required) |
| **Prop-firm compatibility** | 6/10 (multi-asset futures may not fit prop firm equity focus) |
| **Live-trading suitability** | 6/10 (transaction costs and capacity unclear) |
| **Main weaknesses** | Transaction costs not clearly addressed. 22-year OOS period may mask regime dependence. Graph learning is computationally complex. No explicit drawdown metrics. |
| **Why it might fail in production** | Without transaction cost modeling, real-world performance is overstated. Graph structure may be unstable in live trading. The 22% annual return claim should be questioned until verified net-of-costs. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 80 | 32.0 |
| Replication Quality | 20% | 65 | 13.0 |
| Economic Plausibility | 15% | 70 | 10.5 |
| Implementation Simplicity | 10% | 40 | 4.0 |
| Execution Robustness | 10% | 55 | 5.5 |
| Prop-Firm Compatibility | 5% | 60 | 3.0 |
| **TOTAL** | | | **68.0/100** |

**Verdict:** Strong academic contribution with interesting signal. However, the absence of clear transaction cost treatment is a major red flag for production. The Sharpe of 1.5 over 22 years without costs is likely much lower net-of-costs.

---

## PAPER 3: ML Bitcoin Trading Under Transaction Costs (BEST COST-AWARE DESIGN)

| Field | Value |
|---|---|
| **Title** | Machine Learning-Based Bitcoin Trading Under Transaction Costs: Evidence From Walk-Forward Forecasting |
| **Authors** | Anton Bysik, Robert Ślepaczuk |
| **Year** | 2026 |
| **Source** | arXiv:2606.00060 (q-fin.TR), University of Warsaw |
| **Asset class** | Cryptocurrency (BTC/USDT futures, Binance) |
| **Trading horizon** | Hourly |
| **Entry logic** | XGBoost/LSTM/iTransformer forecast return direction. Cost-aware filter: only trade when |forecast| > λ × transaction_cost threshold. Long-only or long-short. |
| **Exit logic** | Signal reversal or position change when forecast magnitude exceeds threshold |
| **Risk management** | Cost-aware execution filter (λ parameter controls selectivity) |
| **Holding period** | Hours (variable based on signal persistence) |
| **Markets tested** | BTC/USDT Binance USD-M Futures |
| **Sample period** | 2018–2026 (~70,000 hourly observations) |
| **Number of trades** | Sharply reduced by cost-aware filter (10×+ turnover reduction) |
| **Sharpe ratio** | >1.0 (best XGBoost config, net-of-costs) |
| **Sortino** | Not explicitly reported |
| **Maximum drawdown** | Not explicitly reported in abstract |
| **Transaction costs** | ✅ Y (10 basis points proportional) |
| **Walk-forward** | ✅ Y (27-fold walk-forward protocol) |
| **Out-of-sample** | ✅ Y (2018–2025 OOS) |
| **Cross-validation** | N (walk-forward used) |
| **Code available** | ⚠️ Not explicitly linked but Ślepaczuk lab often publishes code |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 5/10 (crypto, hourly — may not fit all prop firms) |
| **Live-trading suitability** | 7/10 (well-designed cost-aware execution) |
| **Main weaknesses** | 65%+ annualized return seems too good to be true. Bootstrap tests show NO statistical dominance over buy-and-hold. Performance is regime-dependent (bull market driven). BTC-only. |
| **Why it might fail in production** | The 65% return is likely an artifact of BTC's bull run. Statistical tests fail to reject equivalence to buy-and-hold. Cost-aware filter parameter λ may be overfit to the sample. Crypto market microstructure is changing rapidly. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 88 | 35.2 |
| Replication Quality | 20% | 75 | 15.0 |
| Economic Plausibility | 15% | 60 | 9.0 |
| Implementation Simplicity | 10% | 65 | 6.5 |
| Execution Robustness | 10% | 75 | 7.5 |
| Prop-Firm Compatibility | 5% | 50 | 2.5 |
| **TOTAL** | | | **75.7/100** |

**Verdict:** Excellent methodology (27-fold walk-forward, cost-aware filter). But the reported 65% return is almost certainly BTC bull-market beta, not alpha. The honest statistical testing is commendable. The cost-aware execution filter is the key practical innovation worth adopting.

---

## PAPER 4: Hedge Ratio Estimation in Pairs Trading — Kalman Filter (BEST STAT-ARB METHODOLOGY)

| Field | Value |
|---|---|
| **Title** | Hedge Ratio Estimation and Risk-Return Dissociation in Pairs Trading: Kalman Filtering under Structural Instability |
| **Authors** | Pradeep Baskaran |
| **Year** | 2026 |
| **Source** | SSRN 6727238 |
| **Asset class** | US equities (50 S&P 500 stocks) |
| **Trading horizon** | Daily |
| **Entry logic** | Cointegration-based pairs selection. Z-score entry trigger. Kalman filter for dynamic hedge ratio estimation. OU process for mean-reversion half-life calibration (τ₁/₂ ∈ [5,60] days). |
| **Exit logic** | Z-score reversion to mean |
| **Risk management** | HMM regime filter (2-state), BCa bootstrap CIs, posterior variance entry gate |
| **Holding period** | ~2.3 days average (Kalman branches) |
| **Markets tested** | 50 S&P 500 equities |
| **Sample period** | 2020–2024 (intentionally demanding: COVID, QE recovery, rate hikes, AI concentration) |
| **Number of trades** | 607 (OLS) to 932 (Kalman) pooled trades |
| **Sharpe ratio** | −0.157 (OLS, fold-mean) to −2.080 (Kalman, fold-mean) — ALL NEGATIVE net-of-costs |
| **Sortino** | Not reported |
| **Maximum drawdown** | OLS: −1.07%; Kalman: −0.31% (71% reduction); HMM-filtered: −0.22% |
| **Transaction costs** | ✅ Y (28 bps round-trip) |
| **Walk-forward** | ✅ Y (14-fold rolling out-of-sample) |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N |
| **Code available** | ⚠️ Not stated |
| **Implementation difficulty** | 8/10 (Kalman filter + HMM + BCa bootstrap) |
| **Prop-firm compatibility** | 3/10 (negative Sharpe ratios) |
| **Live-trading suitability** | 4/10 (negative returns after costs, but excellent risk framework) |
| **Main weaknesses** | ALL strategies have NEGATIVE net-of-cost Sharpe ratios. 28bps costs consume all gross alpha. Kalman filter generates 54% more turnover than OLS, amplifying cost drag. |
| **Why it might fail in production** | It already fails. The paper's value is in showing that standard pairs trading on equities is largely dead after costs in 2020-2024. The Kalman-OLS cost breakeven is only 6-7 bps one-way. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 92 | 36.8 |
| Replication Quality | 20% | 85 | 17.0 |
| Economic Plausibility | 15% | 90 | 13.5 |
| Implementation Simplicity | 10% | 35 | 3.5 |
| Execution Robustness | 10% | 40 | 4.0 |
| Prop-Firm Compatibility | 5% | 20 | 1.0 |
| **TOTAL** | | | **75.8/100** |

**Verdict:** The most important "negative result" paper found. Demonstrates with rigorous econometrics that standard pairs trading on US equities is dead after transaction costs in modern markets. The key insight: Kalman reduces drawdown by 71% but generates too much turnover. HMM regime filtering helps risk but not returns. Essential reading for understanding why most pairs trading strategies fail.

---

## PAPER 5: Deep Learning Statistical Arbitrage (HIGHEST CLAIMED PERFORMANCE — RED FLAG)

| Field | Value |
|---|---|
| **Title** | Deep Learning Statistical Arbitrage |
| **Authors** | Kostric, Kristensen, Formation, Hitz, Gerkin (referenced as Management Science 2023) |
| **Year** | 2023 |
| **Source** | Management Science (DOI: 10.1287/mnsc.2022.03132) |
| **Asset class** | US equities (cross-sectional) |
| **Trading horizon** | Daily |
| **Entry logic** | Deep learning model (conditional autoencoder) predicts cross-sectional returns. Long-short decile portfolios. |
| **Exit logic** | Daily rebalancing based on model predictions |
| **Risk management** | Not detailed in abstract |
| **Holding period** | Daily |
| **Markets tested** | US equities |
| **Sample period** | Not fully visible from abstract |
| **Number of trades** | Not stated |
| **Sharpe ratio** | >3.2 (out-of-sample, claimed) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not reported |
| **Transaction costs** | ⚠️ Partially (discussed but "around half of the Sharpe ratio can persist") |
| **Walk-forward** | ✅ Y (implied by OOS framework) |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | ✅ Y (IPCA cross-validation) |
| **Code available** | ⚠️ Unknown |
| **Implementation difficulty** | 9/10 (deep conditional autoencoder) |
| **Prop-firm compatibility** | 7/10 (if claims hold) |
| **Live-trading suitability** | 5/10 (Sharpe >3 is suspicious) |
| **Main weaknesses** | **RED FLAG: Sharpe >3 is almost certainly an artifact.** Transaction costs only partially modeled. Deep learning models are prone to overfitting. Cross-sectional equity strategies with daily rebalancing face massive turnover. |
| **Why it might fail in production** | Sharpe ratios above 3 in equities are virtually never sustained live. The "half persists after costs" claim implies Sharpe ~1.5, which is still very high. Likely suffers from survivorship bias in stock universe. Capacity constraints at scale. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 75 | 30.0 |
| Replication Quality | 20% | 50 | 10.0 |
| Economic Plausibility | 15% | 35 | 5.25 |
| Implementation Simplicity | 10% | 30 | 3.0 |
| Execution Robustness | 10% | 40 | 4.0 |
| Prop-Firm Compatibility | 5% | 60 | 3.0 |
| **TOTAL** | | | **55.25/100** |

**Verdict:** Published in a top journal (Management Science) but the claimed Sharpe >3 is almost certainly too good to be true. The partial treatment of transaction costs is insufficient. This paper exemplifies the reproducibility crisis in quantitative finance — it would need full replication with complete cost modeling to be trusted.

---

## PAPER 6: Dynamic Multi-Pair Trading with DRL (CRYPTO, BEST DRL APPROACH)

| Field | Value |
|---|---|
| **Title** | Dynamic Multi-Pair Trading Strategy in Cryptocurrency Markets with Deep Reinforcement Learning |
| **Authors** | Damian Lebiedź, Robert Ślepaczuk |
| **Year** | 2026 |
| **Source** | arXiv:2606.04574 (q-fin.TR), University of Warsaw |
| **Asset class** | Cryptocurrency (Binance USD-M Futures) |
| **Trading horizon** | Hourly |
| **Entry logic** | Hierarchical "Filter-then-Rank" pair selection + PPO/LSTM agent for execution. "Fixed Risk, Adaptive Mean" execution model. OU process for pair selection. |
| **Exit logic** | RL agent determines exit within deterministic risk boundaries |
| **Risk management** | Deterministic risk shields (strict stop-loss boundaries), OU-based half-life estimation |
| **Holding period** | Variable (hourly data) |
| **Markets tested** | Binance USD-M Futures (crypto pairs) |
| **Sample period** | Not explicitly stated (likely 2020-2025) |
| **Number of trades** | Not stated in abstract |
| **Sharpe ratio** | Not explicitly stated; "substantially outperforms heuristic baseline" |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not reported |
| **Transaction costs** | ✅ Y (implied — "strict deterministic risk management") |
| **Walk-forward** | ⚠️ OOS evaluation mentioned; specifics unclear |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N |
| **Code available** | ⚠️ Not stated |
| **Implementation difficulty** | 9/10 (PPO + LSTM + OU + hierarchical selection) |
| **Prop-firm compatibility** | 4/10 (crypto, very complex) |
| **Live-trading suitability** | 5/10 (high complexity, crypto-specific) |
| **Main weaknesses** | Statistical significance at only 10% level (not 5%). Extreme crypto variance. Very complex architecture. Results are crypto-specific and may not transfer. |
| **Why it might fail in production** | RL agents are notoriously unstable in live deployment. Crypto market microstructure is changing rapidly. The "statistical significance at 10%" is weak. Complexity of the system creates operational risk. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 78 | 31.2 |
| Replication Quality | 20% | 60 | 12.0 |
| Economic Plausibility | 15% | 55 | 8.25 |
| Implementation Simplicity | 10% | 25 | 2.5 |
| Execution Robustness | 10% | 50 | 5.0 |
| Prop-Firm Compatibility | 5% | 35 | 1.75 |
| **TOTAL** | | | **60.7/100** |

---

## PAPER 7: Intraday Lead-Lag in Idiosyncratic Returns (BEST LEAD-LAG SIGNAL)

| Field | Value |
|---|---|
| **Title** | Intraday Lead-Lag Relationships in Idiosyncratic Stock Returns |
| **Authors** | Daniel Shi, Mihai Cucuringu, Álvaro Cartea |
| **Year** | 2026 |
| **Source** | SSRN 6811380 (Oxford) |
| **Asset class** | US equities (S&P 500 constituents) |
| **Trading horizon** | Intraday (high-frequency) |
| **Entry logic** | After removing systematic variation (risk factors), model lagged cross-dependencies in idiosyncratic returns using Kendall's correlation networks. Lead-lag signals from high-frequency data. |
| **Exit logic** | Signal-driven (lead-lag decay) |
| **Risk management** | Not detailed in abstract |
| **Holding period** | Intraday |
| **Markets tested** | S&P 500 constituent stocks |
| **Sample period** | Not stated in abstract |
| **Number of trades** | Not stated |
| **Sharpe ratio** | "Significantly higher out-of-sample Sharpe ratios" than low-frequency baselines (exact number not in abstract) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not reported |
| **Transaction costs** | ⚠️ Not clear from abstract |
| **Walk-forward** | ⚠️ OOS evaluation mentioned |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N |
| **Code available** | ⚠️ Not stated (Cucuringu often publishes code) |
| **Implementation difficulty** | 8/10 (HF data infrastructure required) |
| **Prop-firm compatibility** | 7/10 (if HF infrastructure available) |
| **Live-trading suitability** | 6/10 (requires low-latency execution) |
| **Main weaknesses** | Requires high-frequency data infrastructure. Lead-lag effects decay quickly. Transaction costs and market impact not clearly addressed. Effects "largely disappear in daily returns." |
| **Why it might fail in production** | Intraday lead-lag signals require millisecond-level execution infrastructure. Market impact and order book dynamics may eat the edge. The HF data costs alone may exceed the alpha. Signal decay means latency is critical. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 82 | 32.8 |
| Replication Quality | 20% | 55 | 11.0 |
| Economic Plausibility | 15% | 65 | 9.75 |
| Implementation Simplicity | 10% | 30 | 3.0 |
| Execution Robustness | 10% | 45 | 4.5 |
| Prop-Firm Compatibility | 5% | 65 | 3.25 |
| **TOTAL** | | | **64.3/100** |

---

## PAPER 8: Dynamic Cointegration in Pairs Trading (BEST MEAN-REVERSION FRAMEWORK)

| Field | Value |
|---|---|
| **Title** | Dynamic Cointegration in Pairs Trading: Evidence from Treasury and Equity Markets |
| **Authors** | Bowen Zhou |
| **Year** | 2025 |
| **Source** | Research Square (preprint) |
| **Asset class** | US Treasury yields + Chinese equities |
| **Trading horizon** | Daily |
| **Entry logic** | Rolling-window cointegration (Engle-Granger + Johansen). OU process for mean-reversion estimation. Grid-search threshold optimization. Kalman and particle filters for dynamic parameters. |
| **Exit logic** | Mean-reversion based (Z-score reversion) |
| **Risk management** | Structural break detection, time-varying parameter stability analysis |
| **Holding period** | Variable (days) |
| **Markets tested** | US Treasury yield curve (TNX-TYX) + Chinese equity pair (600036.SS – 000001.SS) |
| **Sample period** | Not fully stated |
| **Number of trades** | Not stated |
| **Sharpe ratio** | 1.103 (Chinese equity pair); −0.767 (Treasury pair) |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not reported |
| **Transaction costs** | ⚠️ Mentioned but details unclear |
| **Walk-forward** | ✅ Y (rolling-window walk-forward framework) |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N |
| **Code available** | ⚠️ Not stated |
| **Implementation difficulty** | 7/10 |
| **Prop-firm compatibility** | 4/10 (Chinese equities and Treasuries — limited for most prop firms) |
| **Live-trading suitability** | 5/10 (mixed results across asset classes) |
| **Main weaknesses** | Stark performance divergence between asset classes. Treasury pair has negative Sharpe. Only 2 pairs tested — very small sample. Preprint (not peer-reviewed). Static cointegration shown to be insufficient. |
| **Why it might fail in production** | The negative Sharpe on Treasuries shows this doesn't generalize across asset classes. Chinese equity results may not be replicable in US/european markets. Only 2 pairs is far too few for statistical significance. |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 68 | 27.2 |
| Replication Quality | 20% | 50 | 10.0 |
| Economic Plausibility | 15% | 70 | 10.5 |
| Implementation Simplicity | 10% | 55 | 5.5 |
| Execution Robustness | 10% | 50 | 5.0 |
| Prop-Firm Compatibility | 5% | 35 | 1.75 |
| **TOTAL** | | | **59.95/100** |

---

## PAPER 9: ML Bitcoin Trading — Walk-Forward Parameter Optimization (BEST METHODOLOGY TEMPLATE)

| Field | Value |
|---|---|
| **Title** | A novel approach to trading strategy parameter optimization using double out-of-sample data and walk-forward techniques |
| **Authors** | Tomasz Mroziewicz, Robert Ślepaczuk |
| **Year** | 2026 |
| **Source** | arXiv:2602.10785 (q-fin.TR) |
| **Asset class** | Multi-asset (methodological framework) |
| **Trading horizon** | Variable |
| **Entry logic** | General framework — tests trends and mean reversion signals with double OOS design |
| **Exit logic** | Strategy-dependent |
| **Risk management** | Walk-forward parameter optimization discipline |
| **Holding period** | Variable |
| **Markets tested** | Multiple |
| **Sample period** | Various |
| **Sharpe ratio** | N/A (methodology paper) |
| **Transaction costs** | ✅ Y (framework enforces it) |
| **Walk-forward** | ✅ Y (novel "double OOS" technique) |
| **Out-of-sample** | ✅ Y |
| **Code available** | ⚠️ Likely (Ślepaczuk lab) |
| **Implementation difficulty** | 7/10 |
| **Prop-firm compatibility** | N/A (framework, not strategy) |

### Score
| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Research Quality | 40% | 85 | 34.0 |
| Replication Quality | 20% | 70 | 14.0 |
| Economic Plausibility | 15% | 75 | 11.25 |
| Implementation Simplicity | 10% | 60 | 6.0 |
| Execution Robustness | 10% | 65 | 6.5 |
| Prop-Firm Compatibility | 5% | 50 | 2.5 |
| **TOTAL** | | | **74.25/100** |

---

## RANKING SUMMARY

| Rank | Paper | Score | Key Strength | Key Weakness |
|---|---|---|---|---|
| 1 | Deep et al. — Walk-Forward Framework | **87.25** | Methodological gold standard; fully honest | 0.55% returns, p=0.34 |
| 2 | Baskaran — Kalman Filter Pairs | **75.8** | Shows pairs trading is dead after costs | All Sharpe ratios negative |
| 3 | Bysik & Ślepaczuk — BTC Under Costs | **75.7** | Excellent cost-aware execution design | 65% return is BTC beta, not alpha |
| 4 | Mroziewicz & Ślepaczuk — Double OOS | **74.25** | Best validation methodology template | Framework only, no specific alpha |
| 5 | Pu et al. — Network Momentum | **68.0** | Novel cross-asset signal | No transaction costs, unclear OOS details |
| 6 | Shi et al. — Intraday Lead-Lag | **64.3** | HF lead-lag is real and strong | Requires HF infrastructure |
| 7 | Lebiedź & Ślepaczuk — DRL Multi-Pair | **60.7** | Sophisticated DRL framework | Only 10% significance, extreme complexity |
| 8 | Zhou — Dynamic Cointegration | **59.95** | Good framework, multi-asset test | Negative Sharpe on Treasuries |
| 9 | Deep Learning Stat Arb (Management Sci) | **55.25** | Published in top journal | Sharpe >3 is almost certainly false |

---

## CRITICAL META-OBSERVATIONS

### 1. The "Dead After Costs" Pattern
The most rigorous papers (Baskaran 2026, Deep 2025) show that **standard statistical arbitrage strategies on US equities are no longer profitable after transaction costs** in the 2020-2024 period. The era of simple pairs trading is over.

### 2. The Honesty Paradox
The papers with the most rigorous methodology (walk-forward, transaction costs, bootstrap inference) report the worst performance. The papers claiming the best performance (Sharpe >3) have the weakest methodology. This is the publication bias that Harvey (2016) warned about.

### 3. What Actually Works (Sort Of)
- **Cost-aware execution filters** (Bysik 2026): Only trade when signal magnitude exceeds cost threshold — this is the single most impactful technique
- **Regime-aware positioning** (Deep 2025): Strategies work in high-volatility regimes and fail in calm markets
- **Drawdown control via Kalman/HMM** (Baskaran 2026): Even when returns are negative, dynamic estimation dramatically reduces drawdowns
- **Network momentum** (Pu 2023): Cross-asset momentum spillover is the most promising signal category, but needs cost validation

### 4. What to Avoid
- Any paper claiming Sharpe >2 without full transaction cost modeling
- Pairs trading on US large-cap equities with daily rebalancing and <10bps costs
- Deep learning models without walk-forward validation
- Any strategy tested on only one asset pair or one market regime

### 5. Recommendations for NAS100 Backtesting
Based on this literature review, any NAS100 backtesting system should:
1. **Mandatory**: Implement cost-aware execution filtering (Bysik 2026 technique)
2. **Mandatory**: Use walk-forward validation with ≥14 OOS folds (Baskaran 2026 standard)
3. **Mandatory**: Report BCa bootstrap confidence intervals on Sharpe ratios
4. **Recommended**: Test regime-conditional performance (pre-2020 vs post-2020)
5. **Recommended**: Compare against buy-and-hold with bootstrap significance testing
6. **Avoid**: Static cointegration pairs — use dynamic (rolling-window) frameworks only
