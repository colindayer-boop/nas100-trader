"""models.py -- task data model + markdown/frontmatter (de)serialization.

A task is one markdown file in research/queue/ named TASK-YYYYMMDD-NN-<slug>.md.
The router ONLY touches TASK-*.md files -- experiment notes (EXP-*), READMEs and
any human note are structurally invisible to it.
"""
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

STATUSES = ["queued", "running", "review", "approved", "rejected", "completed"]
TYPES = ["research", "paper", "implementation", "review",
         "dashboard", "documentation", "ops", "monitoring"]
PRIORITIES = ["P0", "P1", "P2", "P3"]          # P0 = most urgent
TERMINAL = {"approved", "rejected", "completed"}

FIELDS = ["id", "title", "status", "priority", "type", "owner", "reviewer",
          "created", "updated", "inputs", "outputs", "dependencies", "artifacts"]


@dataclass
class Task:
    id: str
    title: str
    status: str = "queued"
    priority: str = "P2"
    type: str = "research"
    owner: str = ""
    reviewer: str = ""
    created: str = field(default_factory=lambda: date.today().isoformat())
    updated: str = field(default_factory=lambda: date.today().isoformat())
    inputs: str = ""
    outputs: str = ""
    dependencies: str = ""
    artifacts: str = ""
    body: str = ""          # everything after the frontmatter -- NEVER regenerated

    def validate(self):
        errs = []
        if self.status not in STATUSES:
            errs.append(f"bad status '{self.status}'")
        if self.type not in TYPES:
            errs.append(f"bad type '{self.type}'")
        if self.priority not in PRIORITIES:
            errs.append(f"bad priority '{self.priority}'")
        return errs


def parse(text):
    """Parse a task markdown file -> Task, or None if it has no task frontmatter."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None
    fm, body = m.group(1), m.group(2)
    vals = {}
    for line in fm.splitlines():
        km = re.match(r"^([a-z_]+):\s*\"?(.*?)\"?\s*$", line)
        if km and km.group(1) in FIELDS:
            vals[km.group(1)] = km.group(2)
    if "id" not in vals or not vals["id"].startswith("TASK-"):
        return None
    t = Task(id=vals["id"], title=vals.get("title", "(untitled)"))
    for k in FIELDS:
        if k in vals:
            setattr(t, k, vals[k])
    t.body = body
    return t


def serialize(t: Task):
    """Task -> markdown. Frontmatter is regenerated; the BODY is passed through
    verbatim so human notes below the frontmatter are never overwritten."""
    t.updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    fm = "\n".join(f'{k}: "{getattr(t, k)}"' for k in FIELDS)
    return f"---\n{fm}\n---\n{t.body}"
