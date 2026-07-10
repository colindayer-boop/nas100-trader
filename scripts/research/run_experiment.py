#!/usr/bin/env python3
"""
run_experiment.py — the Experiment Runner.

Loads a queued/running experiment note, verifies required datasets, launches the
correct backtest script, captures all output, computes summary metrics, updates
the experiment note, and generates Obsidian links. Never touches production code.

Usage:
    python scripts/research/run_experiment.py EXP-20260710-01
    python scripts/research/run_experiment.py EXP-20260710-01 --script my_test.py
    python scripts/research/run_experiment.py EXP-20260710-01 --dry-run
    python scripts/research/run_experiment.py EXP-20260710-01 --resume

Design principles (from AI_OPERATING_SYSTEM.md):
  - Research NEVER edits live_trader.py / brokers / validated constants.
  - Every run leaves a trail: results file + updated experiment note.
  - Never overwrites human notes (only fills AUTO-marker sections).
  - Gracefully recovers from interruption (resume from results file).
"""

import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(REPO, "research", "results")
EXPERIMENTS_DIR = os.path.join(REPO, "research", "experiments")
QUEUE_DIR = os.path.join(REPO, "research", "queue")
ARCHIVE_DIR = os.path.join(REPO, "research", "archive")
VAULT_RESEARCH_DIR = os.path.join(REPO, "vault", "02-Strategy-Research")

# Datasets that live in the repo root (data files)
DATA_ROOT = REPO

# AUTO markers for managed sections in experiment notes
BACKTEST_TABLE_MARKER = "<!-- AUTO:BACKTESTS -->"
METRICS_MARKER = "<!-- AUTO:METRICS -->"
RUN_LOG_MARKER = "<!-- AUTO:RUNLOG -->"
RESULT_LINKS_MARKER = "<!-- AUTO:RESULTLINKS -->"


# ── Experiment note loading ──────────────────────────────────────────────

def find_experiment(eid):
    """Find an experiment note by ID across queue/experiments/archive."""
    for d in (QUEUE_DIR, EXPERIMENTS_DIR, ARCHIVE_DIR):
        hits = glob.glob(os.path.join(d, f"{eid}-*.md"))
        if hits:
            return hits[0]
    return None


def parse_frontmatter(text):
    """Parse YAML frontmatter into a dict."""
    fm = {}
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return fm
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            # Strip inline comments
            if "#" in val and not val.startswith('"'):
                val = val.split("#")[0].strip()
            # Strip quotes
            val = val.strip('"').strip("'")
            fm[key] = val
    return fm


def read_experiment(path):
    """Read experiment note, return (text, frontmatter_dict)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return text, parse_frontmatter(text)


# ── Dataset verification ────────────────────────────────────────────────

def verify_datasets(datasets_str):
    """
    Check that declared datasets exist.
    Returns (missing, found) lists.
    """
    if not datasets_str:
        return [], []

    names = [d.strip() for d in datasets_str.split(",") if d.strip()]
    missing = []
    found = []

    for name in names:
        # Skip generic/external dataset names that aren't local files
        if name.lower().startswith("squeeze") or "DIX" in name.upper():
            # External dataset — warn but don't block
            found.append((name, "external (manual check needed)"))
            continue

        # Try exact path, then repo root, then data/
        candidates = [
            os.path.join(DATA_ROOT, name),
            os.path.join(DATA_ROOT, "data", name),
        ]
        # Also try without extension match in root
        if not any(os.path.exists(c) for c in candidates):
            # Try glob pattern (e.g., "qqq_*_7y.csv")
            globs = glob.glob(os.path.join(DATA_ROOT, name))
            globs += glob.glob(os.path.join(DATA_ROOT, "data", name))
            if globs:
                found.append((name, globs[0]))
                continue
            missing.append(name)
        else:
            for c in candidates:
                if os.path.exists(c):
                    found.append((name, c))
                    break

    return missing, found


# ── Script resolution ───────────────────────────────────────────────────

def resolve_script(fm, explicit_script=None):
    """
    Determine which script to run.
    Priority: --script flag > frontmatter 'script' field > None.
    """
    if explicit_script:
        # If it's a bare name, try research/experiments/ first
        if not os.path.isabs(explicit_script) and "/" not in explicit_script:
            candidate = os.path.join(EXPERIMENTS_DIR, explicit_script)
            if os.path.exists(candidate):
                return candidate
            # Try repo root
            candidate = os.path.join(REPO, explicit_script)
            if os.path.exists(candidate):
                return candidate
        if os.path.exists(explicit_script):
            return os.path.abspath(explicit_script)
        return None

    script_field = fm.get("script", "").strip().strip('"').strip("'")
    if script_field:
        candidate = os.path.join(EXPERIMENTS_DIR, script_field)
        if os.path.exists(candidate):
            return candidate
        candidate = os.path.join(REPO, script_field)
        if os.path.exists(candidate):
            return candidate

    return None


# ── Execution ───────────────────────────────────────────────────────────

def run_backtest(script_path, timeout=3600, extra_args=None):
    """
    Execute the backtest script, capture stdout+stderr.
    Returns dict with: returncode, stdout, stderr, duration_s, timed_out.
    """
    cmd = [sys.executable, script_path]
    if extra_args:
        cmd += extra_args

    start = time.time()
    result = {
        "command": " ".join(cmd),
        "script": script_path,
        "started_at": datetime.datetime.now().isoformat(),
        "timed_out": False,
    }

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
    except subprocess.TimeoutExpired as e:
        result["returncode"] = -1
        result["stdout"] = e.stdout or "" if isinstance(e.stdout, str) else ""
        result["stderr"] = (e.stderr or "" if isinstance(e.stderr, str) else "") + f"\nTIMEOUT after {timeout}s"
        result["timed_out"] = True
    except Exception as e:
        result["returncode"] = -1
        result["stdout"] = ""
        result["stderr"] = f"LAUNCH ERROR: {e}\n{traceback.format_exc()}"

    result["duration_s"] = round(time.time() - start, 2)
    result["finished_at"] = datetime.datetime.now().isoformat()
    return result


# ── Metrics extraction ──────────────────────────────────────────────────

def extract_metrics(stdout, stderr):
    """
    Parse stdout for summary metrics.
    Looks for common patterns: Sharpe, CAGR, DD, trades, win rate, etc.
    Returns dict of found metrics.
    """
    metrics = {}
    combined = stdout + "\n" + stderr

    # Pattern library — extend as scripts produce different formats
    patterns = {
        "sharpe": [
            r"[Ss]harpe[\s:]*(?:ratio)?[\s:]*([\-0-9.]+)",
            r"Sharpe.*?=?\s*([\-0-9.]+)",
        ],
        "cagr": [
            r"CAGR[\s:]*([\-0-9.%]+)",
            r"[Aa]nnualized\s+return[\s:]*([\-0-9.%]+)",
        ],
        "max_dd": [
            r"[Mm]ax.*?DD[\s:]*([\-0-9.%]+)",
            r"[Mm]aximum\s+[Dd]rawdown[\s:]*([\-0-9.%]+)",
            r"MaxDD[\s:]*([\-0-9.%]+)",
        ],
        "total_trades": [
            r"[Tt]otal\s+trades[\s:]*([0-9]+)",
            r"Trades[\s:]*([0-9]+)",
            r"#trades[\s:]*([0-9]+)",
        ],
        "win_rate": [
            r"[Ww]in\s+rate[\s:]*([0-9.%]+)",
            r"Hit\s+rate[\s:]*([0-9.%]+)",
        ],
        "oos_sharpe": [
            r"OOS\s+[Ss]harpe[\s:]*([\-0-9.]+)",
            r"Out[\s-]*of[\s-]*[Ss]ample\s+[Ss]harpe[\s:]*([\-0-9.]+)",
        ],
        "is_sharpe": [
            r"\bIS\s+[Ss]harpe[\s:]*([\-0-9.]+)",
            r"In[\s-]*[Ss]ample\s+[Ss]harpe[\s:]*([\-0-9.]+)",
        ],
        "net_pnl": [
            r"[Nn]et\s+(?:P&?L|pnl|return)[\s:]*\$?([\-0-9.%]+)",
            r"[Tt]otal\s+(?:P&?L|pnl|return)[\s:]*\$?([\-0-9.%]+)",
        ],
        "avg_r": [
            r"[Aa]vg\s*[\rR][\s:]*([\-0-9.]+)",
            r"[Aa]verage\s*[\rR][\s:]*([\-0-9.]+)",
        ],
    }

    for key, plist in patterns.items():
        for pat in plist:
            m = re.search(pat, combined)
            if m:
                metrics[key] = m.group(1)
                break

    return metrics


# ── Results persistence ─────────────────────────────────────────────────

def results_path(eid):
    """Get the results file path for an experiment."""
    return os.path.join(RESULTS_DIR, f"{eid}_results.json")


def load_previous_results(eid):
    """Load previous results for resume support. Returns list of runs."""
    path = results_path(eid)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("runs", [])
    except (json.JSONDecodeError, IOError):
        return []


def save_results(eid, runs, fm):
    """Save results JSON (all runs, including previous)."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = results_path(eid)
    data = {
        "experiment_id": eid,
        "title": fm.get("title", ""),
        "updated_at": datetime.datetime.now().isoformat(),
        "runs": runs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


# ── Experiment note update ──────────────────────────────────────────────

def update_backtest_row(existing_table, run_data, metrics, eid):
    """Build a new row for the backtests table."""
    today = datetime.date.today().isoformat()
    script_name = os.path.basename(run_data.get("script", "?"))
    split = "full"  # default; could be parsed from script args
    is_sharpe = metrics.get("is_sharpe", "-")
    oos_sharpe = metrics.get("oos_sharpe", metrics.get("sharpe", "-"))
    oos_dd = metrics.get("max_dd", "-")
    trades = metrics.get("total_trades", "-")
    corr = metrics.get("corr", "-")
    verdict = "PASS" if run_data.get("returncode") == 0 else "FAIL"

    return f"| {today} | {script_name} | {split} | {is_sharpe} | {oos_sharpe} | {oos_dd} | {trades} | {corr} | {verdict} |"


def ensure_managed_section(text, marker, section_title, default_content):
    """Ensure a managed section exists. Insert before '## Verdict' if not present."""
    if marker in text:
        return text
    insertion = f"\n{section_title}\n\n{marker}\n{default_content}\n<!-- /AUTO -->\n"
    # Insert before ## Verdict
    verdict_match = re.search(r"^## Verdict", text, re.M)
    if verdict_match:
        pos = verdict_match.start()
        return text[:pos] + insertion + "\n" + text[pos:]
    return text + "\n" + insertion


def update_experiment_note(path, text, eid, run_data, metrics, results_file):
    """
    Update AUTO-managed sections of the experiment note.
    Never overwrites content outside AUTO markers.
    """
    # Ensure sections exist
    text = ensure_managed_section(
        text, BACKTEST_TABLE_MARKER, "## Backtest Results (Auto)",
        "| date | script | split | IS Sharpe | OOS Sharpe | OOS DD | trades | corr | verdict |\n|---|---|---|---|---|---|---|---|---|"
    )
    text = ensure_managed_section(
        text, METRICS_MARKER, "## Summary Metrics (Auto)",
        "_Metrics extracted from last run output._"
    )
    text = ensure_managed_section(
        text, RUN_LOG_MARKER, "## Run Log (Auto)",
        ""
    )
    text = ensure_managed_section(
        text, RESULT_LINKS_MARKER, "## Results Files (Auto)",
        ""
    )

    # Update backtest table — append row
    new_row = update_backtest_row(None, run_data, metrics, eid)
    text = append_in_section(text, BACKTEST_TABLE_MARKER, new_row)

    # Update metrics
    metrics_lines = [f"- **{k}**: {v}" for k, v in sorted(metrics.items())]
    if not metrics_lines:
        metrics_lines = ["_No metrics extracted from output._"]
    metrics_block = "\n".join(metrics_lines)
    text = replace_in_section(text, METRICS_MARKER, metrics_block)

    # Update run log
    run_line = f"- {run_data.get('finished_at', '?')} | rc={run_data.get('returncode', '?')} | {run_data.get('duration_s', '?')}s | {run_data.get('command', '?')}"
    text = append_in_section(text, RUN_LOG_MARKER, run_line)

    # Update results links
    rel_results = os.path.relpath(results_file, REPO)
    results_line = f"- [{rel_results}]({rel_results})"
    text = append_in_section(text, RESULT_LINKS_MARKER, results_line)

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def append_in_section(text, marker, line):
    """Append a line right after the marker's content (before the /AUTO close)."""
    pattern = f"({marker}.*?)(\n<!-- /AUTO -->)"
    def replacer(m):
        return m.group(1) + "\n" + line + m.group(2)
    new_text = re.sub(pattern, replacer, text, count=1, flags=re.DOTALL)
    if new_text == text:
        # Fallback: just append after marker line
        new_text = text.replace(marker, marker + "\n" + line, 1)
    return new_text


def replace_in_section(text, marker, content):
    """Replace all content between marker and /AUTO."""
    pattern = f"({marker})(.*?)(<!-- /AUTO -->)"
    replacement = f"\\1\n{content}\n\\3"
    new_text = re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
    if new_text == text:
        new_text = text.replace(marker, marker + "\n" + content + "\n<!-- /AUTO -->", 1)
    return new_text


# ── Obsidian link generation ────────────────────────────────────────────

def generate_obsidian_link(eid, title, results_file, vault_dir=None):
    """
    Generate/update a note in vault/02-Strategy-Research/ linking to the
    experiment results. Never overwrites existing human content.
    """
    if vault_dir is None:
        vault_dir = VAULT_RESEARCH_DIR

    os.makedirs(vault_dir, exist_ok=True)
    note_path = os.path.join(vault_dir, f"{eid} Results.md")

    rel_results = os.path.relpath(results_file, REPO)

    content = f"""---
type: experiment-results
experiment: {eid}
title: "{title} Results"
date: {datetime.date.today().isoformat()}
tags: [research, experiment, results]
---
# {eid} Results

**Experiment:** {title}
**Results file:** `{rel_results}`

_Experiment note:_ [[research/queue/{eid}]]

## Auto-generated links
- Results JSON: `{rel_results}`
- See: [[02-Strategy-Research/Gauntlet|The Gauntlet]]

_Back: [[02-Strategy-Research/_index|Strategy Research]]_
"""

    if os.path.exists(note_path):
        # Don't overwrite — just print
        return note_path, False

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(content)
    return note_path, True


# ── Graceful interruption ───────────────────────────────────────────────

_interrupted = False

def _signal_handler(signum, frame):
    global _interrupted
    _interrupted = True
    print("\n[run_experiment] INTERRUPTED — saving partial results...")

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Experiment Runner — load, execute, and record a research experiment."
    )
    parser.add_argument(
        "experiment_id",
        help="Experiment ID, e.g. EXP-20260710-01",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Override the script to run (relative to repo root or experiments/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify datasets and resolve script but do not execute.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous results (load run history, append new run).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Script timeout in seconds (default: 3600)",
    )
    parser.add_argument(
        "--args",
        default=None,
        help="Extra arguments to pass to the script (quoted string)",
    )
    args = parser.parse_args()

    eid = args.experiment_id

    # 1. Find experiment note
    note_path = find_experiment(eid)
    if not note_path:
        print(f"ERROR: experiment {eid} not found in queue/experiments/archive.")
        sys.exit(1)
    print(f"[load] experiment note: {os.path.relpath(note_path, REPO)}")

    text, fm = read_experiment(note_path)
    title = fm.get("title", eid)
    print(f"[load] title: {title}")
    print(f"[load] status: {fm.get('status', 'unknown')}")

    # 2. Verify datasets
    datasets_str = fm.get("datasets", "")
    missing, found = verify_datasets(datasets_str)
    if found:
        print(f"[data] found {len(found)} dataset(s):")
        for name, path in found:
            print(f"       OK  {name} -> {path}")
    if missing:
        print(f"[data] MISSING {len(missing)} dataset(s):")
        for name in missing:
            print(f"       !!  {name}")
        print("[data] missing datasets — experiment cannot run.")
        print("       Place the file in the repo root or data/ and re-run.")
        if not args.dry_run:
            sys.exit(1)
    if not found and not missing and not datasets_str:
        print("[data] no datasets declared in experiment note.")

    # 3. Resolve script
    script_path = resolve_script(fm, args.script)
    if script_path:
        print(f"[script] resolved: {os.path.relpath(script_path, REPO)}")
    elif args.dry_run:
        print("[script] not found (or not set in frontmatter)")
        print("         Set the 'script:' field in the experiment note,")
        print("         or pass --script <path.py>")
    else:
        print("[script] no script resolved.")
        print("         Set the 'script:' field in the experiment note,")
        print("         or pass --script <path.py>")
        sys.exit(1)

    # 4. Dry run stops here
    if args.dry_run:
        print()
        print("[dry-run] Verification complete:")
        print(f"  experiment: {eid} ({title})")
        print(f"  note:       {os.path.relpath(note_path, REPO)}")
        print(f"  datasets:   {len(found)} found, {len(missing)} missing")
        print(f"  script:     {os.path.relpath(script_path, REPO) if script_path else '(not set)'}")
        print(f"  status:     {fm.get('status', 'unknown')}")
        print("[dry-run] No execution performed.")
        return

    if not script_path:
        sys.exit(1)

    # 5. Load previous runs (resume support)
    previous_runs = load_previous_results(eid) if args.resume else []
    if previous_runs:
        print(f"[resume] loaded {len(previous_runs)} previous run(s) from results file.")

    # Check for interruption before launch
    if _interrupted:
        print("[run_experiment] interrupted before launch. No results.")
        sys.exit(130)

    # 6. Execute
    extra_args = args.args.split() if args.args else None
    print(f"[exec] launching: {script_path}")
    print(f"[exec] timeout: {args.timeout}s")

    run_data = run_backtest(script_path, timeout=args.timeout, extra_args=extra_args)

    rc = run_data.get("returncode", -1)
    print(f"[exec] return code: {rc} ({run_data.get('duration_s', '?')}s)")

    if run_data.get("timed_out"):
        print("[exec] TIMED OUT — partial output captured.")

    # 7. Check interruption after run
    if _interrupted:
        print("[run_experiment] interrupted after run — saving partial results.")

    # 8. Extract metrics
    metrics = extract_metrics(
        run_data.get("stdout", ""),
        run_data.get("stderr", ""),
    )
    if metrics:
        print("[metrics] extracted:")
        for k, v in sorted(metrics.items()):
            print(f"         {k} = {v}")
    else:
        print("[metrics] none extracted (script output format may not match patterns)")

    # 9. Save results JSON
    all_runs = previous_runs + [run_data]
    results_file = save_results(eid, all_runs, fm)
    print(f"[save] results: {os.path.relpath(results_file, REPO)}")

    # 10. Update experiment note (AUTO sections only)
    update_experiment_note(note_path, text, eid, run_data, metrics, results_file)
    print(f"[update] experiment note: {os.path.relpath(note_path, REPO)}")

    # 11. Generate Obsidian links
    vault_note, created = generate_obsidian_link(eid, title, results_file)
    if created:
        print(f"[vault] created: {os.path.relpath(vault_note, REPO)}")
    else:
        print(f"[vault] exists (not overwritten): {os.path.relpath(vault_note, REPO)}")

    # 12. Summary
    print()
    print("=" * 60)
    print(f"EXPERIMENT {eid} — COMPLETE")
    print(f"  script:     {os.path.basename(script_path)}")
    print(f"  returncode: {rc}")
    print(f"  duration:   {run_data.get('duration_s', '?')}s")
    print(f"  metrics:    {len(metrics)} extracted")
    print(f"  results:    {os.path.relpath(results_file, REPO)}")
    print(f"  runs total: {len(all_runs)} (this + previous)")
    print("=" * 60)

    if rc != 0:
        print("\nNOTE: script returned non-zero. Check stderr in results JSON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
