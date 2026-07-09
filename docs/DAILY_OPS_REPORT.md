# DAILY OPS REPORT — 2026-07-10

_Generated 2026-07-10 01:54 by scripts/ops/daily_check.py (report-only; regenerated daily —
do not hand-edit). Visibility = this host's logs/ only; VPS scheduler results
need `python status.py` on the VPS itself._

## VERDICT: **HEALTHY**
No errors, no naked orders, no broker anomalies in today's local logs.


## Production health
- state doc says:

- **Demo/paper readiness: 88/100. Funded/live readiness: 55/100. DO NOT FUND YET.**
- All venues start, protect, alert, self-update. Startup verified (STARTUP_FIX_REPORT).
- **Zero real-money fills have ever occurred.** Early "live" window: 19/21 sessions
  were operator-launched dry-runs; the 2 live sessions had no signals (filters
  correct). The Alpaca −1.5% is pre-existing account history, NOT system losses.
- Parity with the validated backtests was restored on 2026-07-09 (get_bars unit
  bug, 30-bar filter starvation, DAY→GTC brackets). **The clean 30-day statistics
  window starts with the first trading day after commit 236abe3 — it is running now.**
  Governing doc: NEXT_30_DAY_MONITORING_PLAN.md.

## Today's sessions (6 visible: 0 live / 6 dry-run)
- `trader.log` :: `2026-07-10 00:28:47,995 INFO START session=orb broker=alpaca dry_run=True`
- `trader.log` :: `2026-07-10 00:28:51,000 INFO START session=orb broker=alpaca dry_run=True`
- `trader.log` :: `2026-07-10 00:37:35,101 INFO START session=eod broker=alpaca dry_run=True`
- `trader.log` :: `2026-07-10 00:53:09,890 INFO START session=asian broker=alpaca dry_run=True`
- `trader.log` :: `2026-07-10 00:53:38,937 INFO START session=orb broker=alpaca dry_run=True`
- `trader.log` :: `2026-07-10 00:53:42,041 INFO START session=sweep broker=alpaca dry_run=True`

## Orders / fills today (3)
- `trader.log` :: `2026-07-10 00:28:50,141 INFO [DRY-RUN] WOULD BUY 83.0 QQQ (S5)`
- `trader.log` :: `2026-07-10 00:28:52,567 INFO [DRY-RUN] WOULD BUY 83.0 QQQ (S5)`
- `trader.log` :: `2026-07-10 00:53:40,920 INFO [DRY-RUN] WOULD BUY 83.0 QQQ (S5)`

## Signals today (3)
- `trader.log` :: `2026-07-10 00:28:50,141 INFO S5 SIGNAL QQQ ORB long price=723.78 shares=83.0`
- `trader.log` :: `2026-07-10 00:28:52,567 INFO S5 SIGNAL QQQ ORB long price=723.78 shares=83.0`
- `trader.log` :: `2026-07-10 00:53:40,920 INFO S5 SIGNAL QQQ ORB long price=723.78 shares=83.0`

## Skipped signals / gate reasons today (9)
- `trader.log` :: `2026-07-10 00:37:36,683 INFO S3 QQQ: no signal abnvol=-0.71`
- `trader.log` :: `2026-07-10 00:37:36,839 INFO S3 GLD: no signal abnvol=0.20`
- `trader.log` :: `2026-07-10 00:37:37,006 INFO S3 GDX: no signal abnvol=0.40`
- `trader.log` :: `2026-07-10 00:37:37,179 INFO S3 SLV: no signal abnvol=-0.36`
- `trader.log` :: `2026-07-10 00:37:37,328 INFO S3 USO: no signal abnvol=0.09`
- `trader.log` :: `2026-07-10 00:53:15,829 INFO S1 no signal: close=722.54 asian_low=722.25`
- `trader.log` :: `2026-07-10 00:53:17,611 INFO S2 no signal`
- `trader.log` :: `2026-07-10 00:53:20,729 INFO S4 QQQ: no signal`
- `trader.log` :: `2026-07-10 00:53:24,270 INFO S4 SPY: no signal`

## Warnings & errors today (0 errors, 0 naked-order warnings)
_none_

## Broker issues today (0)
_none_

## Risk scale / throttle (today's readings)
- `trader.log` :: `2026-07-10 00:28:49,654 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%`
- `trader.log` :: `2026-07-10 00:28:52,183 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%`
- `trader.log` :: `2026-07-10 00:37:36,501 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%`
- `trader.log` :: `2026-07-10 00:53:11,246 INFO DD-throttle: peak=$100,000 dd=-1.5% throttle=0.81 -> RISK_SCALE=0.81 | month P&L +0.1%`

## Equity (today's readings)
- `trader.log` :: `2026-07-10 00:28:50,141 INFO Session orb complete | equity $98,507.10`
- `trader.log` :: `2026-07-10 00:28:52,567 INFO Session orb complete | equity $98,507.10`
- `trader.log` :: `2026-07-10 00:37:37,328 INFO Session eod complete | equity $98,507.10`
- `trader.log` :: `2026-07-10 00:53:24,271 INFO Session asian complete | equity $98,507.10`

## Risk state files
- **alpaca**: `{"month_key": "2026-07", "month_start_equity": 98432.63, "peak_equity": 100000.0}`
- **binance**: `{"month_key": "2026-07", "month_start_equity": 25000.0, "peak_equity": 25000.0}`

## Last AI changelog entry
| 2026-07-10 | Obsidian Bridge / automated | Daily Ops Report 2026-07-10: no production bug detected, system nominal | git post-commit hook | 970d46b |

## Action required?
**HEALTHY.** Nothing to do — continue the 30-day monitoring window (NEXT_30_DAY_MONITORING_PLAN.md).
