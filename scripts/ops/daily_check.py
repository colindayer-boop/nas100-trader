"""
daily_check.py -- Nightly Ops Runner v1 (report-only).

Reads logs/, risk_state_*.json, CURRENT_PROJECT_STATE.md and AI_CHANGELOG.md and
writes docs/DAILY_OPS_REPORT.md with a HEALTHY / ACTION REQUIRED verdict.

STRICTLY read-only on everything except the report file. It never fixes code and
never touches live_trader.py / brokers / strategies / risk logic (per the AI
Operating System: nightly jobs REPORT; a red report is what authorizes a Lead
Engineer fix session).

Usage:
    python scripts/ops/daily_check.py            # write docs/DAILY_OPS_REPORT.md
    python scripts/ops/daily_check.py --print    # also echo the report to stdout

Scheduling (per AI_OPERATING_SYSTEM.md section 5): run nightly ~21:30 UTC on the
host that owns the logs. On the VPS, pair with `python status.py` for scheduler
task results (schtasks data is Windows-only and not visible from the Mac).
"""
import glob
import json
import os
import re
import sys
from datetime import date, datetime

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOGDIR = os.path.join(REPO, "logs")
REPORT = os.path.join(REPO, "docs", "DAILY_OPS_REPORT.md")
TODAY = date.today().isoformat()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

ERROR_RX = re.compile(r"CRASH|Traceback|ORDER_FAIL|MT5 ORDER FAIL|BROKER INIT FAIL")
NAKED_RX = re.compile(r"NAKED ORDER")
SKIP_RX = re.compile(
    r"GEX POSITIVE|PAUSED|no signal|No signal|not in 08-16 UTC|not formed yet|"
    r"already in position|SESSION COOLDOWN|WEEKEND|short disarmed|vol_ok=False")
FILL_RX = re.compile(r"FILL |EXIT stop|EXIT target|WOULD BUY|WOULD SELL")


def read_logs():
    lines = []
    for p in sorted(glob.glob(os.path.join(LOGDIR, "*.log"))):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines += [(os.path.basename(p), ln.rstrip()) for ln in f]
        except Exception:
            pass
    return lines


def today_lines(lines):
    return [(n, l) for n, l in lines if TODAY in l]


def risk_states():
    out = {}
    for p in sorted(glob.glob(os.path.join(LOGDIR, "risk_state_*.json"))):
        name = os.path.basename(p).replace("risk_state_", "").replace(".json", "")
        try:
            out[name] = json.load(open(p))
        except Exception as e:
            out[name] = {"_error": str(e)}
    return out


def last_changelog_row():
    p = os.path.join(REPO, "docs", "AI_CHANGELOG.md")
    if not os.path.exists(p):
        return "(no changelog)"
    rows = [l for l in open(p, encoding="utf-8") if l.startswith("|") and "Date" not in l and "---" not in l]
    return rows[-1].strip() if rows else "(empty)"


def state_status_block():
    p = os.path.join(REPO, "docs", "CURRENT_PROJECT_STATE.md")
    if not os.path.exists(p):
        return "(state doc missing!)"
    m = re.search(r"## Current production status\n(.*?)\n##", open(p, encoding="utf-8").read(), re.S)
    return m.group(1).strip() if m else "(status section not found)"


def main():
    lines = read_logs()
    today = today_lines(lines)

    sessions = [(n, l) for n, l in today if "START session=" in l]
    live_sessions = [x for x in sessions if "dry_run=False" in x[1]]
    dry_sessions = [x for x in sessions if "dry_run=True" in x[1]]
    signals = [(n, l) for n, l in today if "SIGNAL" in l]
    fills = [(n, l) for n, l in today if FILL_RX.search(l)]
    skips = [(n, l) for n, l in today if SKIP_RX.search(l)]
    errors = [(n, l) for n, l in today if ERROR_RX.search(l)]
    naked = [(n, l) for n, l in today if NAKED_RX.search(l)]
    broker_issues = [(n, l) for n, l in today
                     if re.search(r"retcode|get_bars .* failed|Symbol .* not available|"
                                  r"BROKER INIT FAIL|account_info failed", l)]
    rs_lines = [(n, l) for n, l in today if "RISK_SCALE=" in l or "DD-throttle" in l]
    eq_lines = [(n, l) for n, l in today if re.search(r"equity \$|Equity:", l)]
    states = risk_states()

    # ---- verdict -------------------------------------------------------------
    issues = []
    if errors:
        issues.append(f"{len(errors)} error line(s) (CRASH/FAIL/Traceback) in today's logs")
    if naked:
        issues.append(f"{len(naked)} NAKED ORDER warning(s)")
    if broker_issues:
        issues.append(f"{len(broker_issues)} broker anomaly line(s)")
    for name, st in states.items():
        if "_error" in st:
            issues.append(f"risk_state_{name}.json unreadable: {st['_error']}")
    verdict = "ACTION REQUIRED" if issues else "HEALTHY"

    def sample(rows, k=8, width=150):
        return "\n".join(f"- `{n}` :: `{l[:width]}`" for n, l in rows[:k]) or "_none_"

    body = f"""# DAILY OPS REPORT — {TODAY}

_Generated {NOW} by scripts/ops/daily_check.py (report-only; regenerated daily —
do not hand-edit). Visibility = this host's logs/ only; VPS scheduler results
need `python status.py` on the VPS itself._

## VERDICT: **{verdict}**
{("### Issues found" + chr(10) + chr(10) + chr(10).join(f"- {i}" for i in issues)) if issues else "No errors, no naked orders, no broker anomalies in today's local logs."}
{"**Per the AI Operating System: this report authorizes a Lead Engineer fix session. Document-only here — no code was changed.**" if issues else ""}

## Production health
- state doc says:

{state_status_block()}

## Today's sessions ({len(sessions)} visible: {len(live_sessions)} live / {len(dry_sessions)} dry-run)
{sample(sessions)}

## Orders / fills today ({len(fills)})
{sample(fills)}

## Signals today ({len(signals)})
{sample(signals)}

## Skipped signals / gate reasons today ({len(skips)})
{sample(skips, k=10)}

## Warnings & errors today ({len(errors)} errors, {len(naked)} naked-order warnings)
{sample(errors + naked)}

## Broker issues today ({len(broker_issues)})
{sample(broker_issues)}

## Risk scale / throttle (today's readings)
{sample(rs_lines, k=4)}

## Equity (today's readings)
{sample(eq_lines, k=4)}

## Risk state files
{chr(10).join(f"- **{k}**: `{json.dumps(v)}`" for k, v in states.items()) or "_none found_"}

## Last AI changelog entry
{last_changelog_row()}

## Action required?
**{verdict}.** {"Triage the issues above (Lead Engineer session)." if issues else "Nothing to do — continue the 30-day monitoring window (NEXT_30_DAY_MONITORING_PLAN.md)."}
"""
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w", encoding="utf-8").write(body)
    print(f"wrote docs/DAILY_OPS_REPORT.md  VERDICT: {verdict}")
    if "--print" in sys.argv:
        print(body)
    # exit code signals the verdict for schedulers/hooks (0 healthy, 2 action)
    sys.exit(0 if verdict == "HEALTHY" else 2)


if __name__ == "__main__":
    main()
