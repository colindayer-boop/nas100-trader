"""
build_obsidian.py -- the Obsidian Bridge.

Turns repository data (git history, AI changelog, trader logs, governance docs)
into graph-friendly vault notes under vault/auto/. READ-ONLY on the repo: it
never touches trading code, strategies, brokers, or hand-written notes.

Safety model (idempotent, no-clobber):
- Generated notes live under vault/auto/ only.
- Every generated region sits between <!-- AUTO:BEGIN --> ... <!-- AUTO:END -->
  markers. If a file exists, ONLY the marked region is replaced; anything a human
  wrote outside the markers is preserved byte-for-byte.
- Existing hand-written vault notes (00 Dashboard, 03-Validated-Strategies, ...)
  are never written -- the bridge links TO them (backlinks) instead of duplicating.

Usage:
    python scripts/obsidian/build_obsidian.py            # build/refresh everything
    python scripts/obsidian/build_obsidian.py --dry-run  # print what would change

See scripts/obsidian/README.md for scheduling.
"""
import os
import re
import sys
import subprocess
from datetime import datetime, date

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VAULT = os.path.join(REPO, "vault")
AUTO = os.path.join(VAULT, "auto")
DRY = "--dry-run" in sys.argv

BEGIN = "<!-- AUTO:BEGIN (do not edit inside this block) -->"
END = "<!-- AUTO:END -->"

TODAY = date.today().isoformat()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- plumbing --
def sh(cmd):
    try:
        return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception as e:
        return f"(command failed: {e})"


def write_managed(rel_path, body, header=None):
    """Create or update a note, replacing ONLY the managed block."""
    path = os.path.join(AUTO, rel_path)
    block = f"{BEGIN}\n_generated {NOW} by the Obsidian Bridge_\n\n{body.strip()}\n{END}"
    if os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        if BEGIN in old and END in old:
            pre, rest = old.split(BEGIN, 1)
            _, post = rest.split(END, 1)
            new = pre + block + post
        else:
            # existing file without markers: append the block, never overwrite
            new = old.rstrip() + "\n\n" + block + "\n"
    else:
        head = header if header is not None else f"# {os.path.splitext(os.path.basename(rel_path))[0]}\n"
        new = head + "\n" + block + "\n"
    if DRY:
        changed = (not os.path.exists(path)) or open(path, encoding="utf-8").read() != new
        print(f"[dry-run] {'WRITE' if changed else 'unchanged'}  vault/auto/{rel_path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(new)
    print(f"wrote vault/auto/{rel_path}")


def read_log_lines():
    lines = []
    logdir = os.path.join(REPO, "logs")
    if not os.path.isdir(logdir):
        return lines
    for name in sorted(os.listdir(logdir)):
        if name.endswith(".log"):
            try:
                with open(os.path.join(logdir, name), encoding="utf-8",
                          errors="replace") as f:
                    lines += [(name, ln.rstrip()) for ln in f]
            except Exception:
                pass
    return lines


LOGS = read_log_lines()


def grep_logs(pattern, today_only=False):
    rx = re.compile(pattern)
    out = []
    for name, ln in LOGS:
        if rx.search(ln) and (not today_only or TODAY in ln):
            out.append((name, ln))
    return out


# ---------------------------------------------------------------- sections --
def daily_note():
    sessions = grep_logs(r"START session=", today_only=True)
    signals = grep_logs(r"SIGNAL", today_only=True)
    errors = grep_logs(r"CRASH|Traceback|ORDER_FAIL|NAKED ORDER", today_only=True)
    fills = grep_logs(r"FILL |WOULD BUY|WOULD SELL", today_only=True)
    body = [f"## {TODAY} summary", ""]
    body.append(f"- sessions run (visible in local logs): **{len(sessions)}**")
    body.append(f"- signals: **{len(signals)}** | fills/dry-fills: **{len(fills)}** | errors: **{len(errors)}**")
    if signals:
        body.append("\n### Signals")
        body += [f"- `{ln[:140]}`" for _, ln in signals[:20]]
    if errors:
        body.append("\n### Errors (triage!)")
        body += [f"- `{ln[:140]}`" for _, ln in errors[:20]]
    body.append("\n### Links")
    body.append("[[AI Session Log]] | [[Monitoring Report]] | [[Trade Journal]] | "
                "[[Git Commits]] | [[00 Dashboard]]")
    header = (f"# Daily {TODAY}\n\n_Anything you type outside the AUTO block is preserved._\n")
    write_managed(f"Daily/{TODAY}.md", "\n".join(body), header=header)


def ai_session_log():
    src = os.path.join(REPO, "docs", "AI_CHANGELOG.md")
    rows = ""
    if os.path.exists(src):
        rows = open(src, encoding="utf-8").read()
        # keep just the table
        m = re.search(r"\| Date \|.*", rows, re.S)
        rows = m.group(0) if m else rows
    body = ("Mirrors `docs/AI_CHANGELOG.md` (the source of truth -- edit THERE).\n\n"
            + rows + "\n\nBack: [[AI Index]] | [[00 Dashboard]]")
    write_managed("AI/AI Session Log.md", body)


def git_commits():
    log = sh(["git", "log", "--oneline", "--date=short",
              "--pretty=format:%h | %ad | %s", "-30"])
    body = ("Last 30 commits on `main`.\n\n| hash | date | subject |\n|---|---|---|\n"
            + "\n".join(f"| `{l.split(' | ')[0]}` | {l.split(' | ')[1]} | {' | '.join(l.split(' | ')[2:])} |"
                        for l in log.splitlines() if " | " in l)
            + "\n\nBack: [[Production Index]] | [[00 Dashboard]]")
    write_managed("Production/Git Commits.md", body)


def bugs_fixed():
    # single source: the parity doc's fixed-bug tables + incident notes
    body = ("Canonical record of confirmed bugs and their fixes.\n\n"
            "- Full tables: [[LIVE_TRADING_PARITY]] (repo docs/) -- unit bug, filter\n"
            "  starvation, GTC brackets, naked orders, timezone, emoji crash, startup.\n"
            "- Post-mortems: [[08-Incidents-and-Postmortems/_index|Incidents index]]\n"
            "- Verification trail: [[AI Session Log]]\n\n"
            "| Bug | Fixed in | Post-mortem |\n|---|---|---|\n"
            "| get_bars DAYS vs BARS unit mismatch | 236abe3 | LIVE_TRADING_PARITY |\n"
            "| 30-bar filter starvation (EMA50/HighVol) | 236abe3 | LIVE_TRADING_PARITY |\n"
            "| Alpaca DAY brackets expired at close | 236abe3 | LIVE_TRADING_PARITY |\n"
            "| Startup SyntaxError + args-before-parse | fd0ff25 | STARTUP_FIX_REPORT |\n"
            "| Naked MT5 orders (no SL/TP) | see git ~0ce6e24 era | [[08-Incidents-and-Postmortems/2026-07-07 Naked Orders|note]] |\n"
            "| Emoji crash (6-day silent outage) | ae148e3 era | [[08-Incidents-and-Postmortems/2026-07-06 Emoji Crash|note]] |\n"
            "| MT5 server-time bars ~3h shift | Fable PR | [[08-Incidents-and-Postmortems/Timezone Bug|note]] |\n"
            "\nBack: [[Production Index]] | [[00 Dashboard]]")
    write_managed("Production/Bugs Fixed.md", body)


def monitoring_report():
    sig = grep_logs(r"SIGNAL")
    err = grep_logs(r"CRASH|Traceback|ORDER_FAIL")
    naked = grep_logs(r"NAKED ORDER")
    dry = grep_logs(r"dry_run=True")
    live = grep_logs(r"dry_run=False")
    body = ["Rolling snapshot from local `logs/` (VPS logs live on the VPS -- run "
            "`status.py` there; this mirrors what is visible here).", ""]
    body.append("| metric | count (all local logs) |\n|---|---|")
    body.append(f"| signals logged | {len(sig)} |")
    body.append(f"| live session starts | {len(live)} |")
    body.append(f"| dry-run session starts | {len(dry)} |")
    body.append(f"| errors (CRASH/FAIL/Traceback) | {len(err)} |")
    body.append(f"| naked-order warnings | {len(naked)} |")
    body.append("\nGoverning plan: [[NEXT_30_DAY_MONITORING_PLAN]] (repo docs/).")
    body.append("\nBack: [[Monitoring Index]] | [[00 Dashboard]]")
    write_managed("Monitoring/Monitoring Report.md", "\n".join(body))


def trade_journal():
    fills = grep_logs(r"FILL |EXIT stop|EXIT target|WOULD BUY|WOULD SELL")
    body = ["Every fill / exit / dry-fill found in local logs (newest last, "
            "max 100 shown). VPS fills appear in Telegram + MT5 history.", ""]
    for name, ln in fills[-100:]:
        body.append(f"- `{name}` :: `{ln[:150]}`")
    if not fills:
        body.append("_No fills recorded in local logs yet._")
    body.append("\nBack: [[Trading Index]] | [[00 Dashboard]]")
    write_managed("Trading/Trade Journal.md", "\n".join(body))


def research_notes():
    hunt = os.path.join(REPO, "HUNT_LOG.md")
    sweep = os.path.join(REPO, "SWEEP_SUMMARY.md")
    body = ["Research state (generated pointers -- the graveyard is authoritative).", ""]
    for label, p in [("HUNT_LOG.md", hunt), ("SWEEP_SUMMARY.md", sweep),
                     ("FINDINGS.md", os.path.join(REPO, "FINDINGS.md"))]:
        if os.path.exists(p):
            n = sum(1 for _ in open(p, encoding="utf-8", errors="replace"))
            body.append(f"- **{label}**: {n} lines (repo root)")
    body.append("- Hand-written: [[02-Strategy-Research/Gauntlet|The Gauntlet]], "
                "[[02-Strategy-Research/Rejected Ideas|Rejected Ideas]]")
    body.append("- Pipeline rules: AI_OPERATING_SYSTEM.md section 6 (repo docs/)")
    body.append("\nBack: [[Research Index]] | [[00 Dashboard]]")
    write_managed("Research/Research Notes.md", "\n".join(body))


def dashboard_snapshot():
    state = os.path.join(REPO, "docs", "CURRENT_PROJECT_STATE.md")
    status_line = "(state doc missing)"
    if os.path.exists(state):
        txt = open(state, encoding="utf-8").read()
        m = re.search(r"## Current production status\n(.*?)\n##", txt, re.S)
        status_line = m.group(1).strip()[:600] if m else "(section not found)"
    head = sh(["git", "log", "-1", "--pretty=format:%h %s"])
    body = (f"**HEAD:** `{head}`\n\n**Production status (from CURRENT_PROJECT_STATE):**\n\n"
            f"{status_line}\n\n"
            "_Images/screenshots: store under vault/attachments/ and reference by\n"
            "path (link only) -- the bridge never embeds binaries._\n\n"
            "Back: [[Production Index]] | [[00 Dashboard]]")
    write_managed("Production/Dashboard Snapshot.md", body)


def indexes():
    idx = {
        "AI/AI Index.md":
            "- [[AI Session Log]]\n- Operating system: docs/AI_OPERATING_SYSTEM.md\n"
            "- Changelog source: docs/AI_CHANGELOG.md",
        "Trading/Trading Index.md":
            "- [[Trade Journal]]\n- Book: [[03-Validated-Strategies/_index|Validated Strategies]]\n"
            "- Risk: [[04-Risk-Engine]]",
        "Strategies/Strategies Index.md":
            "- Hand-written pages: [[03-Validated-Strategies/_index|Validated Strategies index]]\n"
            "- S1 [[03-Validated-Strategies/S1 Asian Sweep|Asian Sweep]] | "
            "S5 [[03-Validated-Strategies/S5 ORB|ORB]] | "
            "[[03-Validated-Strategies/BTC Sweep|BTC]] | "
            "[[03-Validated-Strategies/Overnight Drift|OVN]]\n"
            "- (The bridge does NOT duplicate strategy pages -- it links.)",
        "Research/Research Index.md":
            "- [[Research Notes]]\n- [[02-Strategy-Research/_index|Strategy Research (hand-written)]]",
        "Production/Production Index.md":
            "- [[Git Commits]]\n- [[Bugs Fixed]]\n- [[Dashboard Snapshot]]\n"
            "- Deployment: [[07-Deployment]]",
        "Incidents/Incidents Index.md":
            "- Hand-written post-mortems: [[08-Incidents-and-Postmortems/_index|Incidents (vault)]]\n"
            "- [[Bugs Fixed]]",
        "Monitoring/Monitoring Index.md":
            "- [[Monitoring Report]]\n- Plan: docs/NEXT_30_DAY_MONITORING_PLAN.md\n"
            "- Daily notes: [[Daily/" + TODAY + "|today]]",
    }
    for rel, body in idx.items():
        write_managed(rel, body + "\n\nBack: [[00 Dashboard]]")
    # master index for the auto tree
    write_managed("Auto Index.md",
                  "\n".join(f"- [[{os.path.splitext(os.path.basename(k))[0]}]]" for k in idx)
                  + "\n- [[Daily/" + TODAY + "|Today's daily note]]"
                  + "\n\nBack: [[00 Dashboard]]",
                  header="# Auto Index\n\n_Everything below vault/auto/ is generated by "
                         "scripts/obsidian/build_obsidian.py. Hand-written notes are never touched._\n")


def main():
    for fn in (daily_note, ai_session_log, git_commits, bugs_fixed,
               monitoring_report, trade_journal, research_notes,
               dashboard_snapshot, indexes):
        fn()
    print("done" + (" (dry-run)" if DRY else ""))


if __name__ == "__main__":
    main()
