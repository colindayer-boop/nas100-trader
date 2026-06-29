# HUNT LOG - Edge Hunting Results

| Idea | IS Sharpe | OOS Sharpe | OOS Max DD | Trades | Corr to QQQ | Gauntlet Pass | Notes |
|------|-----------|------------|------------|--------|-------------|---------------|-------|
| 1. Funding Rate Carry | ERROR | ERROR | ERROR | ERROR | ERROR | FAIL | Exception: Already tz-aware, use tz_convert to convert.... |

## 2026-06-30 — re-run by working environment (CLI scripts were all broken: tz bugs, syntax errors, missing imports)
| idea | IS Sharpe | OOS Sharpe | OOS DD | verdict |
|---|---|---|---|---|
| #1 funding carry (BTC, always-on) | 17.1 | 24.7 | -0.4% | REAL edge BUT idealized/frictionless — Sharpe>2.5 = flag. Real ~2-4 after costs. Tail risk (FTX-style). Best find of the hunt. |
| #1 funding carry (toggling+cost) | 6.1 | -1.0 | -11% | FAILS — costs eat carry; must run continuously |
| #2-7 (CLI scripts) | — | — | — | NOT RUN — CLI's scripts had tz/syntax/import bugs; rebuild needed |
