# AUDIT: HKUDS/Vibe-Trading vs the NAS100 system

_2026-07-14. Read-only audit; no code merged or modified. Source: github.com/HKUDS/
Vibe-Trading (v0.1.11, Jul 2026). Infrastructure only; NO strategy changes considered._

## Framing (the decisive difference)
**Vibe-Trading is a broad AI RESEARCH PLATFORM** — natural-language → analysis/backtest/
report, 68 tools, 13 LLM providers, 461 alpha factors, 19 data sources, multi-market
engines, React/FastAPI/Docker, 16 messaging channels. Its centre of gravity is
open-ended *discovery*.

**Your system is a focused, validated EXECUTION book** — 8 frozen strategies, a
governance regime (clock resets, committee, evidence month), broker-side risk, an
MT5→private-repo→Mac evidence bridge. Its centre of gravity is *faithfully trading a
proven edge and proving it live*.

Consequence: most of Vibe's surface is discovery machinery that, for your current goal
(pass a prop challenge with a frozen book), is **complexity without benefit** — and
several of its headline features (NL→strategy-code, 461 factors) would directly violate
your own governance (frozen, no new indicators). Only its *data-quality* and *validation-
robustness* infrastructure is genuinely additive.

## Comparison

### 1. Already present in your system (equivalent exists)
| Vibe-Trading | Your equivalent |
|---|---|
| Multi-LLM agent runtime (13 providers) | `llm_bridge` / `delegate` (Qwen 7B/14B, GLM, Ollama), verified end-to-end |
| Backtest validation (walk-forward, OOS) | the gauntlet (IS/OOS, 6/6 split, costs-on, corr<0.3) |
| Broker connectors (10) | Broker ABC + MT5/Alpaca/Binance adapters (the 3 you actually trade) |
| Safety: kill switch, mandate gates, audit ledger | DD-throttle, daily/monthly kill-switches, naked-order guard, `fills.csv` ledger |
| Shadow account / counterfactual backtest | forward-shadow (`shadow_signals.csv`) + fill↔broker reconciliation + A/B/C/D re-cost |
| Research workflow / hypothesis registry | Research OS (ideas/papers/experiments, committee, graveyard, RESEARCH_BACKLOG) |
| Messaging channels (16) | Telegram alerts + dead-man's-switch (you need 1, not 16) |
| Run cards / persistence | evidence manifests (SHA-256), `EVIDENCE_LEDGER`, `reports/latest.json` |
| Trade attribution | LOSING_TRADE_FORENSICS, WEEKEND_EXPOSURE_AUDIT, RESEARCH_TO_LIVE_FORENSICS |
| MCP tool access | consumed via the harness (ToolSearch); you don't need to *host* a server |

### 2. Genuinely missing (Vibe has it, you don't)
| Feature | Note |
|---|---|
| **OHLC/data-quality sanity checks** (reject dirty bars) | you have no formal bad-bar gate in the loaders/exporter |
| **Bootstrap CI + Monte-Carlo permutation** validation | you use walk-forward + 6/6 split; these add distributional robustness |
| **Benchmark comparison panel** (strategy vs QQB buy-hold) | you check corr-to-QQQ but have no side-by-side benchmark view |
| **AST-sandboxed code execution** | only relevant if you ran model-generated code — you don't (delegation is read-only text) → mostly N/A |
| **FastAPI REST / MCP server** for programmatic control | you drive via CLI + Streamlit + launcher, not an API |
| **FTS5 session search** | nice-to-have over the vault/logs |

### 3. Would improve your infrastructure (the useful subset of #2)
| Feature | Why it helps YOUR goal |
|---|---|
| OHLC sanity / bad-bar rejection | a corrupt bar → a wrong signal/fill → a bad committee number; cheap guard, high protection |
| Bootstrap CI / MC permutation | strengthens the re-cost + month-end evidence the committee actually decides on |
| Benchmark panel | frames live/backtest R against the passive QQQ line — one honest chart |

### 4. Duplicates existing work (adopting = rebuild what you have)
Multi-LLM runtime, backtest engines, shadow account, kill-switches/mandate gates,
research workflow, messaging, persistence/run-cards, trade attribution. You already have
leaner, governance-integrated versions of all of these. Importing Vibe's would fork the
truth and add a second framework — the exact thing your recent missions forbade.

### 5. Complexity without measurable benefit (for a frozen validated book)
| Vibe feature | Why it doesn't pay off here |
|---|---|
| **461 Alpha Zoo factors** | discovery; you're FROZEN, no new strategies — huge surface, zero benefit now |
| **NL → strategy code generation** | violates your governance (validated lineage, no invented indicators); adds risk |
| **Multi-market engines** (A-share/India/futures/options) | you trade NAS100/gold/BTC only |
| **16 messaging channels** | you have Telegram; 15 more = noise + secrets sprawl |
| **React frontend / FastAPI / Docker / MCP server** | replaces your working Streamlit + launcher + git-clone VPS = pure churn |
| **Swarm multi-agent (committees)** | your targeted delegation covers real needs; swarm = token burn |
| **87 finance skills / 68 tools** | broad exploration, mismatched to a focused validated book |

---

## Ranked recommendations (productivity gain × effort; infra only)
| # | Recommendation | Gain | Effort | Verdict |
|---|---|---|---|---|
| 1 | **Add OHLC/bad-bar sanity checks** to the data loaders + evidence exporter (drop/flag non-monotonic time, zero/negative prices, high<low, stale bars) | HIGH | LOW | **DO** — protects every downstream number; pure infra |
| 2 | **Add a benchmark panel** to the dashboard (strategy/live R vs QQQ buy-hold over the window) | MED | LOW | **DO** — one honest chart, reuses existing data |
| 3 | **Add Bootstrap-CI / MC-permutation** to the validation/re-cost battery | MED | MED | **CONSIDER post-window** — strengthens committee evidence; not urgent |
| 4 | **Read-only status/evidence REST endpoint** (thin FastAPI over existing artifacts) | LOW-MED | MED | **OPTIONAL** — only if you want programmatic/remote access |
| 5 | Everything in section 5 (factors, NL-codegen, multi-market, Docker/React, swarm, 16 channels) | — | HIGH | **DO NOT** — complexity without benefit; several violate your freeze/governance |

## Verdict
Vibe-Trading is an impressive *discovery* platform, but you are past discovery and in
*evidence*. **Borrow ideas, not the codebase:** adopt its data-quality discipline
(#1, high value/low effort) and optionally its validation-robustness methods (#3) — both
pure infrastructure, no strategy change, no new framework. Reject its discovery surface;
importing it would fork your single-source-of-truth and re-introduce the "second
framework / new strategies" your governance explicitly bans. One verified data-quality
gate is worth more to your prop-challenge goal than 461 factors you're frozen from using.
