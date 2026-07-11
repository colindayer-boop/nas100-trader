#!/usr/bin/env python3
"""
research_metrics.py — Generate JSON metrics for the research pipeline.

Quantitative snapshot of research activity: counts, rates, velocity,
experiment duration estimates. Output is machine-readable JSON for
dashboards, cron jobs, or OpenClaw monitoring.

Usage:
    python scripts/research/research_metrics.py              # write JSON
    python scripts/research/research_metrics.py --print       # stdout JSON
    python scripts/research/research_metrics.py --pretty      # human-readable
    python scripts/research/research_metrics.py --dry-run     # summary line

Never touches production code. Read-only over the research tree.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPERS_DIR = os.path.join(REPO, "research", "papers")
IDEAS_DIR = os.path.join(REPO, "research", "ideas")
QUEUE_DIR = os.path.join(REPO, "research", "queue")
EXPERIMENTS_DIR = os.path.join(REPO, "research", "experiments")
ARCHIVE_DIR = os.path.join(REPO, "research", "archive")
RESULTS_DIR = os.path.join(REPO, "research", "results")
RESULTS_JSON_DIR = os.path.join(REPO, "research", "results")

METRICS_OUTPUT = os.path.join(RESULTS_DIR, "research_metrics.json")


# ── Frontmatter parser ─────────────────────────────────────────────────

def parse_frontmatter(path):
    """Parse YAML frontmatter from a markdown file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return {}

    fm = {}
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if "#" in val and not val.startswith('"'):
                    val = val.split("#")[0].strip()
                val = val.strip('"').strip("'")
                fm[key] = val
    return fm


def collect_notes(directory):
    """Collect frontmatter from all non-README markdown files."""
    notes = []
    for path in sorted(glob.glob(os.path.join(directory, "*.md"))):
        basename = os.path.basename(path)
        if basename.startswith("README"):
            continue
        fm = parse_frontmatter(path)
        fm["_path"] = path
        fm["_basename"] = os.path.splitext(basename)[0]
        fm["_status"] = fm.get("status", "unknown").split()[0]
        fm["_created"] = fm.get("created", "")
        notes.append(fm)
    return notes


def collect_hunt_stats():
    """Parse HUNT_LOG.md for pass/fail stats."""
    hunt_path = os.path.join(REPO, "HUNT_LOG.md")
    if not os.path.exists(hunt_path):
        return {"total": 0, "pass": 0, "fail": 0, "edges": []}
    try:
        with open(hunt_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return {"total": 0, "pass": 0, "fail": 0, "edges": []}

    total = pass_count = fail_count = 0
    edges = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "verdict" in line.lower() or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]
        if len(cells) >= 11:
            total += 1
            verdict = cells[10] if len(cells) > 10 else ""
            edge_name = cells[1]
            edges.append(edge_name)
            if "PASS" in verdict:
                pass_count += 1
            elif "FAIL" in verdict:
                fail_count += 1

    return {
        "total": total,
        "pass": pass_count,
        "fail": fail_count,
        "edges": edges,
    }


def estimate_experiment_durations():
    """
    Estimate average experiment duration from results JSON files.
    Each results file has a 'runs' array with duration_s fields.
    """
    durations = []
    for path in glob.glob(os.path.join(RESULTS_JSON_DIR, "*_results.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for run in data.get("runs", []):
                dur = run.get("duration_s")
                if dur and isinstance(dur, (int, float)) and dur > 0:
                    durations.append(dur)
        except (json.JSONDecodeError, IOError):
            continue

    if not durations:
        return {
            "count": 0,
            "avg_seconds": 0,
            "min_seconds": 0,
            "max_seconds": 0,
            "avg_minutes": 0,
        }

    return {
        "count": len(durations),
        "avg_seconds": round(sum(durations) / len(durations), 2),
        "min_seconds": round(min(durations), 2),
        "max_seconds": round(max(durations), 2),
        "avg_minutes": round(sum(durations) / len(durations) / 60, 2),
    }


def count_velocity(items, days):
    """Count items created in the last N days."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return sum(1 for item in items if item.get("_created", "") and item.get("_created", "") >= cutoff)


def count_by_status(notes):
    """Group notes by status."""
    counts = {}
    for n in notes:
        status = n.get("_status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


# ── Main ────────────────────────────────────────────────────────────────

def generate_metrics():
    """Generate the full metrics dict."""
    papers = collect_notes(PAPERS_DIR)
    ideas = collect_notes(IDEAS_DIR)
    queued = collect_notes(QUEUE_DIR)
    running = collect_notes(EXPERIMENTS_DIR)
    archived = collect_notes(ARCHIVE_DIR)
    hunt = collect_hunt_stats()
    durations = estimate_experiment_durations()

    validated = [a for a in archived if a.get("_status") == "validated"]
    rejected = [a for a in archived if a.get("_status") == "rejected"]

    # Counts
    all_items = papers + ideas + queued + running + archived

    # Rates
    total_finished = len(validated) + len(rejected)
    validation_rate = (len(validated) / total_finished * 100) if total_finished > 0 else 0
    rejection_rate = (len(rejected) / total_finished * 100) if total_finished > 0 else 0

    # Hunt rates
    hunt_total = hunt["total"]
    hunt_pass_rate = (hunt["pass"] / hunt_total * 100) if hunt_total > 0 else 0
    hunt_fail_rate = (hunt["fail"] / hunt_total * 100) if hunt_total > 0 else 0

    metrics = {
        "generated_at": datetime.datetime.now().isoformat(),
        "generated_date": datetime.date.today().isoformat(),

        "counts": {
            "papers": len(papers),
            "ideas": len(ideas),
            "experiments_queued": len(queued),
            "experiments_running": len(running),
            "experiments_validated": len(validated),
            "experiments_rejected": len(rejected),
            "experiments_total": len(queued) + len(running) + len(archived),
            "hunt_entries": hunt_total,
            "hunt_pass": hunt["pass"],
            "hunt_fail": hunt["fail"],
        },

        "rates": {
            "validation_rate_pct": round(validation_rate, 1),
            "rejection_rate_pct": round(rejection_rate, 1),
            "hunt_pass_rate_pct": round(hunt_pass_rate, 1),
            "hunt_fail_rate_pct": round(hunt_fail_rate, 1),
        },

        "velocity": {
            "items_30d": count_velocity(all_items, 30),
            "items_7d": count_velocity(all_items, 7),
            "papers_30d": count_velocity(papers, 30),
            "ideas_30d": count_velocity(ideas, 30),
            "experiments_30d": count_velocity(queued + running + archived, 30),
        },

        "experiment_durations": durations,

        "statuses": {
            "papers": count_by_status(papers),
            "ideas": count_by_status(ideas),
            "experiments_queued": count_by_status(queued),
            "experiments_running": count_by_status(running),
            "experiments_archived": count_by_status(archived),
        },

        "hunt_edges": hunt["edges"],
    }

    # Historical context
    metrics["context"] = {
        "historical_ideas_in": "~30",
        "historical_survivors": "~2",
        "note": "The pipeline's job is to say no. ~30 ideas in, ~2 survived long-term.",
    }

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON research metrics."
    )
    parser.add_argument("--print", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--pretty", action="store_true", help="Human-readable output")
    parser.add_argument("--dry-run", action="store_true", help="Summary line only")
    args = parser.parse_args()

    metrics = generate_metrics()

    if args.dry_run:
        c = metrics["counts"]
        print(f"[dry-run] papers={c['papers']} ideas={c['ideas']} "
              f"queued={c['experiments_queued']} running={c['experiments_running']} "
              f"validated={c['experiments_validated']} rejected={c['experiments_rejected']} "
              f"hunt={c['hunt_entries']} ({c['hunt_pass']}P/{c['hunt_fail']}F)")
        return

    if args.pretty:
        c = metrics["counts"]
        r = metrics["rates"]
        v = metrics["velocity"]
        d = metrics["experiment_durations"]
        print(f"Research Metrics — {metrics['generated_date']}")
        print(f"")
        print(f"Papers:       {c['papers']}")
        print(f"Ideas:        {c['ideas']}")
        print(f"Experiments:  {c['experiments_total']} (queued={c['experiments_queued']} running={c['experiments_running']} validated={c['experiments_validated']} rejected={c['experiments_rejected']})")
        print(f"Hunt Log:     {c['hunt_entries']} ({c['hunt_pass']} PASS / {c['hunt_fail']} FAIL)")
        print(f"")
        print(f"Validation rate: {r['validation_rate_pct']}%")
        print(f"Rejection rate:  {r['rejection_rate_pct']}%")
        print(f"Hunt pass rate:  {r['hunt_pass_rate_pct']}%")
        print(f"")
        print(f"Velocity (30d): {v['items_30d']} items ({v['papers_30d']} papers, {v['ideas_30d']} ideas, {v['experiments_30d']} experiments)")
        print(f"Velocity (7d):  {v['items_7d']} items")
        print(f"")
        if d["count"] > 0:
            print(f"Avg experiment runtime: {d['avg_minutes']} min ({d['count']} runs measured)")
        else:
            print(f"Avg experiment runtime: (no runs measured yet)")
        return

    json_str = json.dumps(metrics, indent=2, default=str)

    if args.print:
        print(json_str)
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(METRICS_OUTPUT, "w", encoding="utf-8") as f:
        f.write(json_str)
    print(f"[metrics] written: {os.path.relpath(METRICS_OUTPUT, REPO)}")


if __name__ == "__main__":
    main()
