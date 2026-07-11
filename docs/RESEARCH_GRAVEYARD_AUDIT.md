# RESEARCH GRAVEYARD AUDIT -- 2026-07-12

_Every rejected idea, its reason, its evidence, and whether research SINCE the
rejection changes the conclusion. Sources: FINDINGS.md, HUNT_LOG.md (261 FAIL rows),
SWEEP_SUMMARY.md, review docs, research/archive. Nothing is resurrected here;
where new evidence exists it arrived through the pipeline, not this audit._

## Legend
STANDS = rejection unchanged | REFINED = boundary sharpened, core rejection intact |
SUPERSEDED (partial) = a successor variant passed review through the proper pipeline

| # | Idea | Reason rejected | Evidence | New research since? |
|---|---|---|---|---|
| 1 | IV Skew filter (Xing/Zhang/Zhao) | no tradeable edge on our book | FINDINGS S6 tests | STANDS |
| 2 | S6 IV Skew Reversal | no edge, data cost | FINDINGS | STANDS |
| 3 | S5-Short "Phase 1" filter stack | overfit stack, OOS decay | FINDINGS | STANDS |
| 4 | Multi-ETF sweep on IWM/DIA/TLT | failed per-instrument | FINDINGS (early test) | **SUPERSEDED (partial)**: Part A + adversarial review (07-12) keep **S5_DIA** (S5, not the originally-tested S1-sweep); IWM & TLT re-rejected on fresh 2021+ data. DIA lives in forward shadow via the pipeline |
| 5 | SPX/VIX divergence | disguised beta, died 2022 | FINDINGS | STANDS -- distinct from the ts-gate (curve slope vs level-divergence); no conflict |
| 6 | Volume Profile / LAT | no intraday MR edge at any bar frequency | FINDINGS "definitive" | STANDS |
| 7 | Short-interest boost (Asquith) | no edge | FINDINGS | STANDS |
| 8 | Dynamic exits (trailing/BE/partial) | kills the 3R winners the edge needs | FINDINGS | STANDS -- re-confirmed by vol-regime report's own adaptive-exit note |
| 9 | Foreign indices (Nikkei/DAX/CAC/HSI/KOSPI) | inconsistent/uncorrelatable | FINDINGS | STANDS |
| 10 | Pairs mean-reversion (GLD/GDX, KO/PEP, XLE/XOP, GLD/TLT) | deep DDs, wrong edge type | HUNT_LOG + sweep | STANDS |
| 11 | EWA/EWC pairs | split-luck (4/6, min OOS 0.06) | SWEEP_SUMMARY | STANDS -- HUNT_LOG's early PASS rows are formally superseded by the 6/6 rule |
| 12 | Cross-sectional / commodity COT | OOS decay | FINDINGS | STANDS |
| 13 | Funding carry | real edge, FTX-tail risk | FINDINGS (shelved) | STANDS as shelved -- no new tail-risk mitigation found |
| 14 | Overnight drift (generic, unconditional) | dies at retail costs | Boyarchenko et al. | **REFINED**: calendar-conditional OVN validated & live; RFS-2026 intraday-momentum mechanism replicates but REJECTED at our breadth (07-12). Generic rejection intact, boundaries now precise |
| 15 | ETF NAV arbitrage | AP/HFT-only | SSRN sweep | STANDS |
| 16 | Bollinger band systems | no robust post-cost edge | literature + own tests | STANDS |
| 17 | London Breakout straddle | arbitraged below costs; S1 fades its losing side | OOS -3.96/-6.19 | STANDS |
| 18 | SSRN intraday momentum (4824172) | post-publication decay | IS +1.32 / OOS -0.80 | STANDS -- survey triage re-confirmed |
| 19 | DIX dark-pool gate | sign-unstable, IS/OOS flip | FINDINGS 07 | STANDS -- macro-state work added no new mechanism |
| 20 | Turtle / Ultimate Oscillator / XS-mom (doc strategies) | gauntlet-rejected | test_doc_strategies | STANDS |
| 21 | Challenge cushion-governor sizing | loses to static in MC | prop_firm_optimizer A/B | STANDS |
| 22 | Stellar 1-Step account type | 3%/6% limits vs our tails | prop sim | STANDS |
| 23 | Forex sweep + forex TSMOM baskets | negative/weak OOS | session tests | STANDS -- strengthened by later CFD-financing law |
| 24 | TensorTrade adoption | overfit-industrialization, dep tax, no brackets | TENSORTRADE_EVALUATION | STANDS (defer) |
| 25 | ATR compression filter | look-ahead + post-hoc threshold; lagged version hurts everywhere | atr_compression_REVIEW (8 thresholds, 0/6, LOYO all-negative) | STANDS (rejected 07-12) |
| 26 | Yield-curve gate | 0/6 vs existing gate, one-era variation | MACRO_FILTER_REVIEW | STANDS (rejected 07-12) |
| 27 | Net-liquidity gate | full-sample artifact, 0/6 OOS | MACRO_FILTER_REVIEW | STANDS -- Part-B segmentation promise explicitly did not survive the gate test |
| 28 | HY credit-spread gate | destroys S5 (0.78->0.26) | MACRO_FILTER_REVIEW | STANDS |
| 29 | Breadth gate | no survivorship-safe free data | pre-registered | STANDS |
| 30 | TSMOM 8-ETF (as CFD book) | financing kills it (-0.08); ETF-side 0.45 below bar | Part C | STANDS -- financing law since re-confirmed twice (RFS momentum, industry-rotation triage) |
| 31 | Industry-rotation TSMOM | duplicates Part C economics | survey triage | STANDS (deferred, reopening condition recorded) |
| 32 | Range-based vol timing / semivol / Markov window / factor momentum | frozen sizing surface, contested lit (Cederburg 2020), tuning surface, wrong instruments | survey triage | STANDS |
| 33 | RFS-2026 intraday-return momentum | mechanism real, breadth-starved at 8 ETFs, CFD-dead | OVERNIGHT_MOMENTUM_REVIEW | STANDS (rejected 07-12; reopen only with a broad single-stock book) |

## Cross-cutting patterns the audit surfaces
1. **The CFD-financing law** is now the single most re-confirmed fact in the graveyard
   (TSMOM, RFS momentum, industry rotation, any monthly-hold idea): ~3 bps/day on
   notional is a structural filter on the whole strategy space. Slow ideas need the
   Alpaca sleeve or don't exist for us.
2. **Two rejections were later partially superseded -- both through the pipeline**
   (S5_DIA via Part A review; OVN via calendar conditioning). The graveyard is
   revisable, but only by full re-validation, never by nostalgia.
3. **Every 2026-07 rejection carries its falsification artifact** (review doc with
   the battery). Older rejections rest on FINDINGS prose -- adequate, but future
   rejections should keep the new standard.
4. No entry shows evidence justifying resurrection today.
