"""shadow.py -- PHASE 601 Stage 11. Shadow execution framework. For every eligible signal it runs
the FULL production pipeline (authorize -> reconcile -> ledger) and records the hypothetical broker
command, but PLACES NO ORDER. This is the only mode permitted until Stage 12 human approval.

Also the parity primitive (Stage 10): replay any historical trade through authorize() and see what
the rewired system would have decided.
"""
from __future__ import annotations
import json, os, time
from .gate import authorize, Signal

SHADOW_LOG = "registry/shadow_log.jsonl"


def shadow_step(signal: Signal, *, registry, inference, guardian_ok, equity,
                account_is_demo, open_positions, prop_ok=True, now=None, log=SHADOW_LOG) -> dict:
    """Run one signal through the gate in shadow. Records the decision + (if allowed) the intent that
    WOULD have been sent. Never submits. prop_ok folds Stage-5 survival in as an extra veto."""
    dec = authorize(signal, registry=registry, inference=inference, guardian_ok=guardian_ok and prop_ok,
                    equity=equity, account_is_demo=account_is_demo, open_positions=open_positions,
                    now=now, shadow=True)
    dec["placed_order"] = False                    # invariant: shadow never places
    dec["would_send"] = dec.get("order_intent") if dec["decision"] == "ALLOW_PAPER" else None
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a") as f:
        f.write(json.dumps({"ts": dec["timestamp"], "signal": signal.signal_id,
                            "decision": dec["decision"], "reasons": dec["reason_codes"]}) + "\n")
    return dec


def parity_replay(historical_trades: list, *, registry, inference, equity) -> dict:
    """Stage 10: replay past live/demo trades through the rewired gate. Classify each divergence.
    A trade the real system took but the gate BLOCKS is the whole point of the recovery."""
    out = []
    for t in historical_trades:
        s = Signal(signal_id=t.get("ticket", "?"), strategy_id=t.get("strategy_id", "unknown"),
                   strategy_version=t.get("version", "unknown"), symbol=t["symbol"],
                   direction=t.get("direction", 1), entry=t["entry"],
                   stop_loss=t.get("sl", 0), take_profit=t.get("tp"))
        d = authorize(s, registry=registry, inference=inference, guardian_ok=True, equity=equity,
                      account_is_demo=True, open_positions=[], shadow=True)
        cls = "BLOCKED_BY_REWIRE" if d["decision"] != "ALLOW_PAPER" else "WOULD_ALLOW"
        out.append({"ticket": t.get("ticket"), "symbol": t["symbol"], "was_taken_live": True,
                    "rewired_decision": d["decision"], "reasons": d["reason_codes"], "class": cls})
    blocked = [r for r in out if r["class"] == "BLOCKED_BY_REWIRE"]
    return {"trades": out, "n": len(out), "would_block": len(blocked),
            "summary": f"{len(blocked)}/{len(out)} historical trades would be BLOCKED by the rewired gate"}
