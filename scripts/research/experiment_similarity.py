#!/usr/bin/env python3
"""
experiment_similarity.py -- find similar prior work before testing a new idea.

Reads experiment notes, idea notes, HUNT_LOG entries, FINDINGS topics, and paper
notes from the research/ tree, scores textual similarity against a proposed
title (+ optional description), and warns if the idea overlaps with something
already rejected.

READ-ONLY: never writes, never touches production files, never edits human notes.

Usage:
    python scripts/research/experiment_similarity.py --title "DIX regime filter"
    python scripts/research/experiment_similarity.py --title "pairs trading" --desc "ETF pairs" --threshold 0.2
    python scripts/research/experiment_similarity.py --title "momentum" --json
    python scripts/research/experiment_similarity.py --title "test" --dry-run
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESEARCH = os.path.join(REPO, "research")
HUNT_LOG = os.path.join(REPO, "HUNT_LOG.md")
FINDINGS = os.path.join(REPO, "FINDINGS.md")

EXPERIMENT_DIRS = [
    os.path.join(RESEARCH, "queue"),
    os.path.join(RESEARCH, "experiments"),
    os.path.join(RESEARCH, "archive"),
]
IDEAS_DIR = os.path.join(RESEARCH, "ideas")
PAPERS_DIR = os.path.join(RESEARCH, "papers")

# ---------------------------------------------------------------------------
# Stop words (small inline list keeps the script dependency-free)
# ---------------------------------------------------------------------------
STOP_WORDS = frozenset(
    """
    a an and are as at be by for from has have in is it its of on or that the
    to was were will with would could should about above after again all also
    am any because been before being below between both but can did do does
    doing down during each few further get had having he her here hers him his
    how i if into just me more most my no nor not now of off on once only other
    our ours out over own same she so some such than their theirs them then
    there these they this those through too under until up very we what when
    where which while who whom why you your yours
    """
    .split()
)

# Fields whose tokens we extract from frontmatter for overlap scoring
FM_LIST_FIELDS = [
    "tags",
    "markets",
    "strategy_types",
    "datasets",
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Record:
    """One searchable item from the research tree."""
    item_type: str           # experiment | idea | hunt-entry | findings-topic | paper
    title: str               # display title / edge name / heading
    status: str = ""         # frontmatter status or HUNT_LOG verdict
    path: str = ""           # file path (relative to repo) or "" for synthetic
    keywords: set[str] = field(default_factory=set)   # token set from title + desc
    tags: set[str] = field(default_factory=set)
    markets: set[str] = field(default_factory=set)
    strategy_types: set[str] = field(default_factory=set)
    datasets: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "type": self.item_type,
            "title": self.title,
            "status": self.status,
            "path": self.path,
            "keywords": sorted(self.keywords),
            "tags": sorted(self.tags),
            "markets": sorted(self.markets),
            "strategy_types": sorted(self.strategy_types),
            "datasets": sorted(self.datasets),
        }


@dataclass
class Hit:
    """A similarity result."""
    record: Record
    score: float
    keyword_score: float
    tag_score: float
    market_score: float
    strategy_score: float
    dataset_score: float

    def to_dict(self) -> dict:
        r = self.record
        return {
            "type": r.item_type,
            "title": r.title,
            "status": r.status,
            "similarity": round(self.score, 4),
            "path": r.path,
            "detail": {
                "keyword": round(self.keyword_score, 4),
                "tag": round(self.tag_score, 4),
                "market": round(self.market_score, 4),
                "strategy": round(self.strategy_score, 4),
                "dataset": round(self.dataset_score, 4),
            },
        }


# ---------------------------------------------------------------------------
# Text / frontmatter utilities
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (fm_dict, body).  Values for list fields are kept raw; splitting
    happens in the caller via ``split_list_value``."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw_fm, body = m.group(1), m.group(2)
    fm: dict[str, str] = {}
    for line in raw_fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            # Strip YAML inline comments (e.g. ``queued  # foo -> bar``)
            v = v.strip()
            if '#' in v:
                v = v.split('#', 1)[0].strip()
            fm[k.strip()] = v
    return fm, body


def split_list_value(raw: str) -> list[str]:
    """Parse a YAML-ish list value: ``[a, b]`` or ``a, b`` or ``"a", "b"``."""
    if not raw:
        return []
    # Strip surrounding brackets
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    parts = re.split(r"[,\n]", raw)
    result = []
    for p in parts:
        p = p.strip().strip('"').strip("'").strip()
        if p and not p.startswith("#"):
            result.append(p.lower())
    return result


def tokenize(text: str) -> set[str]:
    """Lowercase, split on non-alphanumerics, drop stop words and short tokens."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 1 and t not in STOP_WORDS}


def normalize_edge_name(name: str) -> str:
    """Normalise an edge name like ``pairs_gld_gdx`` into readable tokens."""
    return name.replace("_", " ")


# ---------------------------------------------------------------------------
# Parsers -- each returns a list[Record]
# ---------------------------------------------------------------------------


def parse_markdown_notes(directory: str, item_type: str) -> list[Record]:
    """Parse all .md files in *directory* (non-recursive) into Records."""
    records: list[Record] = []
    if not os.path.isdir(directory):
        return records
    for md_path in sorted(glob.glob(os.path.join(directory, "*.md"))):
        fname = os.path.basename(md_path)
        if fname == "README.md":
            continue
        try:
            with open(md_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        title = fm.get("title", fname.removesuffix(".md"))
        status = fm.get("status", "")

        # Gather keywords from title + body (first 500 chars for body context)
        kw = tokenize(title) | tokenize(body[:500])
        # Strip "research", "idea", "experiment" meta keywords to reduce noise
        kw -= {"research", "idea", "experiment", "paper"}

        rec = Record(
            item_type=item_type,
            title=title,
            status=status,
            path=os.path.relpath(md_path, REPO),
            keywords=kw,
        )
        for field_name in FM_LIST_FIELDS:
            vals = set(split_list_value(fm.get(field_name, "")))
            if field_name == "tags":
                rec.tags = vals
            elif field_name == "markets":
                rec.markets = vals
            elif field_name == "strategy_types":
                rec.strategy_types = vals
            elif field_name == "datasets":
                rec.datasets = vals
        records.append(rec)
    return records


def parse_hunt_log() -> list[Record]:
    """Parse HUNT_LOG.md table rows into Records (one per unique edge name)."""
    records: list[Record] = []
    if not os.path.isfile(HUNT_LOG):
        return records
    try:
        with open(HUNT_LOG, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return records

    # Match table rows: | when | edge | IS | OOS | ... | verdict | why |
    # We only need edge name, verdict, and "why" text.
    seen_edges: dict[str, Record] = {}
    row_re = re.compile(r"^\|.*?\|\s*([^|]+?)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|$")
    for line in text.splitlines():
        if not line.startswith("|") or "edge" in line.lower() or "---" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty (leading |), parts[-1] is empty (trailing |)
        parts = parts[1:-1]
        if len(parts) < 11:
            continue
        edge_name = parts[1].strip()
        verdict = parts[9].strip()
        why = parts[10].strip() if len(parts) > 10 else ""
        if not edge_name or edge_name == "edge":
            continue

        readable = normalize_edge_name(edge_name)
        kw = tokenize(readable) | tokenize(why)
        verdict_clean = re.sub(r"\*+", "", verdict).strip()
        status = "PASS" if "PASS" in verdict_clean.upper() else "FAIL"

        # Keep the most recent entry per edge name, but merge why text
        if edge_name in seen_edges:
            seen_edges[edge_name].keywords |= kw
        else:
            seen_edges[edge_name] = Record(
                item_type="hunt-entry",
                title=edge_name,
                status=status,
                path=os.path.relpath(HUNT_LOG, REPO),
                keywords=kw,
            )
    records = list(seen_edges.values())
    return records


def parse_findings() -> list[Record]:
    """Parse FINDINGS.md headings into Records (one per ### topic)."""
    records: list[Record] = []
    if not os.path.isfile(FINDINGS):
        return records
    try:
        with open(FINDINGS, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return records

    # Capture ### headings and following paragraph text until the next heading
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for line in text.splitlines():
        if line.startswith("### "):
            if current_heading:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = line.lstrip("# ").strip()
            current_body = []
        elif line.startswith("## "):
            if current_heading:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = line.lstrip("# ").strip()
            current_body = []
        else:
            current_body.append(line)
    if current_heading:
        sections.append((current_heading, "\n".join(current_body)))

    for heading, body in sections:
        kw = tokenize(heading) | tokenize(body[:400])
        # Determine status from keywords in heading or body
        combined_upper = (heading + " " + body).upper()
        if "REJECTED" in combined_upper or "DO NOT" in combined_upper or "FAIL" in combined_upper:
            status = "rejected"
        elif "VALIDATED" in combined_upper or "KEEP" in combined_upper or "PASS" in combined_upper:
            status = "validated"
        else:
            status = "info"
        records.append(Record(
            item_type="findings-topic",
            title=heading,
            status=status,
            path=os.path.relpath(FINDINGS, REPO),
            keywords=kw,
        ))
    return records


# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def overlap_ratio(small: set[str], big: set[str]) -> float:
    """What fraction of *small* appears in *big*?  Returns 0 if small is empty."""
    if not small:
        return 0.0
    return len(small & big) / len(small)


def score_record(query: Record, candidate: Record) -> Hit:
    """Compute a composite similarity score (0-1) between *query* and *candidate*.

    Keyword scoring uses the *better* of Jaccard (symmetric overlap) and
    directional overlap-ratio (what fraction of query tokens appear in the
    candidate).  This prevents long candidate descriptions from diluting a
    strong but small query match.
    """
    kw_jac = jaccard(query.keywords, candidate.keywords)
    kw_dir = overlap_ratio(query.keywords, candidate.keywords)
    kw_score = max(kw_jac, kw_dir)
    tag_score = jaccard(query.tags, candidate.tags)
    market_score = jaccard(query.markets, candidate.markets)
    strategy_score = jaccard(query.strategy_types, candidate.strategy_types)
    dataset_score = jaccard(query.datasets, candidate.datasets)

    # Weighted composite: keyword overlap dominates (most discriminative)
    # but tag/market/strategy/dataset can bump it up
    composite = (
        0.55 * kw_score
        + 0.15 * tag_score
        + 0.10 * market_score
        + 0.10 * strategy_score
        + 0.10 * dataset_score
    )
    composite = min(composite, 1.0)
    return Hit(
        record=candidate,
        score=composite,
        keyword_score=kw_score,
        tag_score=tag_score,
        market_score=market_score,
        strategy_score=strategy_score,
        dataset_score=dataset_score,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_query(title: str, desc: str) -> Record:
    """Build a synthetic query Record from the CLI title + description."""
    combined = f"{title} {desc}"
    kw = tokenize(combined)
    # Try to extract implicit tags/markets/etc. from keywords
    known_markets = {"qqq", "nasdaq", "spy", "s&p", "etf", "crypto", "futures",
                     "stocks", "bonds", "tlt", "gld", "gold", "iwm", "dia"}
    known_strategies = {"momentum", "mean", "reversion", "pairs", "orb",
                        "opening", "range", "breakout", "sweep", "regime",
                        "filter", "rotation", "reversal", "tsmom"}
    tags = set()
    if "dark" in kw and "pool" in kw:
        tags.add("dark-pool")
    if "dix" in kw:
        tags.add("dix")
    return Record(
        item_type="query",
        title=title,
        keywords=kw,
        tags=tags,
        markets=kw & known_markets,
        strategy_types=kw & known_strategies,
    )


def load_all_records() -> list[Record]:
    """Load all searchable records from the repo."""
    records: list[Record] = []
    # Experiments across queue/experiments/archive
    for d in EXPERIMENT_DIRS:
        records.extend(parse_markdown_notes(d, "experiment"))
    # Ideas
    records.extend(parse_markdown_notes(IDEAS_DIR, "idea"))
    # Papers
    records.extend(parse_markdown_notes(PAPERS_DIR, "paper"))
    # HUNT_LOG
    records.extend(parse_hunt_log())
    # FINDINGS
    records.extend(parse_findings())
    return records


def run(
    title: str,
    desc: str,
    threshold: float,
    as_json: bool,
    dry_run: bool,
) -> int:
    """Main logic. Always returns 0 (warnings are informational)."""

    query = build_query(title, desc)
    records = load_all_records()

    if dry_run:
        counts: dict[str, int] = {}
        for r in records:
            counts[r.item_type] = counts.get(r.item_type, 0) + 1
        if as_json:
            print(json.dumps({
                "dry_run": True,
                "query_title": title,
                "query_keywords": sorted(query.keywords),
                "source_counts": counts,
                "total_records": len(records),
            }, indent=2))
        else:
            print("=== DRY RUN ===")
            print(f"Query title : {title}")
            print(f"Description : {desc or '(none)'}")
            print(f"Query tokens: {', '.join(sorted(query.keywords)) or '(none)'}")
            print(f"\nSources parsed ({len(records)} records):")
            for k in sorted(counts):
                print(f"  {k:20s} {counts[k]}")
        return 0

    # Score every candidate
    hits = [score_record(query, r) for r in records]
    hits = [h for h in hits if h.score >= threshold]
    hits.sort(key=lambda h: h.score, reverse=True)

    # ---- Warnings ----
    warnings: list[str] = []
    infos: list[str] = []

    for h in hits:
        r = h.record
        status_lower = r.status.lower()
        # Rejected experiments or FAIL hunt entries with high similarity
        is_rejected = (
            ("reject" in status_lower)
            or (r.item_type == "hunt-entry" and "fail" in status_lower)
            or (r.item_type == "findings-topic" and "reject" in status_lower)
        )
        is_positive = (
            "valid" in status_lower
            or "pass" in status_lower
            or "active" in status_lower
            or "queued" in status_lower
            or "running" in status_lower
            or "gauntlet" in status_lower
            or (r.item_type == "findings-topic" and "valid" in status_lower)
        )

        if is_rejected and h.score > 0.5:
            warnings.append(
                f"⚠️  WARNING: \"{r.title}\" was REJECTED ({r.status}) "
                f"with similarity {h.score:.2f} — {r.path}"
            )
        elif is_positive and h.score > 0.3:
            infos.append(
                f"ℹ️  INFO: \"{r.title}\" is {r.status} "
                f"with similarity {h.score:.2f} — {r.path}"
            )

    # ---- Output ----
    if as_json:
        output: dict = {
            "query": {
                "title": title,
                "description": desc,
                "keywords": sorted(query.keywords),
                "tags": sorted(query.tags),
            },
            "results": [h.to_dict() for h in hits],
            "warnings": warnings,
            "infos": infos,
            "total_sources": len(records),
            "shown": len(hits),
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"{'='*70}")
        print(f"  Similarity search: \"{title}\"")
        print(f"{'='*70}")
        print(f"\nQuery tokens: {', '.join(sorted(query.keywords)) or '(none)'}")
        if query.tags:
            print(f"Query tags  : {', '.join(sorted(query.tags))}")
        print(f"Sources     : {len(records)} records scanned")
        print(f"Threshold   : {threshold}")
        print()

        if not hits:
            print("No similar items found above threshold.\n")
            print("✅ No overlap with prior work detected. Safe to proceed.")
        else:
            print(f"{'#':>2}  {'Score':>5}  {'Type':<16}  {'Status':<12}  Title")
            print(f"{'—'*70}")
            for i, h in enumerate(hits, 1):
                r = h.record
                title_display = r.title[:45]
                print(f"{i:>2}  {h.score:.2f}   {r.item_type:<16}  {r.status:<12}  {title_display}")
                print(f"    → {r.path}")
            print()

            if warnings:
                for w in warnings:
                    print(w)
                print()
            else:
                print("✅ No high-similarity rejected items found.")

            if infos:
                print()
                for info_msg in infos:
                    print(info_msg)

        print(f"\n{'='*70}")
        print("Read-only tool — no files were modified.")
        print(f"{'='*70}")

    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Find similar prior work before testing a new experiment."
    )
    ap.add_argument("--title", required=True, help="Proposed experiment/idea title.")
    ap.add_argument("--desc", default="", help="Optional description text for richer matching.")
    ap.add_argument("--threshold", type=float, default=0.15,
                    help="Minimum similarity score to show (default: 0.15).")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of text.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse sources and report counts only; do not score.")
    args = ap.parse_args()

    code = run(
        title=args.title,
        desc=args.desc,
        threshold=args.threshold,
        as_json=args.json,
        dry_run=args.dry_run,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
