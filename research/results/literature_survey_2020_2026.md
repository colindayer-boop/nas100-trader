# Academic Literature Survey — Mission 3 Extension
## Ranked Research Candidates (2020–2026)

**Date**: 2026-07-12
**Scope**: intraday momentum, ORB, ETF trend following, volatility timing, macro regime filters
**Filters**: daily/hourly data | free data | explainable | prop compatible | multiple independent validations
**Prior rejections cross-checked**: yes (see FINDINGS.md)

---

## Ranking Criteria

Each candidate scored on:
- **Evidence depth** — how many independent papers validate it?
- **Data simplicity** — daily/hourly OHLCV only, or needs something exotic?
- **Cost robustness** — survives retail spreads/commissions?
- **Prop compatibility** — tradeable on CFD/futures with drawdown limits?
- **Novelty to us** — does it overlap with already-tested/rejected ideas?
- **Decay risk** — post-publication decay probability

Scale: ★ (weak) to ★★★★★ (very strong)

---

## TIER 1 — STRONG EVIDENCE, WORTH TESTING

### 1. ★★★★☆ Day/Night Return Decomposition (Intraday vs Overnight Momentum)
**Expected Research Value: HIGH**

| Field | Value |
|-------|-------|
| Core papers | Barardehi & Bogousslavsky (2026, RFS, cited 26×): "What Drives Momentum and Reversal? Evidence from Day and Night Signals" |
| Supporting | Dor & Zeng (2021, JPM): "Overnight Return Momentum: Evidence from European Markets"; Lou, Polk & Skouras (2019, RFS): "A Tug of War: Overnight vs Intraday Returns" |
| Data needed | Daily OHLC (close-to-open = overnight, open-to-close = intraday) |
| Mechanism | Stock momentum is an **overnight** phenomenon; intraday returns show reversal. Decomposing returns isolates the persistent component. |
| Prop compatible | ✅ — daily data, ETFs/futures/CFDs |
| Cost robust | ✅ — hold overnight, close next day |
| Multiple validations | ✅ — 30 countries (Barardehi), European markets (Dor/Zeng), US stocks (Lou/Polk/Skouras) |
| Novelty | **NEW to us** — our S1 sweeps overnight structure but we've never tested a pure overnight-hold momentum signal |
| Decay risk | LOW — overnight drift is structural (retail doesn't trade overnight, institutional rebalancing flows) |
| Why rank #1 | Strongest paper (RFS, 26 citations), simplest data (daily OHLC), structural mechanism, globally validated. Our S1 already exploits overnight session; a pure overnight momentum factor could be orthogonal or complementary. |

**Caveat**: Our FINDINGS.md already rejected "overnight drift" as "-0.5 to +0.3 after costs" from Boyarchenko/Larsen/Whelan. BUT that was a GENERIC overnight drift test. Barardehi's decomposition is more nuanced — the predictability is *conditional* on past returns. Worth distinguishing.

---

### 2. ★★★★☆ Industry Rotation Trend Following (Century-Long Validation)
**Expected Research Value: HIGH**

| Field | Value |
|-------|-------|
| Core paper | Zarattini & Antonacci (2024, SSRN 4857230): "A Century of Profitable Industry Trends" |
| Supporting | Moskowitz, Ooi & Pedersen (2012); Asness, Moskowitz & Pedersen (2013) |
| Data needed | Daily prices on 48 industry portfolios (free via Ken French Data Library) or sector ETFs |
| Mechanism | Long-only trend following on US industries: 12-month time-series momentum with monthly rebalancing. 100-year sample (1926–2024). |
| Prop compatible | ✅ — sector ETFs (XLK, XLE, XLV, etc.) or CFD equivalents |
| Cost robust | ✅ — monthly rebalancing, low turnover |
| Multiple validations | ✅ — Moskowitz/TSMOM validated this across asset classes; Zarattini extends to 100-year industry sample |
| Novelty | **NEW** — we tested multi-ETF Asian sweep (failed) and cross-sectional momentum (failed), but NOT long-only industry rotation via TSMOM with monthly rebalancing |
| Decay risk | LOW — 100 years of data, structural trend-following premium |
| Why rank #2 | Same author as our validated ORB paper (Zarattini). 100-year sample. Different timeframe (monthly vs our intraday) = likely uncorrelated. Free data. Simple. |

**Caveat**: Trend following at monthly horizon is a DIFFERENT edge type from our intraday sweeps. It may not help fill prop-firm daily drawdown constraints, but could be a swing overlay on a separate account sleeve.

---

### 3. ★★★☆☆ Range-Based Volatility Timing
**Expected Research Value: MEDIUM-HIGH**

| Field | Value |
|-------|-------|
| Core paper | Lehnert (2023, JPM): "Range-Based Volatility Timing" |
| Supporting | Moreira & Muir (2017, JF): "Volatility-Managed Portfolios" (the foundational paper); Engle (1982, ARCH) |
| Data needed | Daily OHLC — uses daily high-low range as volatility estimator (not just close-to-close) |
| Mechanism | Scale exposure inversely to range-based volatility. Range-based vol (Parkinson 1980, Garman-Klass 1980) is more efficient than close-to-close vol. |
| Prop compatible | ✅ — daily data, position sizing overlay |
| Cost robust | ✅ — it's a sizing overlay, not a new signal |
| Multiple validations | ✅ — Moreira & Muir replicated extensively; Lehnert shows range-based improves on close-based; Kang & Kwon (2021) confirm for commodity futures |
| Novelty | **PARTIAL** — we already use `vol_mult_for()` (Barroso & Santa-Clara close-based vol scaling). Range-based vol is a better estimator. Our Mission 3 showed vol scaling helps (Sharpe 1.12→1.24); range-based could improve further. |
| Decay risk | LOW — volatility clustering is structural |
| Why rank #3 | Upgrade to our existing vol scaler. Better vol estimate → better scaling → higher Sharpe. Low risk of overfitting. Free, simple, overlay-only. |

---

### 4. ★★★☆☆ Optimal Trend-Following Window via Markov Switching
**Expected Research Value: MEDIUM-HIGH**

| Field | Value |
|-------|-------|
| Core paper | Zakamulin & Giner (2022, SSRN 4092437): "Optimal Trend-Following in a Markov Switching Model" |
| Supporting | The entire trend-following literature; Faber (2007) for practical simplicity |
| Data needed | Daily prices |
| Mechanism | Rather than fixed moving-average windows, derive the optimal trend-following window analytically under a Markov regime-switching model. Shows that the optimal window is a function of regime persistence. |
| Prop compatible | ✅ — daily data, ETF/index level |
| Cost robust | ✅ — infrequent rebalancing |
| Multiple validations | PARTIAL — Zakamulin has a series of papers; bridges theory to practice. But fewer independent replications than #1–2. |
| Novelty | **NEW** — our TSMOM gate uses a fixed 252-day window. This suggests the optimal window varies with regime. |
| Decay risk | MEDIUM — optimal window estimation has parameter uncertainty |
| Why rank #4 | Could improve our existing TSMOM gate (currently 12-month fixed). Theoretical grounding for adaptive window length. But the improvement may be marginal over a well-chosen fixed window. |

---

## TIER 2 — PROMISING BUT WITH RESERVATIONS

### 5. ★★★☆☆ Overnight vs Daytime Momentum Across Sector ETFs
**Expected Research Value: MEDIUM**

| Field | Value |
|-------|-------|
| Core paper | Salotra, Katikireddy, Anumolu & Pinsky (2026, Risks): "A Comparative Analysis of Overnight vs Daytime Static and Momentum Strategies Across Sector ETFs" |
| Supporting | Lou, Polk & Skouras (2019); same overnight decomposition mechanism as #1 |
| Data needed | Daily OHLC on sector ETFs |
| Mechanism | Tests the overnight momentum anomaly specifically across sector ETFs (not just single stocks). |
| Prop compatible | ✅ — sector ETFs or CFD equivalents |
| Cost robust | ✅ — overnight hold, daily rebalancing |
| Multiple validations | PARTIAL — builds on established literature, first ETF-specific application |
| Novelty | **NEW** — we haven't tested the overnight effect on ETFs; our prior rejection was single-stock overnight drift |
| Decay risk | LOW — structural (overnight liquidity premium) |
| Why rank #5 | Directly applicable to our ETF data. Could add a daily-frequency strategy that's uncorrelated with our intraday sweeps. Single paper though — needs independent confirmation. |

---

### 6. ★★★☆☆ Factor Momentum with Regime-Switching Overlay
**Expected Research Value: MEDIUM**

| Field | Value |
|-------|-------|
| Core paper | Gu & Mulvey (2021, JFDS): "Factor Momentum and Regime-Switching Overlay Strategy" |
| Supporting | Ehsani & Linnainmaa (2022): "Factor Momentum and the Momentum Factor"; Arnott et al. (2023) |
| Data needed | Daily factor returns (free via Ken French or AQR data) |
| Mechanism | Standard factor momentum (time-series momentum applied to style factors: value, size, momentum, quality) + Markov regime-switching overlay that scales exposure based on regime probability. |
| Prop compatible | ⚠️ — requires trading factor-mimicking portfolios or factor ETFs |
| Cost robust | ✅ — monthly/quarterly rebalancing |
| Multiple validations | ✅ — factor momentum is among the most robust anomalies; Gu/Mulvey add the regime overlay |
| Novelty | **NEW** — different from our price-based strategies; this is factor-based |
| Decay risk | LOW for factor momentum; MEDIUM for the regime overlay improvement |
| Why rank #6 | Factor momentum is one of the most robust anomalies in finance. But it's a completely different edge type from our system, requiring different instruments. Implementation complexity is higher. |

---

### 7. ★★☆☆☆ Semivolatility-Managed Portfolios
**Expected Research Value: LOW-MEDIUM**

| Field | Value |
|-------|-------|
| Core paper | Batista & Fernandes (2024, SSRN 4891824): "Semivolatility-Managed Portfolios" |
| Supporting | Moreira & Muir (2017); Qiao, Yan & Deng (2020, JPM): "Downside Volatility-Managed Portfolios" |
| Data needed | Daily returns |
| Mechanism | Scale exposure using only downside volatility (negative returns), not total volatility. Theoretical motivation: downside risk is more persistent and more predictive than upside vol. |
| Prop compatible | ✅ — overlay sizing |
| Cost robust | ✅ |
| Multiple validations | ✅ — 3 independent papers on downside/semivolatility management |
| Novelty | **PARTIAL** — upgrade to our vol scaler (like #3 but different approach) |
| Decay risk | LOW |
| Why rank #7 | Clean theoretical improvement over standard vol scaling. But our Mission 3 showed vol scaling's marginal effect is modest (we already have `vol_mult_for` + DD-throttle). The semivolatility version may add slightly more, but the ceiling is low. |

---

### 8. ★★☆☆☆ Momentum Crash Risk via Volatility Scaling
**Expected Research Value: LOW-MEDIUM**

| Field | Value |
|-------|-------|
| Core paper | Gao & Yuan (2025, SSRN 6112846): "The Unpriced Risk in Momentum Strategies" |
| Supporting | Barroso & Santa-Clara (2015); Daniel & Moskowitz (2016): "Momentum Crashes" |
| Data needed | Daily returns |
| Mechanism | Momentum strategy crash risk is driven by volatility. Vol-scaled momentum eliminates the left tail (momentum crashes) without sacrificing average return. |
| Prop compatible | ✅ |
| Multiple validations | ✅ — this is one of the most replicated findings in finance |
| Novelty | **LOW** — we ALREADY implement Barroso & Santa-Clara vol scaling. This paper confirms the mechanism but doesn't add a new signal. |
| Why rank #8 | Confirms our existing approach is correct. Worth reading for the risk decomposition, but not a new tradeable idea. |

---

## REJECTED FROM SURVEY (with reasons)

### ❌ Intraday Momentum with Noise Bands + VWAP (Zarattini/Aziz SSRN 4824172)
**Already tested and REJECTED** in FINDINGS.md. IS Sharpe +1.32 → OOS Sharpe −0.80. Post-publication decay confirmed. Do not revisit.

### ❌ HMM-Based Intraday Momentum (Christensen, Godsill & Turner 2020, arXiv)
Requires intraday tick data for HMM state estimation. Not daily/hourly. Academic exercise without cost-aware backtest. Cited only 5×.

### ❌ Regime-Gated Momentum on Semiconductor Thematic (Lancaster 2026)
Single-author, non-peer-reviewed, instrument-specific (semiconductor ETFs). Tests a specific thematic rotation, not a generalizable mechanism.

### ❌ Fluid Regime Trading / Physics-Inspired Classification (Faria 2026)
Author's own post-mortem analysis shows the classification failed. Reynolds number distribution "heavily concentrated near zero." Self-rejected.

### ❌ RegimeFolio ML System (Zhang et al. 2025, IEEE Access)
Requires ML/LLM infrastructure, multi-modal inputs. Not explainable by our criteria. Cited 16× but it's a system paper, not a strategy paper.

### ❌ Leveraged ETF Momentum (Hsieh, Chang & Chen 2025)
LETs introduce path-dependent decay (volatility drag). Trading LETFs is a different risk profile from what prop firms allow. Not prop compatible.

### ❌ Standard Bollinger Band Strategies
Already rejected in FINDINGS.md. Academic literature consistently finds no robust post-cost edge for standard BB strategies.

### ❌ Volume-Price-Adjusted MACD (Lin et al. 2026)
arXiv preprint, cited 3×. Requires optimization (sensitivity calibration). Not multiple independent validations. Indicator-based with tuning risk.

### ❌ Q-Learning/DRL for Intraday Trading (Borkar & Jadhav 2026)
ML-based, not explainable. Not multiple validations. Overfits to sample period. Not prop compatible (black box).

### ❌ FX Intraday Technical Trading (Gurgel & Ferreira)
Brazilian FX market, not transferable to our instruments (NQ/Gold/BTC). Already confirmed: edge doesn't transfer to non-Nasdaq assets.

### ❌ Crypto Intraday ML (Wang, Wang & Zhou 2024)
Chinese stock market, HFT infrastructure required. Not free data, not explainable, not prop compatible.

---

## CROSS-REFERENCE WITH PRIOR REJECTIONS

| Prior Rejection | Relevant Candidate | Why Different? |
|-----------------|-------------------|----------------|
| Overnight drift (Boyarchenko) | #1 Day/Night Decomposition | Conditional on past returns, not unconditional drift |
| Intraday momentum (SSRN 4824172) | None — confirmed dead | Already decayed post-publication |
| Multi-ETF Asian Sweep | #2 Industry Rotation | Different mechanism (monthly TSMOM, not intraday sweep) |
| Pairs mean-reversion | #6 Factor Momentum | Different (factor momentum, not pairs spread) |
| Dynamic exits | None | All dynamic exit ideas remain rejected |
| VIX divergence | #4 Markov Switching Window | Replaces fixed window, not a VIX-based filter |

---

## RECOMMENDED TESTING ORDER

1. **#1 Day/Night Decomposition** — fastest to test (daily OHLC), strongest paper, structural mechanism. Test: does conditioning our S1 entries on overnight return direction improve edge? Or: build a standalone daily overnight-momentum factor.

2. **#2 Industry Rotation TSMOM** — free data (Ken French), monthly rebalancing, different frequency = guaranteed uncorrelated. Test: 48-industry TSMOM with our costs.

3. **#3 Range-Based Vol Scaling** — simple overlay upgrade. Replace `vol_mult_for()` close-based vol with Parkinson/Garman-Klass range-based vol. Measure Sharpe delta.

4. **#5 Sector ETF Overnight** — natural extension of #1, uses sector ETFs we already have data for.

5. **#4 Markov Window** — research-only, lower priority. Only if TSMOM gate improvements are needed.

---

## SUMMARY TABLE

| Rank | Candidate | Topic | Data | Validations | Prop | Score |
|------|-----------|-------|------|-------------|------|-------|
| 1 | Day/Night Return Decomposition | Intraday momentum | Daily OHLC | 3+ papers, 30 countries | ✅ | ★★★★☆ |
| 2 | Industry Rotation TSMOM | ETF trend following | Daily (Ken French) | 100yr sample + Moskowitz | ✅ | ★★★★☆ |
| 3 | Range-Based Vol Timing | Volatility timing | Daily OHLC | 3+ papers | ✅ | ★★★☆☆ |
| 4 | Markov Optimal Trend Window | Volatility timing | Daily | 1 strong paper | ✅ | ★★★☆☆ |
| 5 | Sector ETF Overnight Mom | Intraday momentum | Daily OHLC | 1 paper + literature | ✅ | ★★★☆☆ |
| 6 | Factor Momentum + Regime | Macro regime filter | Daily factor returns | 3+ papers | ⚠️ | ★★★☆☆ |
| 7 | Semivolatility-Managed | Volatility timing | Daily returns | 3 papers | ✅ | ★★☆☆☆ |
| 8 | Momentum Crash Risk | Volatility timing | Daily returns | 3+ papers | ✅ | ★★☆☆☆ |

**Bottom line**: Candidates #1 and #2 are the strongest leads. #1 is the most novel (we've never decomposed returns into day/night components despite trading overnight sessions). #2 is the most robust (100-year validation) but at a different frequency. #3 is a low-risk incremental upgrade. Everything else either overlaps with what we already do or lacks sufficient independent validation.
