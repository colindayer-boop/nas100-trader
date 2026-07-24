"""broker_reconciliation.py -- PHASE 601 Stage 7. After an order is (hypothetically) submitted, the
broker's reported position MUST match the intent, and a broker-side stop MUST exist. A position
without its protective stop => CRITICAL: block all new entries, alert, attempt only the pre-authorized
protective modification. Never silently continue. A local trailing stop is NEVER the only protection.

This module places no orders. It reconciles an OrderIntent against a broker-position snapshot and
returns a state; the executor consumes that state.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class BrokerPosition:
    symbol: str
    volume: float
    sl: float
    tp: float | None
    magic: int
    comment: str


def reconcile(intent: dict, pos: BrokerPosition | None) -> dict:
    """Compare a filled position to the intent that authorized it. Fail closed on any mismatch."""
    crit, warn = [], []
    if pos is None:
        return {"state": "NO_FILL", "critical": [], "block_new_entries": False,
                "note": "no position reported yet; not an error unless expected"}
    if pos.sl is None or pos.sl <= 0:
        crit.append("MISSING_BROKER_STOP")                      # the BTC-class failure
    if abs(pos.volume - intent["calculated_volume"]) > 1e-6:
        warn.append(f"VOLUME_MISMATCH intent={intent['calculated_volume']} broker={pos.volume}")
    if pos.magic != intent["magic_number"]:
        crit.append("MAGIC_MISMATCH")                           # not our position / wrong attribution
    if pos.comment != intent["comment"]:
        warn.append("COMMENT_MISMATCH")
    if pos.sl and intent["stop_loss"] and abs(pos.sl - intent["stop_loss"]) / intent["stop_loss"] > 0.001:
        warn.append(f"STOP_MISMATCH intent={intent['stop_loss']} broker={pos.sl}")
    state = "CRITICAL" if crit else ("DIVERGENT" if warn else "OK")
    return {"state": state, "critical": crit, "warnings": warn,
            "block_new_entries": bool(crit),
            "required_action": ("PROTECTIVE_STOP_MODIFICATION" if "MISSING_BROKER_STOP" in crit
                                else "HUMAN_REVIEW" if crit else "none")}


def protective_stop_monitor(positions: list[BrokerPosition], magic: int) -> dict:
    """Sweep all of our positions; any missing a broker-side stop => CRITICAL, block new entries."""
    naked = [p for p in positions if p.magic == magic and (p.sl is None or p.sl <= 0)]
    return {"naked_positions": [p.symbol for p in naked], "block_new_entries": bool(naked),
            "alert": "CRITICAL: position without broker-side stop" if naked else None}
