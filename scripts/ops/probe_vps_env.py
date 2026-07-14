"""probe_vps_env.py -- Phase 1 environment audit. RUN ON THE VPS. Read-only.

Emits the facts the Mac cannot know (paths, interpreter, MT5 connectivity, schemas)
so nothing is guessed. Prints JSON. Never trades, never writes evidence, no secrets.

    python scripts/ops/probe_vps_env.py
"""
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
out = {"repo_path": REPO, "python_exe": sys.executable, "python_version": sys.version.split()[0]}

# MT5 terminal path + connectivity under the CURRENT account (run this as the scheduler
# account AND interactively to compare -- SYSTEM often cannot see the live terminal).
try:
    import MetaTrader5 as mt5
    sys.path.insert(0, REPO)
    from broker import load_config
    cfg = load_config("mt5")
    ok = mt5.initialize(login=int(cfg.get("login", "0") or 0),
                        password=cfg.get("password", ""), server=cfg.get("server", ""))
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    out["mt5"] = {"initialize_ok": bool(ok),
                  "terminal_path": getattr(ti, "path", None),
                  "connected": getattr(ti, "connected", None),
                  "account_reachable": ai is not None,
                  "last_error": mt5.last_error() if not ok else None}
    # schema samples (field names only, NO values -> no secrets/PII)
    if ai is not None:
        out["schema_account_info"] = [k for k in dir(ai) if not k.startswith("_")][:40]
    pos = mt5.positions_get()
    if pos:
        out["schema_position"] = [k for k in dir(pos[0]) if not k.startswith("_")][:40]
    mt5.shutdown()
except Exception as e:
    out["mt5"] = {"error": str(e), "note": "MetaTrader5 unavailable in this context"}

# who am I running as (SYSTEM vs Administrator matters for MT5 access)
try:
    out["run_as_user"] = subprocess.run(["whoami"], capture_output=True, text=True).stdout.strip()
except Exception:
    out["run_as_user"] = None

# fills.csv schema (header only)
fp = os.path.join(REPO, "logs", "fills.csv")
out["fills_header"] = open(fp).readline().strip().split(",") if os.path.exists(fp) else "MISSING"
out["log_files"] = [f for f in os.listdir(os.path.join(REPO, "logs"))
                    if f.endswith(".log")] if os.path.isdir(os.path.join(REPO, "logs")) else []

# scheduled tasks relevant to trading (names only)
try:
    r = subprocess.run(["schtasks", "/query", "/fo", "LIST"], capture_output=True, text=True, timeout=15)
    out["scheduled_tasks"] = [l.split(":", 1)[1].strip() for l in r.stdout.splitlines()
                              if l.lower().startswith("taskname") and "nas100" in l.lower()]
except Exception:
    out["scheduled_tasks"] = "schtasks unavailable"

print(json.dumps(out, indent=2, default=str))
print("\n# Paste this JSON back to Claude. It contains NO secrets (field names + paths only).",
      file=sys.stderr)
