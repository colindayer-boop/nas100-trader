# PRODUCTION READINESS REVIEW — 2026-07-09

_Verified by command, not by reading docs. Fixes implemented during this review are
marked **[FIXED TODAY]** and are on `main` (fd0ff25); the VPS auto-pulls them._

## Area-by-area verdict

| Area | Verdict | Evidence / notes |
|---|---|---|
| **Startup** | 🟢 [FIXED TODAY] | Was fatally broken on the work branch (SyntaxError L135 + args-before-parse). Healed; `py_compile` + full dry-run exit 0. `main` was never broken. |
| **Broker: MT5** | 🟢 | Auth verified live (equity 50k), symbol maps resolve with prices, atomic SL/TP brackets, min-stop clamped, server-UTC rebase verified. |
| **Broker: Alpaca** | 🟢 [FIXED TODAY] | Was naked (no sl/tp). Now BRACKET (sl+tp) / OTO (sl-only) orders. Paper-verified compile; first live paper fill will confirm. |
| **Risk engine** | 🟢 | DD-throttle (per-broker state), daily 5% / monthly 4% kill-switches, VIX regime scaling, equity<=0 guard [kept today]. `risk/` mode package exists but is **dormant/unwired** (inert — see blockers). |
| **Order submission** | 🟢 | `place_order_safe`: retry-with-backoff, no double-send, naked-order WARNING, TypeError fallback only for non-bracket brokers. |
| **Stop loss / Take profit** | 🟢 | S1/S2/S4/S5/SWEEP: broker SL+TP. S3: SL + 5-day time exit. BTC: SL+TP + reconcile. OVN: 5% catastrophe SL + time exit. Verified via test order + dry-run output (`BUY 83 QQQ SL=716.54 TP=745.49`). |
| **State recovery** | 🟡 | Per-broker risk state; BTC/OVN state files with broker-position reconcile (no re-sell into shorts). Gap: BTCTREND/XSMOM still bot-managed only. |
| **Logging** | 🟢 | Rotating trader.log + per-venue `mt5_<session>.log`, ASCII-safe output (post emoji-crash), UTF-8 reconfigure. |
| **Alerts** | 🟢 [IMPROVED TODAY] | Telegram wired + tested; FILL/kill-switch/broker-init alerts; daily heartbeat. **Added global `sys.excepthook` → CRASH alert** so an unhandled exception can never be silent again. |
| **Scheduler** | 🟢 | VPS `Nas100Bot-*` tasks Last Result 0 (verified via status.py), `PYTHONUTF8=1` in .bats, S5 watchdog canary, cooldown lock (guards concurrent runs), weekend skip. |
| **VPS deployment** | 🟢 | Real git clone, auto-pull every 30 min, secrets in gitignored config.ini. |

## Issues found (risk / probability / impact / fix)

1. **Uncommitted startup fix dangling on a side branch** — P: high (any future commit or checkout could ship/lose it) · I: catastrophic (non-running bot) → **[FIXED TODAY]** committed + merged to main.
2. **Alpaca naked orders** — P: certain on every Alpaca fill · I: medium (paper today, but a live migration would inherit it) → **[FIXED TODAY]** bracket/OTO.
3. **Silent crash path on VPS** — P: low-medium (any new unhandled exception) · I: high (repeat of the 6-day silent outage) → **[FIXED TODAY]** global excepthook → Telegram.
4. **test_order.py could fire on a live account** — P: low · I: high → **[FIXED TODAY]** demo guard (`--live-ok` override).
5. **`risk/` mode package unwired** — challenge/funded/live switching does not actually run. P: n/a (inert) · I: expectation gap → fix: wire `--risk-mode` into RISK_SCALE + gates in a small reviewed PR (do NOT rush this into the live path).
6. **BTCTREND/XSMOM without broker stops** — P: low (BTCTREND rebalance-managed; XSMOM Alpaca paper) · I: medium → fix: attach protective SL at rebalance, or keep off funded accounts (documented in LIVE_SAFETY_AUDIT).
7. **Edge unconfirmed live** — P: — · I: decisive for funding → fix: nothing to code; accumulate the clean month, compare live vs backtest.
8. **Single VPS = single point of failure** — P: low-medium (RDP logoff kills MT5, host reboot) · I: medium (brackets protect open positions; new entries stop) → fix: MT5 auto-start task + status.py heartbeat check; consider a second host later.
9. **Secrets previously pasted in chat (MT5/Telegram/etc.)** — P: low · I: medium → fix: rotate before real money (user decision).
10. **paper-trade.yml workflow can't be pushed by token** (no `workflow` scope) — P: certain · I: low → fix: add via GitHub web UI if wanted.

## Production readiness score

**Demo/paper trading (current mission): 88/100** — start-to-finish verified: startup,
brackets on both venues, crash alerting, watchdog, auto-deploy. Deductions: unwired
risk modes (-4), BTCTREND/XSMOM stop gap (-3), single-VPS SPOF (-3), residual
unknowns of a young system (-2).

**Funded/live money: 55/100** — execution layer is ready, but: the edge is
statistically unconfirmed live (the dominant gap), risk modes unwired, secrets need
rotation, and one clean month of demo statistics does not yet exist. Do not fund yet.

## Top 10 remaining blockers (ranked)

1. **No clean month of live statistics yet** — the paper-trail restarted after the naked-order fix; everything else is secondary to this clock.
2. **Live edge vs backtest comparison not yet possible** (needs ~20-30 live signals).
3. **`risk/` challenge/funded/live modes not wired** into live_trader (currently decorative).
4. **BTCTREND/XSMOM lack broker-side stops** (keep off funded accounts until fixed).
5. **First Alpaca bracket fill unverified** (code compiles; confirm S/L+T/P appear on the next paper fill or via a small test order).
6. **Single-VPS SPOF** (no MT5 auto-restart / host redundancy).
7. **Secrets rotation before any real-money account** (tokens/passwords exposed in chat history).
8. **Consecutive-loss / max-trades-per-day guards not enforced** (defined in risk profiles, not in the loop; needs MT5 history polling to count broker-side exits).
9. **Alpaca DAY-order nuance**: bracket legs expire at day end — S3's 5-day hold keeps only the position, not the stop, after day 1 on Alpaca (MT5 unaffected). Needs GTC review in the risk-mode PR.
10. **paper-trade.yml** must be added via web UI if that workflow is wanted (token scope).

## Bottom line
The **machine** is production-ready for its current job (demo/paper accumulation) —
every venue starts, protects, logs, alerts, and self-updates. The **business** is not
fundable yet, and the blocker is not code: it is a month of clean statistics.
