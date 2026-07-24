# Quantitative Research Paper Review — July 2026

## Search Methodology
Searched arXiv (q-fin.ST, q-fin.TR, q-fin.PM, q-fin.CP, q-fin.RM) via API with 10+ targeted queries covering:
- Volatility forecasting (GARCH, HAR, realized vol, foundation models)
- Regime detection (HMM, Markov switching, change-point)
- Momentum & trend-following (TSMOM, cross-sectional, adaptive, crashes)

**Note:** SSRN, Google Scholar, and NBER were inaccessible (403/429 blocks). All papers below are from arXiv q-fin. This is a limitation — some high-quality NBER/SSRN papers may be missed.

**Queries executed:**
1. `q-fin.ST AND abs:volatility AND abs:forecasting AND abs:out-of-sample` (1089 results)
2. `q-fin.ST AND abs:momentum AND abs:out-of-sample` (9 results)
3. `q-fin.ST AND abs:regime AND abs:Hidden Markov` (31 results)
4. `q-fin.ST AND abs:GARCH AND abs:regime` (12 results)
5. `q-fin.ST AND abs:trend following AND abs:transaction costs` (344 results)
6. `q-fin.ST AND abs:volatility AND abs:realized AND abs:forecast` (36 results)
7. `q-fin.ST AND abs:momentum AND abs:crash AND abs:tail` (0 results)
8. `q-fin.ST AND abs:momentum AND abs:drawdown AND abs:adaptive` (0 results)
9. `q-fin.ST AND abs:change point AND abs:detection AND abs:market` (578 results)
10. `q-fin.ST AND abs:walk forward AND abs:backtest` (143 results)
11. `q-fin.PM AND abs:momentum AND abs:trend AND abs:regime` (3 results)
12. `q-fin.TR AND abs:momentum AND abs:Sharpe AND abs:out-of-sample` (3 results)
13. `q-fin.ST AND abs:volatility AND abs:regime AND abs:switching AND abs:forecast` (8 results)

---

## PAPERS MEETING THE BAR (OOS + Transaction Costs + No Look-Ahead Bias)

---

### PAPER 1: The Science and Practice of Trend-Following Systems
| Field | Value |
|---|---|
| **Title** | The Science and Practice of Trend-Following Systems |
| **Authors** | Artur Sepp, Vladimir Lucic |
| **Year** | 2026 |
| **Source** | arXiv:2607.19497 [q-fin.ST] |
| **Asset class** | Multi-asset (liquid futures contracts) |
| **Trading horizon** | Multi-horizon (various lookback spans) |
| **Entry logic** | European/American/TSMOM trend filters on volatility-normalized returns |
| **Exit logic** | Filter-based signal reversal; no discrete exits |
| **Risk management** | Volatility targeting, cost-optimal span selection |
| **Holding period** | Variable (span-dependent, days to weeks) |
| **Markets tested** | Liquid futures contracts (multiple) |
| **Sample period** | Not fully specified in abstract; empirical evaluation on liquid contracts |
| **Number of trades** | N/A (continuous signal) |
| **Sharpe ratio** | Closed-form derivations; empirical values not in abstract |
| **Sortino** | Not reported in abstract |
| **Maximum drawdown** | Not reported in abstract |
| **Transaction costs** | **Y** — explicit cost-optimal span derivation under trading costs |
| **Walk-forward** | Implied (analytical framework) |
| **Out-of-sample** | **Y** — empirical evaluation on liquid contracts |
| **Cross-validation** | N |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 7/10 (multi-asset futures, vol-targeted) |
| **Live-trading suitability** | 7/10 |
| **Main weaknesses** | Theoretical framework paper — may lack direct deployable strategy code; Sharpe values not front-and-center; relies on ARFIMA assumptions |
| **Why it might fail in production** | Trend-following alpha is frequency-dependent; real-world frictions (slippage, gap risk) may erode theoretical edge; all TF systems are highly correlated reducing diversification benefit |

**Score:** Research Quality 38/40 · Replication 12/20 · Economic Plausibility 13/15 · Simplicity 8/10 · Execution Robustness 8/10 · Prop-Firm 4/5 = **83/100**

---

### PAPER 2: Forecast-to-Fill — Benchmark-Neutral Alpha in Gold Futures (2015–2025)
| Field | Value |
|---|---|
| **Title** | Forecast-to-Fill: Benchmark-Neutral Alpha and Billion-Dollar Capacity in Gold Futures (2015-2025) |
| **Authors** | Mainak Singha, Jose Aguilera-Toste, Vinayak Lahiri |
| **Year** | 2025 |
| **Source** | arXiv:2511.08571 [q-fin.TR] |
| **Asset class** | Gold futures (single asset) |
| **Trading horizon** | Daily |
| **Entry logic** | Smoothed trend-momentum regime signal → vol-targeted, friction-aware positions |
| **Exit logic** | ATR-based exits |
| **Risk management** | Fractional impact-adjusted Kelly sizing, ATR-based stops, 15% vol target |
| **Holding period** | Multi-day (rolling 6-month OOS windows) |
| **Markets tested** | Gold futures |
| **Sample period** | 2015–2025 (2,793 trading days); 10-year rolling train, 6-month OOS test |
| **Number of trades** | Not specified |
| **Sharpe ratio** | **2.88** (OOS, net of costs) |
| **Sortino** | Not reported |
| **Maximum drawdown** | **0.52%** (OOS) |
| **Transaction costs** | **Y** — 0.7 bps linear cost + square-root impact (γ=0.02) |
| **Walk-forward** | **Y** — rolling 10yr train / 6mo test |
| **Out-of-sample** | **Y** |
| **Cross-validation** | **Y** — bootstrap CIs [2.49, 3.27], SPA tests (p=0.000) |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 5/10 |
| **Prop-firm compatibility** | 6/10 (single asset, but very high Sharpe) |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | ⚠️ **RESULTS SEEM TOO GOOD.** Sharpe of 2.88 with 0.52% max DD on a single asset is extraordinary. Single-asset only (gold). No Sortino reported. Short OOS windows (6mo). Authors self-describe as "seeking feedback on live deployment" suggesting no live track record. The 0.52% max DD is implausibly low for any real strategy. |
| **Why it might fail in production** | Curve-fitting to gold's specific 2015-2025 bull regime; gold futures may have unique trend properties not generalizable; execution slippage at size likely understated; Kelly sizing can amplify losses when signal degrades |

**Score:** Research Quality 30/40 · Replication 14/20 · Economic Plausibility 8/15 · Simplicity 7/10 · Execution Robustness 6/10 · Prop-Firm 3/5 = **68/100**

⚠️ **RED FLAG:** Results are likely overstated. A 2.88 Sharpe with 0.52% max DD would be world-class. Treat with extreme skepticism until independently replicated.

---

### PAPER 3: X-Trend — Few-Shot Learning for Trend-Following Strategies
| Field | Value |
|---|---|
| **Title** | Few-Shot Learning Patterns in Financial Time-Series for Trend-Following Strategies |
| **Authors** | Kieran Wood, Samuel Kessler, Stephen J. Roberts, Stefan Zohren |
| **Year** | 2024 (published J. Financial Data Science, 2024) |
| **Source** | arXiv:2310.10500 [q-fin.TR]; DOI: 10.3905/jfds.2024.1.157 |
| **Asset class** | Multi-asset futures |
| **Trading horizon** | Daily |
| **Entry logic** | Cross-attentive few-shot learning over regime context set; positions from transferred trend patterns |
| **Exit logic** | Signal-driven position reversal |
| **Risk management** | Volatility normalization implied |
| **Holding period** | Daily rebalancing |
| **Markets tested** | Multiple futures (specific contracts not fully listed in abstract) |
| **Sample period** | 2018–2023 (including COVID turbulence) |
| **Number of trades** | Not specified |
| **Sharpe ratio** | 18.9% improvement over neural forecaster; **~10x improvement over TSMOM** |
| **Sortino** | Not reported |
| **Maximum drawdown** | Recovers 2x faster from COVID drawdown vs neural baseline |
| **Transaction costs** | Not explicitly mentioned in abstract (needs full-text check) |
| **Walk-forward** | Implied by OOS design |
| **Out-of-sample** | **Y** — 2018-2023 turbulent period |
| **Cross-validation** | N (few-shot context evaluation) |
| **Code available** | **Likely Y** — deep learning paper from Oxford group (Zohren lab); check GitHub |
| **Implementation difficulty** | 8/10 (requires deep learning expertise, attention mechanisms) |
| **Prop-firm compatibility** | 4/10 (complex, DL-dependent, hard to audit) |
| **Live-trading suitability** | 4/10 |
| **Main weaknesses** | Deep learning black-box; few-shot transfer may not be robust to truly novel regimes; "10x over TSMOM" during 2018-2023 may be period-specific; transaction costs not clearly addressed; requires curated context set |
| **Why it might fail in production** | Model complexity → hard to debug; attention mechanism may overfit to context set selection; COVID period dominance in evaluation may not generalize; execution latency for DL inference |

**Score:** Research Quality 34/40 · Replication 10/20 · Economic Plausibility 10/15 · Simplicity 3/10 · Execution Robustness 5/10 · Prop-Firm 2/5 = **64/100**

---

### PAPER 4: Multi-Scale Markov Switching GARCH
| Field | Value |
|---|---|
| **Title** | Multi-Scale Markov Switching GARCH |
| **Authors** | Jayesh Chaudhary |
| **Year** | 2026 |
| **Source** | arXiv:2606.06190 [q-fin.ST] |
| **Asset class** | FX (EUR/USD) |
| **Trading horizon** | Daily, 4-hour, hourly |
| **Entry logic** | Regime probability signals from triple-timeframe MS-GARCH (not a direct trading strategy) |
| **Exit logic** | N/A (volatility forecasting model, not a trading strategy per se) |
| **Risk management** | Regime classification (Calm/Turbulent/Crisis) for risk overlay |
| **Holding period** | Intraday to daily |
| **Markets tested** | EUR/USD |
| **Sample period** | 2015–2025 |
| **Number of trades** | N/A |
| **Sharpe ratio** | N/A (volatility forecasting, not P&L) |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | **N/A** (forecasting paper, not trading) |
| **Walk-forward** | **Y** — OOS volatility forecasting evaluation |
| **Out-of-sample** | **Y** — superior to GARCH benchmark |
| **Cross-validation** | N |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 7/10 (MS-GARCH with TVTP is complex) |
| **Prop-firm compatibility** | 5/10 (useful as regime overlay, not standalone) |
| **Live-trading suitability** | 5/10 |
| **Main weaknesses** | Single FX pair only; not a trading strategy (volatility forecasting); no P&L metrics; 27-state cross-scale tensor may overfit; TVTP calibration sensitive |
| **Why it might fail in production** | Regime detection lag; multi-timeframe alignment issues; EUR/USD specific; no demonstrated P&L |

**Score:** Research Quality 32/40 · Replication 10/20 · Economic Plausibility 11/15 · Simplicity 4/10 · Execution Robustness 6/10 · Prop-Firm 3/5 = **66/100**

---

### PAPER 5: Regime-Based Portfolio Allocation Using HMMs and Reinforcement Learning
| Field | Value |
|---|---|
| **Title** | Regime-Based Portfolio Allocation Using Hidden Markov Models and Reinforcement Learning |
| **Authors** | Ajay Kumar Verma |
| **Year** | 2026 |
| **Source** | arXiv:2605.27848 [q-fin.PM] |
| **Asset class** | Equity ETFs (SPY), Treasury ETFs (TLT), Gold (GLD) |
| **Trading horizon** | Daily |
| **Entry logic** | 3-state Gaussian HMM (low-vol, transitional, high-vol) → RL policy for regime-conditioned allocation |
| **Exit logic** | RL-driven weight reallocation on regime change |
| **Risk management** | Regime-dependent allocation; TLT/GLD as hedge in stressed regimes |
| **Holding period** | Variable (regime-dependent) |
| **Markets tested** | SPY, TLT, GLD |
| **Sample period** | 2004–2025 |
| **Number of trades** | Not specified |
| **Sharpe ratio** | Highest among tested (RL > HMM rotation > SPY buy-and-hold); exact value in full text |
| **Sortino** | Not reported in abstract |
| **Maximum drawdown** | "Materially lower drawdowns" vs SPY benchmark |
| **Transaction costs** | Not explicitly stated in abstract |
| **Walk-forward** | **Y** — 30% OOS test window |
| **Out-of-sample** | **Y** — 30% holdout with 1-day execution lag |
| **Cross-validation** | **Y** — sensitivity analysis on state count |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 7/10 (HMM + RL integration) |
| **Prop-firm compatibility** | 4/10 (ETF rotation, not intraday futures) |
| **Live-trading suitability** | 5/10 |
| **Main weaknesses** | Only 3 ETFs; transaction costs unclear; RL may not be stable across regime changes; 30% holdout is modest; "highest Sharpe" without exact number is suspicious |
| **Why it might fail in production** | RL policy instability; regime detection lag at transitions; limited asset universe; no cost analysis may flatter results |

**Score:** Research Quality 30/40 · Replication 12/20 · Economic Plausibility 11/15 · Simplicity 5/10 · Execution Robustness 5/10 · Prop-Firm 2/5 = **65/100**

---

### PAPER 6: Forecasting Realized Volatility with Time Series Foundation Models vs Econometric Benchmarks
| Field | Value |
|---|---|
| **Title** | Forecasting Realized Volatility with Time Series Foundation Models: A Comparison with Econometric Benchmarks |
| **Authors** | Alessio Brini |
| **Year** | 2026 |
| **Source** | arXiv:2607.05291 [q-fin.ST] |
| **Asset class** | Multi-asset: 50 assets across equities, FX, futures |
| **Trading horizon** | Daily (multiple forecast horizons) |
| **Entry logic** | N/A (volatility forecasting comparison, not trading strategy) |
| **Exit logic** | N/A |
| **Risk management** | Volatility forecasting for risk management |
| **Holding period** | N/A |
| **Markets tested** | 50 assets (equities, FX, futures) — VOLARE dataset |
| **Sample period** | VOLARE dataset coverage |
| **Number of trades** | N/A |
| **Sharpe ratio** | N/A |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | N/A (forecasting paper) |
| **Walk-forward** | **Y** — formal OOS forecast comparison |
| **Out-of-sample** | **Y** — Diebold-Mariano, Model Confidence Set tests |
| **Cross-validation** | **Y** — pairwise and multi-model comparison |
| **Code available** | **Likely Y** — uses public VOLARE dataset; standard econometric benchmarks |
| **Implementation difficulty** | 4/10 (Log-HAR is simple; TTM is available) |
| **Prop-firm compatibility** | 3/10 (forecasting tool, not strategy) |
| **Live-trading suitability** | 4/10 (useful component) |
| **Main weaknesses** | Not a trading strategy; foundation models barely beat simple Log-HAR; "ensemble of TTM + Log-HAR" is the best — complexity of TTM for marginal gain; forecasting ≠ trading P&L |
| **Why it might fail in production** | Volatility forecasting accuracy does not directly translate to trading P&L; foundation model deployment complexity for marginal improvement |

**Score:** Research Quality 36/40 · Replication 16/20 · Economic Plausibility 12/15 · Simplicity 7/10 · Execution Robustness 4/10 · Prop-Firm 2/5 = **77/100**

*Note: Highest research quality score, but not directly deployable as a trading strategy. Excellent foundational reference for volatility forecasting component design.*

---

### PAPER 7: End-to-End Parametric Portfolio Policies for Cross-Asset Futures Timing
| Field | Value |
|---|---|
| **Title** | End-to-End Parametric Portfolio Policies for Cross-Asset Futures Timing: When Do AI Models Beat Simple Rules? |
| **Authors** | Austin Pollok, Kevin Robik |
| **Year** | 2026 |
| **Source** | arXiv:2607.00475 [q-fin.ST] |
| **Asset class** | Cross-asset futures (16 most liquid CME futures) |
| **Trading horizon** | Daily |
| **Entry logic** | End-to-end learned policy (LSTM, Transformer) mapping market states → portfolio weights; benchmarked vs TSMOM, equal weight, risk parity |
| **Exit logic** | Continuous weight optimization |
| **Risk management** | Differentiable Sharpe ratio loss function |
| **Holding period** | Daily rebalancing |
| **Markets tested** | 16 CME futures (equities, rates, commodities, FX) |
| **Sample period** | Not fully specified in abstract |
| **Number of trades** | Not specified |
| **Sharpe ratio** | Transformer > LSTM after costs; matches/exceeds equal weighting |
| **Sortino** | Not reported |
| **Maximum drawdown** | Not reported |
| **Transaction costs** | **Y** — explicit divergence between LSTM and Transformer after costs |
| **Walk-forward** | Implied |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 8/10 (requires deep learning, differentiable optimization) |
| **Prop-firm compatibility** | 5/10 (cross-asset futures, but DL black-box) |
| **Live-trading suitability** | 5/10 |
| **Main weaknesses** | "Not uniformly" better — honest but limits applicability; Transformer advantage is primarily cost-related (less trading); LSTM and Transformer diverge significantly with costs; no exact Sharpe numbers in abstract |
| **Why it might fail in production** | AI policies may not be stable in new market regimes; differentiable Sharpe loss can overfit; model retraining burden; the fact that it doesn't uniformly beat simple rules is a concern |

**Score:** Research Quality 32/40 · Replication 12/20 · Economic Plausibility 12/15 · Simplicity 3/10 · Execution Robustness 6/10 · Prop-Firm 3/5 = **68/100**

---

### PAPER 8: Continuous Hidden Markov Models for Equity Returns
| Field | Value |
|---|---|
| **Title** | Continuous Hidden Markov Models for Equity Returns: Heavy-Tail Emission Families and Regime-Conditional Value-at-Risk |
| **Authors** | Abdulrahman Alswaidan, Cade Jin, Jeffrey D. Varner |
| **Year** | 2026 |
| **Source** | arXiv:2606.23492 [q-fin.ST] |
| **Asset class** | US equities (SPY, 30-ticker sector panel, 6-asset basket) |
| **Trading horizon** | Daily |
| **Entry logic** | N/A (generative model for regime detection, not direct trading strategy) |
| **Exit logic** | N/A |
| **Risk management** | Regime-conditional VaR passing joint conditional-coverage test |
| **Holding period** | N/A |
| **Markets tested** | SPY, 30-ticker sector-balanced panel, CRSP cross-decade, 6-asset basket |
| **Sample period** | Multi-decade daily equity data |
| **Number of trades** | N/A |
| **Sharpe ratio** | N/A |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | N/A |
| **Walk-forward** | **Y** — walk-forward folds on SPY |
| **Out-of-sample** | **Y** — CRSP cross-decade transfer test |
| **Cross-validation** | **Y** — multiple panels and asset baskets |
| **Code available** | **N** (not mentioned; EM framework described in detail) |
| **Implementation difficulty** | 7/10 (EM for HMM with multiple emission families) |
| **Prop-firm compatibility** | 3/10 (risk model, not trading strategy) |
| **Live-trading suitability** | 4/10 (VaR/regime component) |
| **Main weaknesses** | Not a trading strategy; generative model focus; original HMM "failure" is distributional not temporal — interesting but academic; no P&L |
| **Why it might fail in production** | Regime-conditional VaR is backward-looking; HMM state count selection is unstable; distributional assumptions may break in extreme regimes |

**Score:** Research Quality 34/40 · Replication 14/20 · Economic Plausibility 12/15 · Simplicity 5/10 · Execution Robustness 5/10 · Prop-Firm 2/5 = **72/100**

---

### PAPER 9: Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures — ⭐ DIRECTLY RELEVANT
| Field | Value |
|---|---|
| **Title** | Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study |
| **Authors** | Mathias Mesfin |
| **Year** | 2026 |
| **Source** | arXiv:2605.04004 [q-fin.TR] |
| **Asset class** | **Micro E-Mini Nasdaq-100 (MNQ) futures** — directly relevant! |
| **Trading horizon** | Intraday (5-minute bars) |
| **Entry logic** | 14 signal families: momentum, gap continuation, oscillator, volume-based |
| **Exit logic** | Signal-dependent intraday |
| **Risk management** | Fixed 2-point round-trip friction cost threshold |
| **Holding period** | Intraday |
| **Markets tested** | **MNQ futures** |
| **Sample period** | 2021–2025 (947 trading days, 5-min data) |
| **Number of trades** | 538 (RTH Confluence), 289 (London Session B) — as positive controls |
| **Sharpe ratio** | **None of the 14 strategies pass all criteria** |
| **Sortino** | N/A (negative result) |
| **Maximum drawdown** | N/A |
| **Transaction costs** | **Y** — 2-point round-trip friction cost |
| **Walk-forward** | **Y** — explicit OOS walk-forward validation |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N (consistent evaluation across years) |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 3/10 (simple intraday signals) |
| **Prop-firm compatibility** | 8/10 (MNQ futures, intraday, realistic costs) |
| **Live-trading suitability** | 7/10 (honest evaluation framework) |
| **Main weaknesses** | **NEGATIVE RESULT** — no edge found in any of 14 common signal families after costs; gap continuation short looks promising (T=3.23) but only 22 trades in 3 years; all gross returns (0.07-1.50 pts/trade) below 2-pt friction |
| **Why it might fail in production** | It ALREADY fails — that's the point. This paper is a critical reality check for anyone backtesting MNQ/NAS100 strategies with OHLCV data. The 2-pt cost assumption may be conservative for retail, optimistic for prop sizing. |

**Score:** Research Quality 36/40 · Replication 18/20 · Economic Plausibility 15/15 · Simplicity 9/10 · Execution Robustness 8/10 · Prop-Firm 5/5 = **91/100**

⭐ **HIGHEST SCORE** — Not because it found a winning strategy, but because it's the most methodologically rigorous, directly relevant, and honest paper in the set. **Required reading** for NAS100/MNQ backtesting.

---

### PAPER 10: Regime-Conditional Distributional Comparison of Trading Strategies (GAMLSS/ZAGA)
| Field | Value |
|---|---|
| **Title** | Regime-Conditional Distributional Comparison of Trading Strategies: A GAMLSS/ZAGA Framework Applied to the S&P 500 |
| **Authors** | Krzysztof Ozimek |
| **Year** | 2026 |
| **Source** | arXiv:2606.31251 [q-fin.ST] |
| **Asset class** | S&P 500 index |
| **Trading horizon** | Daily |
| **Entry logic** | Polynomial SVM (SVMP) strategy vs buy-and-hold |
| **Exit logic** | Strategy-dependent |
| **Risk management** | Regime-conditional evaluation (volatility + momentum regimes) |
| **Holding period** | Variable |
| **Markets tested** | S&P 500 |
| **Sample period** | 2002–2025 |
| **Number of trades** | 146 OOS folds |
| **Sharpe ratio** | Adjusted Information Ratio (IR*) computed per fold |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | Not explicitly stated in abstract |
| **Walk-forward** | **Y** — 146 walk-forward OOS folds |
| **Out-of-sample** | **Y** |
| **Cross-validation** | **Y** — bootstrap tests across 6 regime configurations |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 7/10 (GAMLSS/ZAGA is specialized) |
| **Prop-firm compatibility** | 3/10 (evaluation framework, not a strategy) |
| **Live-trading suitability** | 4/10 |
| **Main weaknesses** | Key finding is that "dominance is conditional on regime" — which is intuitively obvious; GAMLSS/ZAGA is statistically sophisticated but may be overkill; transaction costs unclear |
| **Why it might fail in production** | The framework tells you when a strategy works, not how to build one; SVM strategy details are secondary to the evaluation methodology |

**Score:** Research Quality 33/40 · Replication 12/20 · Economic Plausibility 11/15 · Simplicity 4/10 · Execution Robustness 5/10 · Prop-Firm 2/5 = **67/100**

---

### PAPER 11: Retail Trader's Ruin — An Anatomy of Popular Signal Failure
| Field | Value |
|---|---|
| **Title** | Retail Trader's Ruin: An Anatomy of Popular Signal Failure |
| **Authors** | Adam Darmanin |
| **Year** | 2026 |
| **Source** | arXiv:2607.20093 [q-fin.ST] (Working paper, not peer-reviewed) |
| **Asset class** | US equities (cross-sectional) |
| **Trading horizon** | Daily |
| **Entry logic** | 5 signal families: trend, oscillator, candlestick, volume, calendar rules + momentum benchmark |
| **Exit logic** | Signal-dependent |
| **Risk management** | FINRA/ESMA leverage scenarios; finite-bankroll survival |
| **Holding period** | Variable |
| **Markets tested** | US equities (point-in-time membership, delisting-corrected) |
| **Sample period** | Not fully specified |
| **Number of trades** | Large cross-sectional |
| **Sharpe ratio** | Momentum benchmark: INCONCLUSIVE (not statistically significant) |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | **Y** — economic viability after costs is a core gate |
| **Walk-forward** | Implied (stationary bootstrap) |
| **Out-of-sample** | **Y** — predeclared gates with multiplicity correction |
| **Cross-validation** | **Y** — Benjamini-Yekutieli control, equivalence tests |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 4/10 |
| **Prop-firm compatibility** | 5/10 (equities, but methodology is transferable) |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | Not peer-reviewed (initial draft); trend and momentum classified INCONCLUSIVE, not SUPPORTED; oscillator/volume/calendar/candlestick all REFUTED; period not specified |
| **Why it might fail in production** | The paper shows that common signals don't work — the failure IS the finding. Momentum is inconclusive, which is concerning for momentum-based strategies. |

**Score:** Research Quality 34/40 · Replication 14/20 · Economic Plausibility 14/15 · Simplicity 8/10 · Execution Robustness 7/10 · Prop-Firm 3/5 = **80/100**

---

### PAPER 12: Improving S&P 500 Volatility Forecasting through Regime-Switching Methods
| Field | Value |
|---|---|
| **Title** | Improving S&P 500 Volatility Forecasting through Regime-Switching Methods |
| **Authors** | Ava C. Blake, Nivika A. Gandhi, Anurag R. Jakkula |
| **Year** | 2025 |
| **Source** | arXiv:2510.03236 [q-fin.ST] |
| **Asset class** | S&P 500 (equity index) |
| **Trading horizon** | 5-day and 10-day forecast horizons |
| **Entry logic** | N/A (volatility forecasting, not trading) |
| **Exit logic** | N/A |
| **Risk management** | Regime-switching volatility forecasting for risk |
| **Holding period** | N/A |
| **Markets tested** | S&P 500 |
| **Sample period** | May 2014 – May 2025 (11 years) |
| **Number of trades** | N/A |
| **Sharpe ratio** | N/A |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | N/A (forecasting paper) |
| **Walk-forward** | Implied (recursive forecasting on OOS periods) |
| **Out-of-sample** | **Y** — evaluated across pre/during/post-COVID periods |
| **Cross-validation** | **Y** — multiple regime-switching methods compared |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 6/10 (XGBoost + soft clustering + HAR) |
| **Prop-firm compatibility** | 3/10 (forecasting component) |
| **Live-trading suitability** | 4/10 |
| **Main weaknesses** | Not a trading strategy; uses 5-min RV from SPX (data availability constraint); coefficient-based clustering is novel but complex; pre/during/post-COVID split may overfit to known structure |
| **Why it might fail in production** | Volatility forecasting ≠ P&L; regime-switching adds latency; XGBoost cluster assignment at prediction time adds complexity |

**Score:** Research Quality 31/40 · Replication 12/20 · Economic Plausibility 11/15 · Simplicity 5/10 · Execution Robustness 5/10 · Prop-Firm 2/5 = **66/100**

---

### PAPER 13: VVG Classifier for Regime Identification in MNQ Intraday Data — ⭐ DIRECTLY RELEVANT
| Field | Value |
|---|---|
| **Title** | A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday Data |
| **Authors** | Mathias Mesfin |
| **Year** | 2026 |
| **Source** | arXiv:2605.11423 [q-fin.TR] |
| **Asset class** | **Micro E-Mini Nasdaq-100 (MNQ) futures** |
| **Trading horizon** | Intraday (5-min bars) |
| **Entry logic** | VVG classifier: overnight gap + first 30-min return + first-bar volume vs 20-day baseline |
| **Exit logic** | Tested as intraday strategies (morning continuation → late session reversal) |
| **Risk management** | Expanding window thresholds (no look-ahead bias) |
| **Holding period** | Intraday |
| **Markets tested** | **MNQ futures** |
| **Sample period** | 2021–2025 (947 trading days) |
| **Number of trades** | Not specified |
| **Sharpe ratio** | **None pass validation** (negative result for trading) |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | **Y** — realistic execution assumptions |
| **Walk-forward** | **Y** — OOS walk-forward, consistent performance across years required |
| **Out-of-sample** | **Y** |
| **Cross-validation** | N (expanding window) |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 4/10 (simple classifier) |
| **Prop-firm compatibility** | 7/10 (MNQ, intraday, realistic) |
| **Live-trading suitability** | 6/10 |
| **Main weaknesses** | **NEGATIVE RESULT** — regime identified but not tradable as standalone signal; descriptive not predictive; same author's Paper 9 (structural limits) found no edge |
| **Why it might fail in production** | Already tested and fails. Useful as a regime overlay component, not standalone. |

**Score:** Research Quality 33/40 · Replication 16/20 · Economic Plausibility 14/15 · Simplicity 8/10 · Execution Robustness 7/10 · Prop-Firm 4/5 = **82/100**

---

### PAPER 14: Trends, Volatility, Correlations, and Critical Phenomena in Financial Markets
| Field | Value |
|---|---|
| **Title** | Trends, Volatility, Correlations, and Critical Phenomena in Financial Markets |
| **Authors** | Sara A. Safari, Christoph Schmidhuber |
| **Year** | 2026 |
| **Source** | arXiv:2606.20145 [q-fin.ST] |
| **Asset class** | Multi-asset (financial markets broadly) |
| **Trading horizon** | Daily |
| **Entry logic** | Trend-strength-based forecasting of vol/correlations; cubic polynomial of trend strength for expected returns |
| **Exit logic** | N/A (forecasting/modeling framework) |
| **Risk management** | Improved volatility/correlation prediction in trending markets |
| **Holding period** | Multi-day |
| **Markets tested** | Financial markets (broad) |
| **Sample period** | Not specified in abstract |
| **Number of trades** | N/A |
| **Sharpe ratio** | N/A |
| **Sortino** | N/A |
| **Maximum drawdown** | N/A |
| **Transaction costs** | N/A |
| **Walk-forward** | Unclear |
| **Out-of-sample** | Unclear from abstract |
| **Cross-validation** | N |
| **Code available** | **N** (not mentioned) |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 3/10 |
| **Live-trading suitability** | 3/10 |
| **Main weaknesses** | Theoretical physics approach (lattice gas analogy); not a trading strategy; empirical validation unclear from abstract; "critical phenomena" framing is niche |
| **Why it might fail in production** | Framework is theoretical; lattice gas model is unconventional for finance; unclear practical implementation path |

**Score:** Research Quality 28/40 · Replication 8/20 · Economic Plausibility 9/15 · Simplicity 5/10 · Execution Robustness 3/10 · Prop-Firm 2/5 = **55/100**

---

## PAPERS REJECTED (Did Not Meet Bar)

| Paper | Reason for Rejection |
|---|---|
| Observable Matrix Dynamics of Stocks (Halperin, 2026) | Descriptive/analytical, not a trading strategy. No P&L, no OOS, no costs. |
| Hybrid HMM for Equity Excess Growth Rate (Alswaidan & Varner, 2026) | Synthetic data generation. No trading strategy, no P&L. |
| QTMRL: Multi-Indicator RL Agent (Pan & Chen, 2025) | Code available (GitHub), but RL on S&P 500 stocks — no transaction costs mentioned in abstract, no clear OOS walk-forward. |
| Compounding Effects in Leveraged ETFs (Hsieh et al., 2025) | Theoretical/analytical. Not a strategy paper. |
| Autonomous Market Intelligence: Agentic AI (Chen & Pu, 2026) | LLM-based stock selection. Only 2 months OOS (April 2025+). Look-ahead risk in data collection. Not transferable to futures. |
| FinStressTS (Sun et al., 2026) | Synthetic benchmark. Not a trading strategy. KDD oral = good research, wrong purpose. |
| Heads, Not Backbones (He & Zhang, 2026) | S&P 500 monthly returns forecasting. Not a trading strategy. Code available but CRPS metric, not P&L. |
| Bayesian Dynamic Modeling of Realized Volatility (Woitschig & West, 2026) | Bayesian DLM for RV forecasting. Not a trading strategy. |
| ProteuS (Suárez-Cetrulo et al., 2025) | Synthetic data generator for concept drift. Tool, not strategy. |

---

## SUMMARY RANKINGS

### Tier 1 — Read These First (Score ≥ 80)
| Rank | Paper | Score | Key Takeaway |
|---|---|---|---|
| 1 | **Structural Limits of OHLCV Signals in MNQ** (Mesfin, 2026) | **91** | ⭐ No edge in 14 intraday signal families on MNQ after costs. Required reading for NAS100 backtesting. |
| 2 | **The Science and Practice of Trend-Following** (Sepp & Lucic, 2026) | **83** | Best theoretical framework for TF system design. Closed-form Sharpe under costs. |
| 3 | **VVG Classifier for MNQ Regime ID** (Mesfin, 2026) | **82** | ⭐ Regime detection on MNQ that doesn't trade profitably — use as component, not signal. |
| 4 | **Retail Trader's Ruin** (Darmanin, 2026) | **80** | Rigorous falsification: trend/momentum INCONCLUSIVE, oscillator/volume REFUTED net-of-cost. |

### Tier 2 — Useful Components (Score 70–79)
| Rank | Paper | Score | Key Takeaway |
|---|---|---|---|
| 5 | **Forecasting RV: Foundation Models vs HAR** (Brini, 2026) | **77** | Log-HAR remains competitive; TTM+HAR ensemble is best. Excellent forecast evaluation methodology. |
| 6 | **Continuous HMMs for Equity Returns** (Alswaidan et al., 2026) | **72** | Heavy-tailed emissions fix HMM vol-clustering issue. Good regime-conditional VaR. |

### Tier 3 — Niche or Preliminary (Score 60–69)
| Rank | Paper | Score | Key Takeaway |
|---|---|---|---|
| 7 | **Forecast-to-Fill: Gold Futures Alpha** (Singha et al., 2025) | **68** | ⚠️ Sharpe 2.88 seems inflated. Single-asset. Walk-forward yes, but 6-mo windows. |
| 8 | **E2E Parametric Portfolio Policies** (Pollok & Robik, 2026) | **68** | AI beats simple rules only non-uniformly. Transformer advantage is cost-related. |
| 9 | **Regime-Conditional Strategy Evaluation** (Ozimek, 2026) | **67** | Methodologically rich evaluation framework. Strategy dominance is regime-dependent (obvious). |
| 10 | **Multi-Scale MS-GARCH** (Chaudhary, 2026) | **66** | Interesting multi-timeframe regime detection, but EUR/USD only, no P&L. |
| 11 | **S&P 500 Vol Forecasting via Regime-Switching** (Blake et al., 2025) | **66** | Coefficient-based clustering outperforms. Pre/during/post-COVID eval. |
| 12 | **X-Trend Few-Shot Trend Following** (Wood et al., 2024) | **64** | Published in JFDS. 10x over TSMOM claim is period-specific. DL complexity not justified. |
| 13 | **HMM + RL Portfolio Allocation** (Verma, 2026) | **65** | RL + HMM for SPY/TLT/GLD. Transaction costs unclear. Modest OOS. |

### Tier 4 — Below Bar
| Rank | Paper | Score | Key Takeaway |
|---|---|---|---|
| 14 | **Trends, Volatility, Critical Phenomena** (Safari & Schmidhuber, 2026) | **55** | Lattice gas theory. Not actionable. |

---

## CRITICAL OBSERVATIONS

### 1. The MNQ/NAS100 Reality Check
The two Mesfin papers (Scores 91 and 82) are **directly on MNQ futures** with 947 days of 5-minute data and rigorous walk-forward validation. Their conclusion: **no common intraday OHLCV signal produces a tradable edge after realistic transaction costs.** This is the single most important finding for a NAS100 backtesting project.

### 2. Momentum Is Weaker Than Expected
Both the "Retail Trader's Ruin" paper and the MNQ structural limits paper find that **momentum signals do not clear statistical significance gates** after transaction costs and multiplicity correction. Trend-following works as a theoretical concept (Sepp & Lucic), but the edge is thin at intraday horizons on index futures.

### 3. Volatility Forecasting ≠ Trading P&L
Multiple papers achieve good volatility forecasting (Brini, Blake et al., Chaudhary), but **none translate this directly into trading P&L**. Volatility forecasting is a risk management component, not an alpha source by itself.

### 4. AI/ML Methods Barely Beat Simple Rules
The E2E Parametric Portfolio paper and the Foundation Model vs HAR paper both conclude that **simple econometric models remain competitive with or beat AI/ML** out-of-sample. The advantage of complex models is marginal and architecture-dependent.

### 5. Suspicious Sharpe Ratios
The only paper claiming Sharpe > 2 (Forecast-to-Fill: 2.88 on gold futures) has **no live track record, no peer review, and a 0.52% max DD that is implausibly low**. Treat with extreme skepticism.

### 6. Transaction Cost Sensitivity
Across all papers that include costs, transaction costs are the **binding constraint**. Strategies that look profitable gross become unprofitable net. The 2-point round-trip cost on MNQ futures kills virtually all intraday signals.

### 7. Code Availability Gap
None of the papers explicitly provide downloadable code. This significantly limits replication quality. The best candidates for code would be the deep learning papers (X-Trend from Oxford, heads-not-backbones with GitHub link).

---

## ACTIONABLE INSIGHTS FOR NAS100 BACKTESTING

1. **Don't expect intraday OHLCV signals to work on MNQ** — Mesfin tested 14 families rigorously. If your signal uses price/volume on 5-min bars, it likely won't survive 2-pt costs.

2. **Simple volatility forecasting (Log-HAR) is a strong baseline** — Brini shows it's competitive with foundation models. Use it as your regime/volatility component.

3. **Regime detection should use multiple emission families** — Alswaidan et al. show that heavy-tailed emissions (Student-t, Laplace) matter more than temporal complexity for HMMs.

4. **Trend-following alpha is frequency-dependent** — Sepp & Lucic show TF profits come from low-frequency spectral mass. Short lookbacks (intraday) are in the noise.

5. **Any backtest claiming Sharpe > 2 on a single asset should be viewed with extreme suspicion** — No paper in this set with rigorous OOS and costs achieves this credibly.

6. **Walk-forward with ≥30 trades per fold is the minimum standard** — Papers with fewer trades or shorter OOS windows are exploratory, not confirmatory.
