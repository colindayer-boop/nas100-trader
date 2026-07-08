You are the senior engineer responsible for this repository.

You have full autonomy.

Your objective is to improve the repository while preserving all trading behaviour.

====================================================================
HARD RULES
====================================================================

NEVER modify:

- live_trader.py
- broker.py
- mt5_broker.py
- config.ini
- strategy logic
- execution logic
- position sizing
- risk calculations
- anything that could change live trading behaviour

You may improve infrastructure only.

Every change must preserve behaviour.

====================================================================
TASK 1
====================================================================

If the Streamlit dashboard has already been completed, verify it only.

Otherwise rebuild it.

Dashboard requirements:

- dashboard/app.py
- dashboard/README.md
- requirements-dashboard.txt

Requirements:

- pathlib only
- read-only
- defensive programming
- never crash on missing logs
- never crash on malformed JSON
- auto refresh
- health cards
- risk table
- recent orders
- recent fills
- warnings/errors
- last 100 log lines

If already complete, skip immediately.

====================================================================
TASK 2
====================================================================

Perform a complete repository audit.

Identify:

- dead code
- duplicate code
- unused files
- TODO
- FIXME
- technical debt
- unsafe assumptions
- inconsistent naming
- missing documentation
- opportunities for cleanup

Write:

docs/PROJECT_AUDIT.md

====================================================================
TASK 3
====================================================================

Finish architecture documentation.

Create every missing architecture document.

Only improve incomplete documents.

Do not rewrite finished ones.

====================================================================
TASK 4
====================================================================

Improve README.

Include:

- overview
- architecture
- installation
- dashboard
- brokers
- sessions
- deployment
- troubleshooting
- project structure

====================================================================
TASK 5
====================================================================

Perform a repository-wide infrastructure cleanup.

Allowed improvements:

- pathlib
- typing
- logging
- exception handling
- imports
- documentation
- comments
- cleanup
- resource management
- defensive programming

Never change trading behaviour.

====================================================================
TASK 6
====================================================================

Search for bugs that do NOT affect strategy behaviour.

Fix only infrastructure bugs.

Leave trading logic untouched.

====================================================================
TASK 7
====================================================================

Create:

docs/WORK_COMPLETED.md

Include:

- every modified file
- every new file
- every improvement
- every skipped task
- remaining recommendations
- technical debt still present

====================================================================
WORK STYLE
====================================================================

Work like a senior software engineer.

Do not ask for confirmation.

Do not stop between tasks.

After every completed task:

- immediately save all modified files

Then continue automatically.

If one task cannot be completed:

- document why
- continue with the next task

Continue until every possible task has been completed.

Only finish after writing docs/WORK_COMPLETED.md.

Never stop early.
