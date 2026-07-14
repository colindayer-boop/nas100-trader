# Multi-model delegation bridge

One command hands a task to a local/subscription model, validates the reply against
a fixed contract, and collects it into the task. Claude stays the final reviewer and
the only agent allowed to change production. Backends run as fixed argv (never
shell=True, never model-controlled commands); model output is untrusted text.

## Five commands
```bash
python scripts/router/task_router.py delegate TASK-20260710-02              # auto-route
python scripts/router/task_router.py delegate TASK-20260710-02 --backend qwen       # 7B local worker
python scripts/router/task_router.py delegate TASK-20260710-02 --backend qwen-deep  # 14B deeper
python scripts/router/task_router.py delegate TASK-20260710-02 --backend glm        # GLM-5.2 via OpenClaw/z.ai
python scripts/router/task_router.py bridge-status                          # health of all backends
```

## Auto-routing (deterministic)
- **qwen (7B)** — logs, indexing, extraction, summaries, repo search, links (default).
- **qwen-deep (14B)** — adversarial/implementation/multi-file review, repo-wide reasoning.
  Also the auto-escalation when a 7B reply fails the response contract twice.
- **glm** — papers, literature, macro, long-context synthesis, independent research review.

One task → one primary backend. A second backend is used only on contract failure
(7B→14B) or when routing selects it; the reason is recorded in the delegation log.

## Response contract (enforced)
Replies must contain `# Findings`, `# Evidence`, `# Risks`, `# Recommendation`, and
exactly one of `NO_ACTION | INVESTIGATE | CREATE_EXPERIMENT | REVIEW_REQUIRED | REJECT`.
Invalid replies are kept for debugging, retried once, and never collected as valid.

## Backends (discovered + verified 2026-07-14)
| backend | command | verified |
|---|---|---|
| qwen | `cat {brief} \| ollama run qwen2.5-coder:7b` | ✓ live (28s) |
| qwen-deep | `... qwen2.5-coder:14b` | ✓ live (55s) |
| glm | `openclaw agent --model glm-5.2 --message-file {brief} --json --session-key delegate-{task}` | ✓ live (85s, provider zai) |

Ollama: the bridge checks `http://127.0.0.1:11434/api/tags` and, if down, kickstarts
the existing LaunchAgent `com.colindayer.ollama` (bounded 30s wait; never spawns a
second server). Config lives in `config.ini [llm_bridge]`; observability in
`state/router_state.json` (last success/failure) and each task's `## Delegation log`.

Trading OS launcher → **Bridge** menu: Status · Restart Ollama · Test Qwen · Test GLM.
