# Obsidian Bridge

Turns repository data (git history, AI changelog, trader logs, governance docs)
into graph-friendly notes under `vault/auto/`. Read-only on the repo; never
touches trading code or hand-written notes.

## Installation

Nothing to install — stdlib Python 3 only.

```
python scripts/obsidian/build_obsidian.py            # build/refresh
python scripts/obsidian/build_obsidian.py --dry-run  # preview changes
```

Open the **repo root** as your Obsidian vault (Dataview plugin recommended);
generated notes appear under `vault/auto/`, entry point `[[Auto Index]]`.

## Folder layout (generated)

```
vault/auto/
  Auto Index.md                      master index
  Daily/YYYY-MM-DD.md                daily note (sessions/signals/errors + links)
  AI/        AI Index, AI Session Log        (mirrors docs/AI_CHANGELOG.md)
  Trading/   Trading Index, Trade Journal    (FILL/EXIT/dry-fill lines from logs)
  Strategies/ Strategies Index               (links to hand-written pages, no dupes)
  Research/  Research Index, Research Notes  (HUNT_LOG/SWEEP/FINDINGS pointers)
  Production/ Production Index, Git Commits, Bugs Fixed, Dashboard Snapshot
  Incidents/ Incidents Index                 (links to vault post-mortems)
  Monitoring/ Monitoring Index, Monitoring Report
```

## Safety model

- Generated content sits between `<!-- AUTO:BEGIN -->` / `<!-- AUTO:END -->`
  markers. Re-runs replace ONLY that block; anything you type outside it in a
  generated note is preserved. Hand-written vault notes are never written.
- Idempotent: same inputs -> identical output; safe on a schedule or in a hook.
- Never embeds binaries; screenshots are linked (`![[../attachments/x.png]]`).

## Scheduled usage

- **Mac (manual/daily):** run after each session, or add to a git post-commit hook:
  `.git/hooks/post-commit` -> `python scripts/obsidian/build_obsidian.py >/dev/null 2>&1 &`
- **VPS (optional):**
  `schtasks /create /tn "nas100-obsidian" /sc DAILY /st 21:45 /f /tr "cmd /c cd /d <repo> && python scripts\obsidian\build_obsidian.py"`
- Per AI_OPERATING_SYSTEM.md section 5, this is an Ops-Runner job: it REPORTS,
  it never modifies code.
