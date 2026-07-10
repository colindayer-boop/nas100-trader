"""dispatch.py -- routing rules: task type -> AI system.

From the mission + AI_OPERATING_SYSTEM.md roles:
    Production bugs         -> Claude        (Lead Engineer)
    Research implementation -> GLM           (research scripts only)
    Paper analysis          -> Qwen
    Independent review      -> Fable         (author != reviewer rule)
    Operations              -> OpenClaw scheduler

The router ASSIGNS; it never performs work. Note: 'implementation' means
production-side work (bugs) and is gated by the AI Operating System's
evidence-before-edits law -- assignment is not authorization.
"""
ROUTES = {
    "implementation": "Claude",          # production bugs / Lead Engineer
    "research":       "GLM",             # research implementation
    "paper":          "Qwen",            # paper analysis
    "review":         "Fable",           # independent review
    "ops":            "OpenClaw",        # operations / scheduler
    "monitoring":     "OpenClaw",        # nightly/report jobs
    "dashboard":      "GLM",             # research-side UI work
    "documentation":  "Claude",          # governance docs
}

FALLBACK = "Claude"


def choose(task):
    """Return the AI system that owns this task type."""
    owner = ROUTES.get(task.type, FALLBACK)
    # review tasks must not be assigned to whoever is listed as having authored
    # the reviewed artifact (author != reviewer). The task's `reviewer` field, if
    # pre-set by a human, wins over the routing table.
    if task.type == "review" and task.reviewer:
        return task.reviewer
    return owner
