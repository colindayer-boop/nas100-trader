#!/usr/bin/env python3
"""
strategy_genealogy.py -- build a full genealogy graph of trading strategies.

Scans research notes (papers, ideas, experiments, archive), the HUNT_LOG
graveyard, and production strategies from CURRENT_PROJECT_STATE.md to produce
a Mermaid flowchart + Obsidian-friendly markdown.

Output:  research/results/strategy_genealogy.md
Flags:
    --dry-run   Parse and print summary to stdout; write nothing.
    --print     Print the full output to stdout instead of writing a file.

Never touches production files or human notes. Idempotent.
"""
import argparse
import os
import re
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESEARCH = os.path.join(REPO, "research")
RESULTS = os.path.join(RESEARCH, "results")
OUTPUT = os.path.join(RESULTS, "strategy_genealogy.md")

HUNT_LOG = os.path.join(REPO, "HUNT_LOG.md")
PROJECT_STATE = os.path.join(REPO, "docs", "CURRENT_PROJECT_STATE.md")

# ── production strategies referenced in CURRENT_PROJECT_STATE.md ─────────────
PRODUCTION_STRATEGIES = [
    ("S1", "Asian sweep (QQQ)"),
    ("S2", "Gold FVG"),
    ("S3", "Abnormal volume"),
    ("S4", "Multi-sweep (QQQ+SPY)"),
    ("S5", "ORB long/short"),
    ("SWEEP", "Basket (9 tickers)"),
    ("BTC", "BTC sweep"),
    ("OVN", "Overnight"),
    ("BTCTREND", "BTC trend"),
    ("XSMOM", "Cross-sectional momentum"),
]


# ── frontmatter / wikilink parsing ──────────────────────────────────────────

def parse_frontmatter(text):
    """Return (fm_dict, body) from a markdown file with YAML frontmatter."""
    fm = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if m:
        yaml_block, body = m.group(1), m.group(2)
        for line in yaml_block.splitlines():
            # skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            mm = re.match(r"^(\w[\w-]*)\s*:\s*(.*)$", line)
            if mm:
                key = mm.group(1).strip()
                val = mm.group(2).strip()
                # strip inline comment (after #) but keep quoted hashes
                if not val.startswith('"') and not val.startswith("'"):
                    val = re.sub(r"\s+#.*$", "", val)
                # strip surrounding quotes
                val = val.strip('"').strip("'")
                fm[key] = val
    return fm, body


def extract_wikilinks(body):
    """Return list of wikilink targets (basename, without pipe text)."""
    links = []
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body):
        target = m.group(1).strip()
        # skip non-research vault pages
        if "/" in target:
            continue
        links.append(target)
    return links


def short_label(text, max_len=30):
    """Shorten a label for Mermaid node display."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def safe_node_id(prefix, name):
    """Make a Mermaid-safe node id."""
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{prefix}_{name}")[:60]


# ── scanners ────────────────────────────────────────────────────────────────

def scan_md_dir(directory):
    """Yield (filepath, basename, frontmatter, body) for each .md (skip README)."""
    if not os.path.isdir(directory):
        return
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        path = os.path.join(directory, fname)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fm, body = parse_frontmatter(text)
        basename = fname[:-3]  # strip .md
        yield path, basename, fm, body


def scan_papers():
    """Return list of paper dicts."""
    papers = []
    for path, basename, fm, body in scan_md_dir(os.path.join(RESEARCH, "papers")):
        papers.append({
            "basename": basename,
            "title": fm.get("title", basename),
            "status": fm.get("status", "unknown"),
            "year": fm.get("year", ""),
            "authors": fm.get("authors", ""),
            "wikilinks": extract_wikilinks(body),
            "path": os.path.relpath(path, REPO),
        })
    return papers


def scan_ideas():
    """Return list of idea dicts."""
    ideas = []
    for path, basename, fm, body in scan_md_dir(os.path.join(RESEARCH, "ideas")):
        ideas.append({
            "basename": basename,
            "title": fm.get("title", basename),
            "status": fm.get("status", "unknown"),
            "wikilinks": extract_wikilinks(body),
            "path": os.path.relpath(path, REPO),
        })
    return ideas


def scan_experiments():
    """Return list of experiment dicts from queue, experiments, archive."""
    experiments = []
    for subdir in ("queue", "experiments", "archive"):
        for path, basename, fm, body in scan_md_dir(os.path.join(RESEARCH, subdir)):
            experiments.append({
                "basename": basename,
                "id": fm.get("id", basename),
                "title": fm.get("title", basename),
                "status": fm.get("status", "unknown"),
                "idea": fm.get("idea", "").strip('"').strip("'"),
                "paper": fm.get("paper", "").strip('"').strip("'"),
                "location": subdir,
                "wikilinks": extract_wikilinks(body),
                "path": os.path.relpath(path, REPO),
            })
    return experiments


def scan_hunt_log():
    """Parse HUNT_LOG.md table rows; return list of dicts.

    Columns: when | edge | IS | OOS | OOS_DD | corr | CAGR | pos_mo |
             prop_fit | n | verdict | why
    """
    rows = []
    if not os.path.isfile(HUNT_LOG):
        return rows
    with open(HUNT_LOG, encoding="utf-8") as f:
        text = f.read()
    # table rows: | ... | **PASS** | ...  or  | ... | **FAIL** | ...
    for m in re.finditer(
        r"^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
        r"\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|"
        r"\s*\**(\w+)\**\s*\|\s*([^|]*)\|",
        text, re.MULTILINE
    ):
        edge = m.group(2).strip()
        verdict = m.group(11).strip().upper()
        if verdict not in ("PASS", "FAIL"):
            continue
        rows.append({
            "edge": edge,
            "verdict": verdict,
            "why": m.group(12).strip(),
            "oos_sharpe": m.group(4).strip(),
            "is_sharpe": m.group(3).strip(),
        })
    return rows


def latest_verdicts(hunt_rows):
    """Collapse to the latest verdict per edge name."""
    latest = {}
    for row in hunt_rows:
        latest[row["edge"]] = row  # last one wins (file is chronological)
    return latest


# ── graph construction ─────────────────────────────────────────────────────

class Graph:
    def __init__(self):
        self.nodes = {}       # node_id -> {kind, label, status, meta}
        self.edges = []       # list of (src_id, dst_id, label)
        self._seen_edges = set()

    def add_node(self, node_id, kind, label, status="unknown", meta=None):
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "kind": kind,
                "label": short_label(label),
                "full_label": label,
                "status": status,
                "meta": meta or {},
            }
        else:
            # update if we have better info
            if status != "unknown" and self.nodes[node_id]["status"] == "unknown":
                self.nodes[node_id]["status"] = status

    def add_edge(self, src, dst, label=""):
        key = (src, dst, label)
        if key not in self._seen_edges:
            self._seen_edges.add(key)
            self.edges.append((src, dst, label))


def build_graph(papers, ideas, experiments, hunt_verdicts):
    g = Graph()

    # Papers → nodes
    for p in papers:
        nid = safe_node_id("paper", p["basename"])
        g.add_node(nid, "paper", p["title"], p["status"],
                   {"basename": p["basename"], "path": p["path"]})

    # Ideas → nodes
    for idea in ideas:
        nid = safe_node_id("idea", idea["basename"])
        g.add_node(nid, "idea", idea["title"], idea["status"],
                   {"basename": idea["basename"], "path": idea["path"]})

    # Idea → Paper links (via wikilinks in body)
    for idea in ideas:
        idea_nid = safe_node_id("idea", idea["basename"])
        for link in idea["wikilinks"]:
            paper_nid = safe_node_id("paper", link)
            if paper_nid in g.nodes:
                g.add_edge(paper_nid, idea_nid, "inspires")

    # Experiments → nodes
    for exp in experiments:
        nid = safe_node_id("exp", exp["id"])
        g.add_node(nid, "experiment", f"{exp['id']}: {exp['title']}",
                   exp["status"],
                   {"basename": exp["basename"], "path": exp["path"],
                    "location": exp["location"]})

        # Experiment → Idea
        if exp["idea"]:
            idea_nid = safe_node_id("idea", exp["idea"])
            if idea_nid in g.nodes:
                g.add_edge(idea_nid, nid, "tests")
            else:
                # dangling idea reference -- still create edge
                g.add_node(idea_nid, "idea", exp["idea"], "unknown",
                           {"basename": exp["idea"], "path": ""})
                g.add_edge(idea_nid, nid, "tests")

        # Experiment → Paper
        if exp["paper"]:
            paper_nid = safe_node_id("paper", exp["paper"])
            if paper_nid in g.nodes:
                g.add_edge(paper_nid, nid, "origin")
            else:
                g.add_node(paper_nid, "paper", exp["paper"], "unknown",
                           {"basename": exp["paper"], "path": ""})
                g.add_edge(paper_nid, nid, "origin")

    # HUNT_LOG edges → nodes for rejected edges
    for edge_name, info in hunt_verdicts.items():
        nid = safe_node_id("hunt", edge_name)
        label = edge_name
        status = "rejected" if info["verdict"] == "FAIL" else "validated-hunt"
        g.add_node(nid, "hunt", label, status,
                   {"verdict": info["verdict"], "why": info["why"],
                    "oos_sharpe": info["oos_sharpe"]})

    # Production strategies → nodes
    for short, desc in PRODUCTION_STRATEGIES:
        nid = safe_node_id("prod", short)
        g.add_node(nid, "production", f"{short}: {short_label(desc, 24)}",
                   "production",
                   {"short": short, "desc": desc})

    return g


# ── Mermaid generation ─────────────────────────────────────────────────────

KIND_SHAPES = {
    "paper":       ("[{}]", "rect"),
    "idea":        ("({})", "rounded"),
    "experiment":  ("{{{}}}", "diamond"),
    "production":  ("{{{{{}}}}}", "hexagon"),
    "hunt":        ("[/{}\\]", "parallelogram"),
}

# Mermaid class styles
STATUS_STYLES = {
    "rejected":        "fill:#fdd,stroke:#c00,stroke-width:2px",
    "validated":       "fill:#dfd,stroke:#0a0,stroke-width:2px",
    "validated-hunt":  "fill:#dfd,stroke:#0a0,stroke-width:2px",
    "production":      "fill:#ddf,stroke:#00a,stroke-width:2px",
    "queued":          "fill:#ffd,stroke:#aa0,stroke-width:1px",
    "running":         "fill:#ffd,stroke:#aa0,stroke-width:2px",
    "gauntlet":        "fill:#fed,stroke:#f80,stroke-width:2px",
    "idea":            "fill:#eef,stroke:#88a,stroke-width:1px",
    "unread":          "fill:#eee,stroke:#999,stroke-width:1px",
    "reviewed":        "fill:#eef,stroke:#88a,stroke-width:1px",
    "no-edge":         "fill:#fdd,stroke:#c00,stroke-width:1px",
    "PASS":            "fill:#dfd,stroke:#0a0,stroke-width:1px",
    "FAIL":            "fill:#fdd,stroke:#c00,stroke-width:2px",
}


def mermaid_node_line(node_id, info):
    kind = info["kind"]
    label = info["label"].replace('"', "'")
    shape_fmt, _ = KIND_SHAPES.get(kind, ("({})", "rounded"))
    return f'    {node_id}{shape_fmt.format(label)}'


def generate_mermaid(g):
    lines = ["```mermaid", "flowchart LR"]

    # ── Group by lineage where possible ────────────────────────────────────
    # Subgraphs: papers, ideas, experiments, production, graveyard
    lines.append("    subgraph Papers")
    for nid, info in sorted(g.nodes.items()):
        if info["kind"] == "paper":
            lines.append(mermaid_node_line(nid, info))
    lines.append("    end")

    lines.append("    subgraph Ideas")
    for nid, info in sorted(g.nodes.items()):
        if info["kind"] == "idea":
            lines.append(mermaid_node_line(nid, info))
    lines.append("    end")

    lines.append("    subgraph Experiments")
    for nid, info in sorted(g.nodes.items()):
        if info["kind"] == "experiment":
            lines.append(mermaid_node_line(nid, info))
    lines.append("    end")

    lines.append("    subgraph Production")
    for nid, info in sorted(g.nodes.items()):
        if info["kind"] == "production":
            lines.append(mermaid_node_line(nid, info))
    lines.append("    end")

    lines.append("    subgraph Graveyard [Hunt Log -- Rejected Edges]")
    for nid, info in sorted(g.nodes.items()):
        if info["kind"] == "hunt":
            lines.append(mermaid_node_line(nid, info))
    lines.append("    end")

    # ── Edges ───────────────────────────────────────────────────────────────
    for src, dst, label in g.edges:
        if label:
            lines.append(f"    {src} -->|{label}| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")

    # ── Class definitions ───────────────────────────────────────────────────
    # Assign classes per node
    node_classes = {}
    for nid, info in g.nodes.items():
        status = info["status"]
        if status in STATUS_STYLES:
            node_classes[nid] = status.replace("validated-hunt", "validated")
        elif status in STATUS_STYLES:
            node_classes[nid] = status

    # Emit classDef lines
    seen_classes = set()
    for cls, style in STATUS_STYLES.items():
        cls_clean = cls.replace("validated-hunt", "validated")
        if cls_clean not in seen_classes:
            lines.append(f'    classDef {cls_clean} {style}')
            seen_classes.add(cls_clean)

    # Assign nodes to classes
    for nid, cls in node_classes.items():
        lines.append(f"    class {nid} {cls}")

    lines.append("```")
    return "\n".join(lines)


# ── Markdown generation ────────────────────────────────────────────────────

def generate_markdown(g, papers, ideas, experiments, hunt_verdicts):
    sections = []

    # Header
    sections.append("# Strategy Genealogy")
    sections.append("")
    sections.append("_Auto-generated by `scripts/research/strategy_genealogy.py`. "
                    "Idempotent -- re-run anytime._")
    sections.append("")
    sections.append(f"**Nodes:** {len(g.nodes)} | **Edges:** {len(g.edges)}")
    sections.append("")

    # Mermaid diagram
    sections.append("## Flowchart")
    sections.append("")
    sections.append(generate_mermaid(g))
    sections.append("")

    # Legend
    sections.append("### Legend")
    sections.append("")
    sections.append("| Shape | Meaning |")
    sections.append("|---|---|")
    sections.append("| `[Rectangle]` | Research paper |")
    sections.append("| `(Rounded)` | Idea |")
    sections.append("| `{Diamond}` | Experiment (color = status) |")
    sections.append("| `{{Hexagon}}` | Production strategy |")
    sections.append("| `[/Parallelogram/]` | Hunt-log edge (rejected/validated) |")
    sections.append("")
    sections.append("| Color | Status |")
    sections.append("|---|---|")
    sections.append("| Red | Rejected / Failed |")
    sections.append("| Green | Validated / Passed |")
    sections.append("| Blue | Production |")
    sections.append("| Yellow | Queued / Running |")
    sections.append("| Orange | In gauntlet |")
    sections.append("| Gray | Unread / No-edge |")
    sections.append("")

    # Papers index
    sections.append("## Papers")
    sections.append("")
    if papers:
        for p in papers:
            status_badge = f" `{p['status']}`" if p["status"] else ""
            sections.append(f"- [[{p['basename']}|{p['title']}]]{status_badge}"
                            f" — {p['authors']} ({p['year']})")
    else:
        sections.append("_No papers yet._")
    sections.append("")

    # Ideas index
    sections.append("## Ideas")
    sections.append("")
    if ideas:
        for idea in ideas:
            status_badge = f" `{idea['status']}`" if idea["status"] else ""
            sections.append(f"- [[{idea['basename']}|{idea['title']}]]{status_badge}")
    else:
        sections.append("_No ideas yet._")
    sections.append("")

    # Experiments index
    sections.append("## Experiments")
    sections.append("")
    if experiments:
        for exp in experiments:
            loc = exp["location"]
            status_badge = f" `{exp['status']}`" if exp["status"] else ""
            sections.append(f"- [[{exp['basename']}|{exp['id']}: {exp['title']}]]"
                            f"{status_badge} _({loc})_")
    else:
        sections.append("_No experiments yet._")
    sections.append("")

    # Production strategies
    sections.append("## Production Strategies")
    sections.append("")
    sections.append("_From `docs/CURRENT_PROJECT_STATE.md` -- frozen during "
                    "30-day statistics window._")
    sections.append("")
    for short, desc in PRODUCTION_STRATEGIES:
        sections.append(f"- **{short}** — {desc}")
    sections.append("")

    # Graveyard
    sections.append("## Graveyard (HUNT_LOG)")
    sections.append("")
    sections.append("_Edges already tested. Do NOT re-test rejected edges._")
    sections.append("")
    if hunt_verdicts:
        sections.append("| Edge | Verdict | OOS Sharpe | Why |")
        sections.append("|---|---|---|---|")
        for edge, info in sorted(hunt_verdicts.items()):
            verdict_emoji = "PASS" if info["verdict"] == "PASS" else "~~FAIL~~"
            sections.append(f"| `{edge}` | {verdict_emoji} | "
                            f"{info['oos_sharpe']} | {info['why']} |")
    else:
        sections.append("_Hunt log empty or not found._")
    sections.append("")

    # Links section
    sections.append("## Links")
    sections.append("")
    sections.append("[[Research Index]] | "
                    "[[02-Strategy-Research/Gauntlet|Gauntlet]] | "
                    "[[00 Dashboard]]")
    sections.append("")

    return "\n".join(sections)


# ── summary for --dry-run ──────────────────────────────────────────────────

def print_summary(g, papers, ideas, experiments, hunt_rows, hunt_verdicts):
    print("=== Strategy Genealogy -- Dry Run Summary ===")
    print()
    print(f"Papers:       {len(papers)}")
    for p in papers:
        print(f"  - {p['basename']} [{p['status']}]")
    print()
    print(f"Ideas:        {len(ideas)}")
    for i in ideas:
        print(f"  - {i['basename']} [{i['status']}]")
    print()
    print(f"Experiments:  {len(experiments)}")
    for e in experiments:
        print(f"  - {e['id']} [{e['status']}] ({e['location']})"
              f"  idea={e['idea'] or '—'}  paper={e['paper'] or '—'}")
    print()
    print(f"Hunt rows:    {len(hunt_rows)} total, "
          f"{len(hunt_verdicts)} unique edges")
    fails = sum(1 for v in hunt_verdicts.values() if v["verdict"] == "FAIL")
    passes = sum(1 for v in hunt_verdicts.values() if v["verdict"] == "PASS")
    print(f"              {fails} FAIL, {passes} PASS")
    print()
    print(f"Graph nodes:  {len(g.nodes)}")
    print(f"Graph edges:  {len(g.edges)}")
    print()
    print("Production strategies referenced:")
    for short, desc in PRODUCTION_STRATEGIES:
        print(f"  - {short}: {desc}")
    print()
    print(f"Output target: {os.path.relpath(OUTPUT, REPO)}")
    print("(dry-run: nothing written)")


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Build strategy genealogy graph from research notes.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and print summary; write nothing.")
    ap.add_argument("--print", action="store_true",
                    help="Print output to stdout instead of writing file.")
    args = ap.parse_args()

    # Scan everything
    papers = scan_papers()
    ideas = scan_ideas()
    experiments = scan_experiments()
    hunt_rows = scan_hunt_log()
    hunt_verdicts = latest_verdicts(hunt_rows)

    # Build graph
    g = build_graph(papers, ideas, experiments, hunt_verdicts)

    if args.dry_run:
        print_summary(g, papers, ideas, experiments, hunt_rows, hunt_verdicts)
        return

    # Generate output
    md = generate_markdown(g, papers, ideas, experiments, hunt_verdicts)

    if args.print:
        print(md)
        return

    # Write to file
    os.makedirs(RESULTS, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Written {os.path.relpath(OUTPUT, REPO)}  "
          f"({len(g.nodes)} nodes, {len(g.edges)} edges)")


if __name__ == "__main__":
    main()
