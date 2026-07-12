"""llm_bridge.py -- delegate router tasks to your subscription models (GLM/Qwen).

Purpose: reduce expensive-model token use. Cheap/subscription models do the
reading-heavy work (paper summaries, log triage, independent reviews); the Lead
Engineer only reads their outputs.

Two modes:

1. FILE mode (works today, zero config):
     python scripts/router/task_router.py brief TASK-20260710-02
   -> writes research/handoffs/<Owner>/TASK-...-BRIEF.md : a SELF-CONTAINED prompt
     (role, context docs inlined, the task, required return format). Paste it into
     OpenClaw GLM / Qwen chat. Save the model's reply as ...-REPLY.md, then:
     python scripts/router/task_router.py collect TASK-20260710-02
   -> ingests the reply into the task body, status -> review (human/lead reads it).

2. AUTO mode (optional): if config.ini has
     [llm_bridge]
     glm_cmd   = openclaw run --model glm-4.6 --prompt-file {brief}
     qwen_cmd  = qwen chat --file {brief}
   the brief is piped straight to your CLI and the reply captured automatically.
   {brief} is replaced with the brief path. Command output = the reply.

Guardrails: subscription models get READ-ONLY work products. Their replies land as
review-status task attachments -- they never touch code, production, or the vault
directly (OS rule: research firewall + reviewer-diversity, which this finally makes
real: GLM/Qwen ARE different models).
"""
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import queue as q                    # noqa: E402

REPO = q.REPO
HANDOFF = os.path.join(REPO, "research", "handoffs")

# context each role needs, kept SMALL on purpose (that's the token saving)
ROLE_CONTEXT = {
    "Qwen":  ["docs/CURRENT_PROJECT_STATE.md"],
    "GLM":   ["docs/CURRENT_PROJECT_STATE.md", "docs/RESEARCH_BACKLOG.md"],
    "Fable": ["docs/CURRENT_PROJECT_STATE.md"],
}
RETURN_FORMAT = """
## Required return format
Reply in markdown with EXACTLY these sections:
### Summary            (<= 10 lines)
### Findings           (bullet list, evidence-first, no speculation)
### Recommendation     (one of: NO_ACTION | NEEDS_LEAD_REVIEW | REJECT)
### Confidence         (LOW | MED | HIGH + one line why)
Do not propose code changes. Do not invent data. If context is insufficient,
say exactly what file/number you need."""


def _find(task_id):
    p = q.task_path(task_id)
    if not p:
        raise SystemExit(f"not found in research/queue: {task_id}")
    return p


def brief(task_id):
    path = _find(task_id)
    from models import parse
    t = parse(open(path, encoding="utf-8").read())
    owner = t.owner or "GLM"
    outdir = os.path.join(HANDOFF, owner)
    os.makedirs(outdir, exist_ok=True)
    ctx_parts = []
    for rel in ROLE_CONTEXT.get(owner, ["docs/CURRENT_PROJECT_STATE.md"]):
        p = os.path.join(REPO, rel)
        if os.path.exists(p):
            body = open(p, encoding="utf-8", errors="replace").read()[:6000]
            ctx_parts.append(f"---- CONTEXT: {rel} (truncated) ----\n{body}")
    out = os.path.join(outdir, f"{task_id}-BRIEF.md")
    open(out, "w", encoding="utf-8").write(
        f"# TASK BRIEF for {owner} -- {task_id}\n\n"
        f"You are the **{owner}** role in a multi-model trading-research system "
        f"(read-only analyst: you summarize/review; you never modify code or data).\n\n"
        f"## The task\n**{t.title}**\n\n{t.body.strip()[:3000]}\n\n"
        f"## Inputs field\n`{t.inputs}`\n\n"
        + "\n\n".join(ctx_parts) + "\n" + RETURN_FORMAT + "\n")
    print(f"brief written: {os.path.relpath(out, REPO)}")

    # AUTO mode: run the configured CLI if present
    cmd = _bridge_cmd(owner)
    if cmd:
        reply = out.replace("-BRIEF.md", "-REPLY.md")
        full = cmd.replace("{brief}", out)
        print(f"auto mode: running `{full}`")
        try:
            r = subprocess.run(full, shell=True, capture_output=True, text=True,
                               timeout=600)
            open(reply, "w", encoding="utf-8").write(r.stdout or r.stderr)
            print(f"reply captured: {os.path.relpath(reply, REPO)} (rc={r.returncode})")
            return collect(task_id)
        except Exception as e:
            print(f"auto mode failed ({e}) -- fall back to FILE mode: paste the brief manually")
    else:
        print(f"FILE mode: paste the brief into your {owner} chat, save the reply as "
              f"{os.path.relpath(out.replace('-BRIEF.md', '-REPLY.md'), REPO)}, then run:"
              f"\n  python scripts/router/task_router.py collect {task_id}")


def _bridge_cmd(owner):
    try:
        import configparser
        cp = configparser.ConfigParser()
        cp.read(os.path.join(REPO, "config.ini"))
        return cp.get("llm_bridge", f"{owner.lower()}_cmd", fallback="").strip() or None
    except Exception:
        return None


def collect(task_id):
    path = _find(task_id)
    from models import parse
    t = parse(open(path, encoding="utf-8").read())
    owner = t.owner or "GLM"
    reply = os.path.join(HANDOFF, owner, f"{task_id}-REPLY.md")
    if not os.path.exists(reply):
        raise SystemExit(f"no reply file: {os.path.relpath(reply, REPO)}")
    body = open(reply, encoding="utf-8", errors="replace").read().strip()
    rec = (re.search(r"### Recommendation\s*\n\s*(\w+)", body) or [None, "?"])[1]
    t.body += (f"\n## {owner} reply ({datetime.now():%Y-%m-%d %H:%M}) -- "
               f"recommendation: {rec}\n\n{body[:8000]}\n")
    t.status = "review"
    q.save(path, t)
    print(f"{task_id}: {owner} reply ingested ({len(body)} chars, rec={rec}) -> status=review")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] in ("brief", "collect"):
        (brief if sys.argv[1] == "brief" else collect)(sys.argv[2])
    else:
        print(__doc__)
