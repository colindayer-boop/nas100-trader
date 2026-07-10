"""queue.py -- load/save tasks in research/queue/ (TASK-*.md only)."""
import glob
import os
import re
from datetime import date

from models import Task, parse, serialize

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUEUE_DIR = os.path.join(REPO, "research", "queue")


def _slug(s):
    return re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")[:48] or "task"


def task_path(task_id):
    hits = glob.glob(os.path.join(QUEUE_DIR, f"{task_id}-*.md"))
    return hits[0] if hits else None


def load_all():
    """Every TASK-*.md in the queue -> [Task]. Ignores EXP notes, READMEs, humans."""
    out = []
    for p in sorted(glob.glob(os.path.join(QUEUE_DIR, "TASK-*.md"))):
        t = parse(open(p, encoding="utf-8").read())
        if t is not None:
            out.append((p, t))
    return out


def save(path, task: Task):
    open(path, "w", encoding="utf-8").write(serialize(task))


def next_id():
    stamp = date.today().strftime("%Y%m%d")
    ns = [int(m.group(1)) for p in glob.glob(os.path.join(QUEUE_DIR, f"TASK-{stamp}-*.md"))
          if (m := re.search(rf"TASK-{stamp}-(\d+)", os.path.basename(p)))]
    return f"TASK-{stamp}-{(max(ns) + 1) if ns else 1:02d}"


def create(title, type_="research", priority="P2", inputs="", outputs="",
           dependencies="", reviewer=""):
    """Create a new queued task file. Never overwrites."""
    os.makedirs(QUEUE_DIR, exist_ok=True)
    tid = next_id()
    t = Task(id=tid, title=title, type=type_, priority=priority, inputs=inputs,
             outputs=outputs, dependencies=dependencies, reviewer=reviewer)
    errs = t.validate()
    if errs:
        raise ValueError("; ".join(errs))
    t.body = (f"\n# {tid} - {title}\n\n## Context\n_(fill in)_\n\n"
              f"## Acceptance criteria\n- \n\n"
              f"## Links\n[[Research Index]] | [[00 Dashboard]]\n")
    path = os.path.join(QUEUE_DIR, f"{tid}-{_slug(title)}.md")
    if os.path.exists(path):
        raise FileExistsError(path)
    save(path, t)
    return path, t
