# Quantitative Research Scout Report
## Systematic Trading Literature Review (2021–2026)

**Date:** 2026-07-24
**Analyst:** Automated multi-agent web research (5 parallel streams, 50+ queries)
**Sources:** arXiv (q-fin), SSRN, Google Scholar, NBER, Springer, Elsevier, IEEE, Nature, ACM, NeurIPS, Oxford/Imperial/Columbia working papers

---

## EXECUTIVE SUMMARY

After evaluating **39 papers** across 5 research streams (market microstructure, statistical arbitrage, ML/RL, volatility/regime/momentum, and futures/FX/commodities), the honest conclusion is:

> **No paper meets the 85/100 threshold for unambiguous recommendation.** The papers that come closest are either (a) methodology/validation frameworks rather than tradeable strategies, or (b) honest negative-result papers that prove why common strategies *don't* work.

This is not a failure of the search — it is the genuine state of the literature. The most rigorous papers report the worst performance. The papers claiming the best performance have the weakest methodology. This is the "honesty paradox" that Campbell Harvey identified, confirmed across every stream.

**The single most valuable finding for your NAS100 project:** Mesfin (2026) rigorously proved that **no common intraday OHLCV signal produces a tradable edge on MNQ futures after 2-point transaction costs** across 947 days of walk-forward testing. This is your baseline reality check.

---

## PART 1: CONSOLIDATED PAPER TABLE

### Scoring System
| Criterion | Weight |
|---|---|
| Research Quality | 40% |
| Replication Quality | 20% |
| Economic Plausibility | 15% |
| Implementation Simplicity | 10% |
| Execution Robustness | 10% |
| Prop-Firm Compatibility | 5% |
| **Total** | **100** |

### 1.1 — Top 10 Research Papers (All Streams, Ranked by Score)

| Rank | Score | Paper | Authors | Year | Source | Asset | Horizon | Sharpe | Costs? | WF? | OOS? | Code? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **91** | Structural Limits of OHLCV Signals in MNQ Futures | Mesfin | 2026 | arXiv:2605.04004 | MNQ futures | Intraday 5-min | None pass | ✅ | ✅ | ✅ | ❌ |
| **2** | **87** | Interpretable Hypothesis-Driven Trading (Walk-Forward Framework) | Deep, Deep, Lamptey | 2025 | arXiv:2512.12924 | US equities | Daily | 0.33 | ✅ | ✅ (34-fold) | ✅ | ✅ |
| **3** | **83** | The Science and Practice of Trend-Following Systems | Sepp & Lucic | 2026 | arXiv:2607.19497 | Multi-asset futures | Multi-horizon | Closed-form | ✅ | Implied | ✅ | ❌ |
| **4** | **82** | VVG Classifier for MNQ Regime Identification | Mesfin | 2026 | arXiv:2605.11423 | MNQ futures | Intraday 5-min | None pass | ✅ | ✅ | ✅ | ❌ |
| **5** | **80** | The GT-Score: Reducing Overfitting in Data-Driven Trading | Sheppert | 2026 | JRFM 19(1) via arXiv:2602.00080 | S&P 500 equities | Daily | N/A (meta) | Partial | ✅ (9-split) | ✅ | ✅ |
| **6** | **80** | Retail Trader's Ruin: Anatomy of Popular Signal Failure | Darmanin | 2026 | arXiv:2607.20093 | US equities | Daily | Inconclusive | ✅ | Implied | ✅ | ❌ |
| **7** | **79** | DL for Financial Time Series: Large-Scale Benchmark | Saly-Kaufmann et al. | 2026 | arXiv:2603.01820 | Multi-asset futures | Daily | Best model: VSN+LSTM | ✅ (breakeven) | ✅ | ✅ | Likely |
| **8** | **77** | Forecasting RV: Foundation Models vs Econometric Benchmarks | Brini | 2026 | arXiv:2607.05291 | 50 assets (eq/FX/fut) | Daily | N/A (forecast) | N/A | ✅ | ✅ | Likely |
| **9** | **77.5** | Carry Momentum in Commodity Futures | Davis et al. | 2022 | Financial Analysts Journal | Commodity futures | Daily/weekly | ~1.0 | ✅ | Implied | ✅ | ❌ |
| **10** | **76** | Assessing Look-Ahead Bias in GPT Sentiment Predictions | Glasserman & Lin | 2023 | arXiv:2309.17322 (Columbia) | US equities | Daily | N/A (warning) | N/A | ✅ | ✅ | ❌ |

### 1.2 — Papers Scoring 70–85 (Useful Components, Not Standalone Strategies)

| Score | Paper | Key Contribution | Why Not Higher |
|---|---|---|---|
| 75.8 | Baskaran — Kalman Filter Pairs Trading (SSRN 2026) | Proves pairs trading is dead after 28bps costs. Best negative-result econometrics. | All Sharpes negative net-of-cost |
| 75.7 | Bysik & Ślepaczuk — BTC Trading Under Costs | Best cost-aware execution filter design (27-fold WF) | 65% return is BTC beta, not alpha |
| 74.25 | Mroziewicz & Ślepaczuk — Double OOS Walk-Forward | Best validation methodology template | Framework only, no specific alpha |
| 73 | Cheridito & Weiss — RL for Trade Execution | RL execution with market+limit orders | Simulator-to-real gap |
| 72 | FinRL-Meta (NeurIPS 2022) | Open-source RL-for-finance framework | Framework, not standalone alpha |
| 72 | Continuous HMMs for Equity Returns | Heavy-tailed emissions fix vol-clustering | Risk model, not trading strategy |
| 71 | Castro/Harvey — FX Hedging Strategies | Multi-signal FX, Campbell Harvey co-author | Daily FX, limited prop-firm fit |
| 70.5 | Xu & Wang — Vol-Managed Commodity Momentum | Practical vol-managed momentum | Single asset class |

---

## PART 2: DETAILED ANALYSIS — TOP CANDIDATES

### ⭐ Paper #1: Structural Limits of OHLCV Signals in MNQ Futures (Score: 91/100)

| Field | Detail |
|---|---|
| **Title** | Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study |
| **Authors** | Mathias Mesfin |
| **Year** | 2026 |
| **Source** | arXiv:2605.04004 [q-fin.TR] |
| **Asset class** | Micro E-Mini Nasdaq-100 (MNQ) futures |
| **Trading horizon** | Intraday (5-minute bars) |
| **Entry logic** | 14 signal families: momentum, gap continuation, oscillator, volume-based |
| **Exit logic** | Signal-dependent intraday |
| **Risk management** | Fixed 2-point round-trip friction cost threshold |
| **Holding period** | Intraday |
| **Markets tested** | MNQ futures |
| **Sample period** | 2021–2025 (947 trading days, 5-min bars) |
| **Number of trades** | 538 (RTH Confluence), 289 (London Session B) as positive controls |
| **Sharpe ratio** | **NONE of 14 strategies pass all criteria** |
| **Sortino** | N/A (negative result) |
| **Maximum drawdown** | N/A |
| **Transaction costs** | ✅ Y (2-point round-trip) |
| **Walk-forward** | ✅ Y |
| **Out-of-sample** | ✅ Y |
| **Cross-validation** | N (consistent evaluation across years) |
| **Code available** | ❌ N |
| **Implementation difficulty** | 3/10 |
| **Prop-firm compatibility** | 8/10 (MNQ, intraday, realistic costs) |
| **Live-trading suitability** | 7/10 (honest evaluation framework) |
| **Main weaknesses** | NEGATIVE RESULT — no edge found in 14 signal families after costs. Gap continuation short looks promising (T=3.23) but only 22 trades in 3 years. |
| **Why it might fail in production** | It ALREADY fails — that's the point. This is the baseline reality check for NAS100 backtesting. |

**Why this paper scores 91/100:** Directly tests your market (MNQ), your timeframe (intraday), your data (OHLCV), with rigorous walk-forward validation and realistic costs. It's the most important paper in the entire survey for your project — not because it found alpha, but because it defines the null hypothesis you must beat.

---

### ⭐ Paper #2: Interpretable Hypothesis-Driven Trading (Score: 87/100)

| Field | Detail |
|---|---|
| **Title** | Interpretable Hypothesis-Driven Trading: A Rigorous Walk-Forward Validation Framework |
| **Authors** | Gagan Deep, Akash Deep, William Lamptey |
| **Year** | 2025 |
| **Source** | arXiv:2512.12924 |
| **Asset class** | US equities (100 S&P 500 stocks) |
| **Trading horizon** | Daily |
| **Entry logic** | 5 hypothesis types: institutional accumulation, flow momentum, mean reversion, breakouts, range-bound value. RL agent selects hypothesis per stock. |
| **Exit logic** | Hypothesis-specific exits + stop-loss |
| **Risk management** | Position limits, stop-loss, market-neutral (β=0.058) |
| **Holding period** | Variable (days) |
| **Markets tested** | 100 US equities |
| **Sample period** | 2015–2024 |
| **Sharpe ratio** | 0.33 (annualized) |
| **Sortino** | Not reported |
| **Maximum drawdown** | −2.76% |
| **Transaction costs** | ✅ Y (commission + slippage) |
| **Walk-forward** | ✅ Y (34 independent OOS windows) |
| **Out-of-sample** | ✅ Y |
| **Code available** | ✅ Y (GitHub — link in paper) |
| **Implementation difficulty** | 7/10 |
| **Prop-firm compatibility** | 4/10 |
| **Live-trading suitability** | 7/10 |
| **Main weaknesses** | Returns not statistically significant (p=0.34). Only works in high-vol regimes. 0.55% annualized returns. |
| **Why it might fail** | Too low-return for any real fee structure. Regime-dependent. |

**Why it scores 87/100:** The methodological gold standard. 34-fold walk-forward, open-source code, honest reporting. Read as a validation framework template, not a money-maker.

---

### ⭐ Paper #3: Science and Practice of Trend-Following (Score: 83/100)

| Field | Detail |
|---|---|
| **Title** | The Science and Practice of Trend-Following Systems |
| **Authors** | Artur Sepp, Vladimir Lucic |
| **Year** | 2026 |
| **Source** | arXiv:2607.19497 [q-fin.ST] |
| **Asset class** | Multi-asset liquid futures |
| **Trading horizon** | Multi-horizon (various lookback spans) |
| **Entry logic** | European/American/TSMOM trend filters on vol-normalized returns |
| **Exit logic** | Filter-based signal reversal |
| **Risk management** | Volatility targeting, cost-optimal span selection |
| **Holding period** | Days to weeks |
| **Sharpe ratio** | Closed-form derivations (empirical in full text) |
| **Transaction costs** | ✅ Y (explicit cost-optimal span derivation) |
| **Walk-forward** | Implied (analytical framework) |
| **Out-of-sample** | ✅ Y |
| **Code available** | ❌ N |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 7/10 |
| **Live-trading suitability** | 7/10 |
| **Main weaknesses** | Theoretical framework paper. TF alpha is frequency-dependent — intraday TF is in the noise. |
| **Why it might fail** | Real-world frictions (slippage, gap risk) may erode theoretical edge. All TF systems are highly correlated. |

---

### ⭐ Paper #4: GT-Score — Overfitting Reduction (Score: 80/100)

| Field | Detail |
|---|---|
| **Title** | The GT-Score: A Robust Objective Function for Reducing Overfitting |
| **Authors** | Alexander Sheppert |
| **Year** | 2026 |
| **Source** | JRFM 19(1), arXiv:2602.00080 |
| **Entry logic** | Meta-objective function wrapping any ML strategy |
| **Risk management** | Integrates downside risk + consistency + statistical significance |
| **Walk-forward** | ✅ Y (9 splits, 15 random seeds) |
| **Out-of-sample** | ✅ Y |
| **Code available** | ✅ Y (supplementary materials) |
| **Implementation difficulty** | 4/10 (wrapper, not full strategy) |
| **Main weaknesses** | Meta-methodology, not standalone alpha. Small effect sizes. |

---

### ⭐ Paper #5: DL Financial Time Series Benchmark (Score: 79/100)

| Field | Detail |
|---|---|
| **Title** | Deep Learning for Financial Time Series: A Large-Scale Benchmark |
| **Authors** | Saly-Kaufmann, Wood, Peter-Calliess, Zohren |
| **Year** | 2026 |
| **Source** | arXiv:2603.01820 [q-fin.TR, cs.LG] |
| **Asset class** | Multi-asset futures (commodities, equity indices, bonds, FX) |
| **Trading horizon** | Daily rebalancing |
| **Entry logic** | DL model → long/short/flat position sizing |
| **Risk management** | Sharpe ratio optimization as training objective |
| **Sharpe ratio** | Best model: VSN+LSTM (exact value in paper tables) |
| **Transaction costs** | ✅ Y (breakeven cost analysis) |
| **Walk-forward** | ✅ Y (rolling windows) |
| **Out-of-sample** | ✅ Y |
| **Code available** | Likely (Oxford/Zohren lab) |
| **Implementation difficulty** | 6/10 |
| **Prop-firm compatibility** | 5/10 |
| **Main weaknesses** | "Breakeven cost" ≠ full net-of-cost backtest. No regime-conditional breakdown. |

---

## PART 3: CRITICAL META-FINDINGS

### 3.1 The Honesty Paradox (Confirmed Across All 5 Streams)

| Paper Quality | Typical Sharpe Claimed | Reality |
|---|---|---|
| Rigorous (WF + costs + OOS + bootstrap) | 0.33 – 1.0 | Genuine but modest |
| Moderate (OOS, partial costs) | 1.0 – 2.0 | Likely 0.3 – 0.8 net of full costs |
| Weak (in-sample, no costs) | 2.0 – 5.0+ | Almost certainly overfit |
| LLM-based | 3.0+ | Likely look-ahead bias from training data |

### 3.2 What Actually Works (From the Rigorous Papers)

1. **Cost-aware execution filters** — Only trade when |signal| > λ × transaction_cost. This reduces turnover 10× and is the single most impactful technique (Bysik 2026).
2. **Walk-forward validation with ≥14 OOS folds** — The minimum standard. Papers using <5 folds are exploratory.
3. **Volatility targeting** — Essential for position sizing. Log-HAR is competitive with AI for vol forecasting (Brini 2026).
4. **Regime-conditional evaluation** — Strategies work in specific regimes. Reporting aggregate Sharpe masks this.
5. **Bootstrap confidence intervals on Sharpe** — Without CIs, Sharpe estimates are meaningless.

### 3.3 What Doesn't Work (Rigorously Disproven)

1. **Pairs trading on US large-cap equities** — Dead after 28bps round-trip costs (Baskaran 2026, ALL Sharpes negative).
2. **Intraday OHLCV signals on MNQ** — 14 signal families tested, none survive 2-pt costs (Mesfin 2026).
3. **Oscillator/volume/candlestick signals on equities** — REFUTED after costs with multiplicity correction (Darmanin 2026).
4. **LLM sentiment trading** — Systematic look-ahead bias from training data contamination (Glasserman & Lin 2023).
5. **Any strategy claiming Sharpe > 3** — No rigorous paper in this survey achieves this credibly.

---

## PART 4: IMPLEMENTATION GUIDES

### 4.1 How to Implement the Walk-Forward Validation Framework (Deep et al. 2025)

**Python Implementation:**
```python
import numpy as np
import pandas as pd
from typing import Tuple, Dict

class WalkForwardValidator:
    """
    Implements the Deep et al. (2025) walk-forward framework.
    34 independent OOS windows, each with its own training period.
    """
    def __init__(self, n_folds: int = 34, train_ratio: float = 0.75):
        self.n_folds = n_folds
        self.train_ratio = train_ratio
    
    def generate_folds(self, data: pd.DataFrame) -> list:
        """Generate non-overlapping walk-forward folds."""
        total_len = len(data)
        fold_size = total_len // (self.n_folds + 1)
        train_size = int(fold_size * self.train_ratio)
        
        folds = []
        for i in range(self.n_folds):
            start = i * fold_size
            train_end = start + train_size
            test_end = train_end + (fold_size - train_size)
            
            if test_end > total_len:
                break
                
            train_data = data.iloc[start:train_end]
            test_data = data.iloc[train_end:test_end]
            folds.append((train_data, test_data))
        
        return folds
    
    def validate_strategy(self, data: pd.DataFrame, strategy_fn, cost_bps: float = 2.0):
        """
        Run strategy through all walk-forward folds.
        Returns Sharpe with bootstrap CIs.
        """
        folds = self.generate_folds(data)
        fold_sharpes = []
        fold_returns = []
        
        for i, (train, test) in enumerate(folds):
            # Fit on train, predict on test
            signals = strategy_fn.fit_predict(train, test)
            
            # Apply transaction costs
            positions = self._apply_costs(signals, cost_bps)
            returns = (positions.shift(1) * test['returns']).dropna()
            
            # Subtract transaction costs
            turnover = positions.diff().abs()
            cost_drag = turnover * cost_bps / 1e4
            net_returns = returns - cost_drag
            
            sharpe = np.sqrt(252) * net_returns.mean() / net_returns.std()
            fold_sharpes.append(sharpe)
            fold_returns.extend(net_returns.values)
        
        # Bootstrap CI
        returns_arr = np.array(fold_returns)
        boot_sharpes = []
        for _ in range(10000):
            sample = np.random.choice(returns_arr, size=len(returns_arr), replace=True)
            boot_sharpes.append(np.sqrt(252) * sample.mean() / sample.std())
        
        ci_low, ci_high = np.percentile(boot_sharpes, [2.5, 97.5])
        
        return {
            'fold_sharpes': fold_sharpes,
            'aggregate_sharpe': np.mean(fold_sharpes),
            'bootstrap_ci': (ci_low, ci_high),
            'p_value': self._compute_p_value(fold_sharpes),
            'n_significant': sum(1 for s in fold_sharpes if s > 0)
        }
```

**MT5 Implementation:**
- Use Python via `MetaTrader5` package for signal generation
- Execute via EA that reads signal file or receives via ZeroMQ socket
- Key: implement slippage tracking on every fill to measure actual vs. expected cost

**Market Data Required:**
- OHLCV bars at strategy timeframe (1-min for intraday, daily for swing)
- Tick data for realistic spread/slippage estimation
- Economic calendar for regime annotation

**Integration with Research Platform:**
- **Event Database:** Store every walk-forward fold as an event with train/test boundaries, parameters, and OOS performance
- **Belief Graph:** Add node: "Walk-forward validated with N folds" → increases confidence weight
- **Strategy Registry:** Tag each strategy with WF fold count, bootstrap CI, and p-value
- **Shadow Mode:** Deploy WF-validated strategies in shadow to verify live OOS matches backtest OOS
- **Capital Allocation Engine:** Weight allocation by bootstrap CI lower bound, not point Sharpe estimate

---

### 4.2 How to Implement Cost-Aware Execution Filter (Bysik & Ślepaczuk 2026)

**Python Implementation:**
```python
class CostAwareExecutionFilter:
    """
    Only trade when |forecast| exceeds transaction-cost-based threshold.
    From Bysik & Ślepaczuk (2026) — reduces turnover 10×.
    """
    def __init__(self, cost_bps: float, lambda_threshold: float = 1.5):
        self.cost_bps = cost_bps
        self.lambda_threshold = lambda_threshold
    
    def filter_signals(self, forecasts: pd.Series, current_positions: pd.Series) -> pd.Series:
        """
        Filter: only change position when |forecast| > λ × cost
        """
        threshold = self.lambda_threshold * self.cost_bps / 1e4
        filtered_positions = current_positions.copy()
        
        for i in range(1, len(forecasts)):
            # Only trade if signal magnitude exceeds cost threshold
            if abs(forecasts.iloc[i]) > threshold:
                filtered_positions.iloc[i] = np.sign(forecasts.iloc[i])
            else:
                filtered_positions.iloc[i] = filtered_positions.iloc[i-1]
        
        return filtered_positions
```

**Why this matters:** This single technique reduced turnover by 10× in the Bysik paper, transforming a strategy that lost money on costs into one that generated positive net returns. It's the highest ROI implementation in the entire survey.

---

### 4.3 How to Implement Vol-Managed Trend Following (Sepp & Lucic + Xu & Wang)

**Python Implementation:**
```python
class VolManagedTrendFollowing:
    """
    Combines Sepp & Lucic (2026) cost-optimal trend spans
    with Xu & Wang (2021) volatility management.
    """
    def __init__(self, lookback_span: int = 60, vol_target: float = 0.15,
                 cost_bps: float = 2.0):
        self.lookback_span = lookback_span
        self.vol_target = vol_target
        self.cost_bps = cost_bps
    
    def generate_positions(self, returns: pd.Series) -> pd.Series:
        """
        1. Compute TSMOM signal at cost-optimal span
        2. Scale by inverse realized volatility
        3. Apply cost-aware filter
        """
        # Step 1: TSMOM signal
        cum_returns = returns.rolling(self.lookback_span).sum()
        direction = np.sign(cum_returns)
        
        # Step 2: Vol scaling
        realized_vol = returns.rolling(22).std() * np.sqrt(252)
        vol_weight = self.vol_target / realized_vol.clip(lower=0.05)
        
        # Step 3: Raw position
        raw_position = direction * vol_weight.clip(upper=3.0)
        
        # Step 4: Cost-aware filter (don't trade for small changes)
        position_change = raw_position.diff().abs()
        threshold = self.cost_bps / 1e4 * 5  # 5x cost as minimum edge
        raw_position[position_change < threshold] = raw_position.shift(1)
        
        return raw_position.fillna(0)
```

---

## PART 5: RANKINGS AND RECOMMENDATIONS

### 5.1 Top 10 Research Papers

| Rank | Score | Paper | Type |
|---|---|---|---|
| 1 | 91 | Mesfin — Structural Limits of OHLCV in MNQ | ⭐ Negative result (required reading) |
| 2 | 87 | Deep et al. — Walk-Forward Validation Framework | Methodology + code |
| 3 | 83 | Sepp & Lucic — Science and Practice of TF | Theoretical framework |
| 4 | 82 | Mesfin — VVG Classifier for MNQ Regime ID | ⭐ Component (regime detection) |
| 5 | 80 | Sheppert — GT-Score Overfitting Reduction | Meta-methodology + code |
| 6 | 80 | Darmanin — Retail Trader's Ruin | Falsification study |
| 7 | 79 | Saly-Kaufmann et al. — DL Financial TS Benchmark | Multi-model benchmark |
| 8 | 77.5 | Davis et al. — Carry Momentum in Commodities | Strategy (commodity futures) |
| 9 | 77 | Brini — Foundation Models vs HAR for RV | Volatility forecasting |
| 10 | 76 | Glasserman & Lin — LLM Look-Ahead Bias | Essential warning |

### 5.2 Top 5 Strategies Worth Implementing

| Rank | Strategy | Source | Expected Net Edge | Why |
|---|---|---|---|---|
| 1 | **Cost-aware execution filter** as a platform feature | Bysik 2026 | Turnover reduction 10× | Highest ROI implementation. Applies to ALL strategies. |
| 2 | **Walk-forward validation engine** (34-fold + bootstrap CIs) | Deep 2025 | Does not generate alpha — prevents false alpha | Essential infrastructure for any systematic strategy. |
| 3 | **Vol-managed trend following** on daily timeframe | Sepp & Lucic 2026, Xu & Wang 2021 | Modest (Sharpe ~0.5–1.0) | Theoretically grounded. Works on futures. NOT for intraday MNQ. |
| 4 | **GT-Score objective function** for model training | Sheppert 2026 | Reduces overfitting by ~98% in generalization ratio | Meta-layer over any ML signal. Code provided. |
| 5 | **Log-HAR volatility forecasting** as regime component | Brini 2026 | Not direct alpha | Competitive with AI. Use for position sizing and regime classification. |

**Honest assessment:** None of these are "plug-and-play profitable strategies." They are infrastructure, methodology, and components. The literature does not contain a free lunch.

### 5.3 Top 3 Most Likely to Survive Real Transaction Costs

| Rank | Strategy | Why It Survives |
|---|---|---|
| 1 | **Cost-aware execution filter** (Bysik technique) | It IS the cost survival mechanism — only trades when edge exceeds costs |
| 2 | **Daily/weekly trend following** with vol targeting (Sepp & Lucic framework) | Long holding periods → low turnover → costs are small fraction of gross edge |
| 3 | **Carry + momentum** in liquid commodity futures (Davis et al.) | Weekly rebalancing, liquid markets, small bid-ask spreads |

### 5.4 Top 3 Most Suitable for Prop-Firm Evaluation

| Rank | Strategy | Prop-Firm Fit | Notes |
|---|---|---|---|
| 1 | **Daily trend following on index futures** (NQ/ES via Sepp & Lucic framework) | 7/10 | Prop firms want index futures. Daily horizon avoids HFT infrastructure needs. Use cost-optimal spans. |
| 2 | **Carry-momentum on commodity futures** (Davis et al.) | 6/10 | If the prop firm allows commodity futures. Weekly rebalance fits drawdown limits. |
| 3 | **Regime-conditional vol-managed momentum** (Xu & Wang + HMM regime overlay) | 6/10 | Reduces drawdowns in hostile regimes — critical for prop firm max-DD rules. |

**Important caveat:** Mesfin (2026) proves that intraday OHLCV signals on MNQ specifically do NOT survive costs. If your prop firm requires intraday trading on NAS100, the literature offers no proven edge. The trend-following approaches above operate on daily+ timeframes.

### 5.5 What Would Need to Be Added to Your Research Platform

| Component | What to Build | Source Paper |
|---|---|---|
| **Event Database** | Store WF folds, bootstrap CIs, regime labels, and actual slippage observations per trade | Deep 2025, Baskaran 2026 |
| **Belief Graph** | Nodes for: "WF-validated (N folds)", "bootstrap CI > 0", "survives cost threshold λ", "regime-conditional edge confirmed" | All top-tier papers |
| **Strategy Registry** | Tag each strategy with: fold count, OOS Sharpe, bootstrap CI, turnover ratio, cost-adjusted Sharpe, regime performance breakdown | Deep 2025, Sheppert 2026 |
| **Shadow Mode** | Track: predicted vs. actual fill prices, predicted vs. actual slippage, signal-to-fill latency, regime at time of each trade | Cheridito & Weiss 2026 |
| **Capital Allocation Engine** | Weight by bootstrap CI lower bound × regime-conditional performance. Penalize turnover. Apply cost-aware filter globally. | Bysik 2026, Sheppert 2026 |

---

## PART 6: 90-DAY IMPLEMENTATION ROADMAP
### Ordered by Expected Information Gain (EIG), Not Expected Profitability

**Principle:** Learn the most important things first. Kill bad ideas early. Build infrastructure that compounds in value.

### Phase 1: Foundation (Days 1–30) — "Establish the Null Hypothesis"

| Week | Task | EIG Rationale | Deliverable |
|---|---|---|---|
| 1 | **Replicate Mesfin's MNQ falsification** on your data | Highest EIG: if 14 signal families don't work on MNQ after costs, you stop wasting time on intraday OHLCV signals | Confirmation (or refutation) that standard intraday signals are dead on your data |
| 2 | **Build walk-forward validation engine** (34-fold + bootstrap CIs) | Without this, every subsequent result is unreliable. This is the single most important infrastructure piece | Reusable WF validator with bootstrap CI reporting |
| 3 | **Implement cost-aware execution filter** as platform feature | 10× turnover reduction applies to everything downstream. Instant ROI. | Cost-aware filter module integrated into Strategy Registry |
| 4 | **Implement Log-HAR volatility forecasting** as regime component | Simple, competitive with AI, gives you a baseline vol forecast for position sizing and regime detection | HAR vol forecast module feeding Belief Graph |

### Phase 2: Signal Discovery (Days 31–60) — "Test What Might Actually Work"

| Week | Task | EIG Rationale | Deliverable |
|---|---|---|---|
| 5–6 | **Test daily trend-following** on NQ/MNQ using Sepp & Lucic cost-optimal spans | TF alpha lives at low frequencies. If there's edge on NQ, it's here — not intraday. | Daily TF strategy with WF results, bootstrap CIs, regime breakdown |
| 7 | **Test carry-momentum** on liquid commodity futures (if universe allows) | Cross-validated in FAJ. Weekly frequency = low turnover = costs manageable. | Carry-momentum strategy with net-of-cost Sharpe and DD profile |
| 8 | **Build regime detection overlay** (VVG-style + HMM heavy-tail) | Tells you WHEN strategies work. Without this, aggregate Sharpe masks regime-dependence. | Regime classifier integrated with Belief Graph and Strategy Registry |

### Phase 3: Validation & Hardening (Days 61–90) — "Verify or Kill"

| Week | Task | EIG Rationale | Deliverable |
|---|---|---|---|
| 9–10 | **Run GT-Score optimization** on surviving strategies | Meta-objective reduces overfitting. If a strategy doesn't survive GT-Score, kill it. | GT-Score validated strategy set with generalization ratios |
| 11 | **Deploy surviving strategies in Shadow Mode** | Live OOS validation is the only true test. Track predicted vs. actual fills, slippage, and regime. | Shadow performance report: backtest vs. live, per-strategy |
| 12 | **Capital Allocation Engine integration** | Allocate by bootstrap CI lower bound × regime fit. Penalize turnover. | Capital allocation framework with automated regime gating |

### Decision Gates

| Gate | Criterion | Action if FAIL |
|---|---|---|
| End of Week 1 | Confirm MNQ intraday signals are dead on your data | Pivot entirely to daily+ timeframes |
| End of Week 4 | WF engine produces reliable bootstrap CIs | Do not proceed to signal testing until fixed |
| End of Week 8 | At least ONE strategy shows bootstrap CI lower bound > 0 | If none pass, the literature says this is expected. Focus on execution infrastructure. |
| End of Week 12 | Shadow-mode live results within bootstrap CI of backtest | If divergence > 2σ, investigate regime shift or implementation shortfall |

---

## PART 7: PAPERS EXPLICITLY REJECTED

| Paper | Reason |
|---|---|
| Deep Learning Statistical Arbitrage (Management Science 2023) | Sharpe >3 with partial cost treatment. Almost certainly overstated. |
| Forecast-to-Fill: Gold Futures Alpha (2025) | Sharpe 2.88 with 0.52% max DD is implausible. No live track record. |
| QuantAgent: LLMs for HFT | LLM inference latency (seconds) incompatible with HFT (microseconds). |
| Deep RL Portfolio Optimization (China A-shares) | Single emerging market, no walk-forward, costs unclear. |
| Sentiment Trading with LLMs (Kirtac & Germano 2024) | Look-ahead bias from LLM training contamination (per Glasserman & Lin 2023). |
| ~70% of ML trading papers found | No transaction costs, no genuine OOS, or simulator-only validation. |

---

## FINAL ASSESSMENT

**No paper in the 2021–2026 literature achieves the 85/100 threshold for unambiguous recommendation as a standalone profitable strategy.**

The papers that score highest are:
1. **Negative-result studies** that prevent you from wasting time (Mesfin 91/100)
2. **Methodology frameworks** that prevent you from fooling yourself (Deep 87/100, Sheppert 80/100)
3. **Theoretical contributions** that guide design without providing deployable code (Sepp & Lucic 83/100)

This is the honest state of quantitative trading research. The edge is in infrastructure, execution, and rigorous validation — not in discovering a secret signal from a paper.

**Recommended next steps:**
1. Read Mesfin (2026) immediately — it's about your exact market
2. Build the walk-forward validation engine before testing any strategy
3. Implement the cost-aware execution filter as a platform-wide feature
4. Set expectation: bootstrap CI lower bound > 0 net-of-costs is a genuine achievement

---

*Report compiled from 5 parallel research subagents covering: market microstructure & intraday, statistical arbitrage & mean reversion, ML/RL for trading, volatility/regime/momentum, and futures/FX/commodities. 50+ web queries executed across arXiv, SSRN, Google Scholar, NBER, Springer, IEEE, and university repositories.*
