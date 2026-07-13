"""link_strategies.py -- inject a standard navigation/evidence footer into each
strategy note in vault/03-Validated-Strategies, derived from knowledge_graph.json.
Documentation only. Idempotent: replaces the block between the AUTO markers."""
import json, os, re
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KG = json.load(open(os.path.join(REPO, "knowledge_graph.json")))
NOTE = {"S1":"S1 Asian Sweep","S2":"S2 Gold FVG","S3":"S3 Abnormal Volume","S4":"S4 Multi Sweep",
        "S5":"S5 ORB","OVN":"Overnight Drift","BTC":"BTC Sweep","BTCTREND":"BTC Trend"}
nodes = {n["id"]: n for n in KG["nodes"]}
M0, M1 = "<!-- KG-NAV:START -->", "<!-- KG-NAV:END -->"

def linked(node_id):
    """obsidian [[wikilink]] for a node's file if it's a vault note, else a doc ref."""
    n = nodes.get(node_id, {})
    f = n.get("file", node_id)
    if f.startswith("vault/"):
        return f"[[{os.path.splitext(os.path.basename(f))[0]}]]"
    return f"`{f}`" if f.endswith((".md", ".py")) else node_id

for sid, note in NOTE.items():
    path = os.path.join(REPO, "vault", "03-Validated-Strategies", f"{note}.md")
    if not os.path.exists(path):
        continue
    out = [f"\n{M0}", "## Navigation (auto -- from knowledge graph)"]
    # the five questions, answered from edges touching this strategy
    e = KG["edges"]
    val = [x["target"] for x in e if x["source"] == sid and x["rel"] == "validated_by"]
    rev = [x["target"] for x in e if x["source"] == sid and x["rel"] == "reviewed_by"]
    sha = [x["target"] for x in e if x["source"] == sid and x["rel"] == "shadowed_by"]
    kill = [x["source"] for x in e if x["target"] == sid and x["rel"] == "contradicts"]
    dep = [x["target"] for x in e if x["source"] == sid and x["rel"] == "depends_on" and x["target"] != sid]
    v = nodes[sid].get("validation", "?")
    out.append(f"- **Why does this exist?** validated lineage; current validation status **{v}**"
               + (f"; depends on {', '.join(linked(d) for d in dep)}" if dep else ""))
    out.append(f"- **What evidence supports it?** " + (", ".join(linked(x) for x in (val + rev)) or "see audits"))
    out.append(f"- **What killed alternatives?** " + (", ".join(linked(x) for x in kill) or "none rejected against this strategy"))
    out.append(f"- **What is shadowing / waiting?** " + (", ".join(linked(x) for x in sha) or "not shadowed (live strategy)"))
    out.append(f"- **Latest review:** [[STRATEGY_VALIDATION_AUDIT]] · master index [[KNOWLEDGE_GRAPH]]")
    out.append("\nSee also: [[MONTHLY_EVIDENCE_COMMITTEE]] · [[RESEARCH_BACKLOG]] · [[RESEARCH_GRAVEYARD_AUDIT]] · dashboard STRATEGIES page")
    out.append(M1)
    block = "\n".join(out)
    cur = open(path, encoding="utf-8").read()
    if M0 in cur:
        cur = re.sub(re.escape(M0) + r".*?" + re.escape(M1), block.strip(), cur, flags=re.S)
    else:
        cur = cur.rstrip() + "\n" + block + "\n"
    open(path, "w", encoding="utf-8").write(cur)
    print(f"linked {note}")
