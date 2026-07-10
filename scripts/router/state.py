"""state.py -- router state persistence (state/router_state.json).

Records every assignment the router has made so reruns are idempotent: a task
already assigned (status != queued, or present in the ledger) is never
re-dispatched or duplicated. State is derivative -- the task files remain the
source of truth; deleting the state file only loses the assignment history.
"""
import json
import os
from datetime import datetime

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_PATH = os.path.join(REPO, "state", "router_state.json")


def load():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"assignments": {}, "runs": []}


def save(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, STATE_PATH)


def record_run(st, assigned, skipped):
    st["runs"].append({
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assigned": [t.id for t in assigned],
        "skipped": skipped,
    })
    st["runs"] = st["runs"][-50:]          # keep the last 50 runs
    for t in assigned:
        st["assignments"][t.id] = {"owner": t.owner, "at": t.updated,
                                   "type": t.type, "priority": t.priority}
    return st
