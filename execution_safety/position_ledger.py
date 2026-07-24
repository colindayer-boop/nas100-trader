"""position_ledger.py -- PHASE 601 Stage 8. One immutable, append-only ledger that joins:
trial -> contract -> inference decision -> order intent -> broker position. Every open broker
position must answer "why does this exist?". A broker position whose (magic, comment) has no ledger
entry is an ORPHAN_POSITION => alert, block all new orders, never assume ownership, require human
classification. Fail closed.
"""
from __future__ import annotations
import json, os, time
from dataclasses import dataclass, asdict, field

LEDGER = "registry/position_ledger.jsonl"


@dataclass
class LedgerEntry:
    intent_id: str
    trial_ids: list
    strategy_id: str
    strategy_version: str
    decision_id: str
    symbol: str
    magic: int
    comment: str
    created_at: float
    broker_ticket: int | None = None
    status: str = "AUTHORIZED"          # AUTHORIZED -> FILLED -> CLOSED
    history: list = field(default_factory=list)


class PositionLedger:
    def __init__(self, path=LEDGER):
        self.path = path
        self.entries: dict[str, LedgerEntry] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            for line in open(self.path):
                d = json.loads(line)
                self.entries[d["intent_id"]] = LedgerEntry(**d)

    def _append(self, e: LedgerEntry):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a") as f:                 # append-only => immutable audit trail
            f.write(json.dumps(asdict(e)) + "\n")

    def record_intent(self, intent: dict, trial_ids: list, decision_id: str) -> LedgerEntry:
        e = LedgerEntry(intent_id=intent["intent_id"], trial_ids=trial_ids,
                        strategy_id=intent["strategy_id"], strategy_version=intent["strategy_version"],
                        decision_id=decision_id, symbol=intent["symbol"], magic=intent["magic_number"],
                        comment=intent["comment"], created_at=intent["created_at"])
        self.entries[e.intent_id] = e; self._append(e)
        return e

    def is_ours(self, magic: int, comment: str) -> bool:
        return any(e.magic == magic and e.comment == comment for e in self.entries.values())


def classify_broker_positions(positions, ledger: PositionLedger, our_magic: int) -> dict:
    """Any broker position not traceable to a ledger entry is an ORPHAN => block everything."""
    orphans = []
    for p in positions:
        magic = getattr(p, "magic", None); comment = getattr(p, "comment", "")
        if magic == our_magic and ledger.is_ours(magic, comment):
            continue
        orphans.append({"symbol": getattr(p, "symbol", "?"), "magic": magic, "comment": comment})
    return {"orphans": orphans, "block_all_orders": bool(orphans),
            "policy": "ORPHAN_POSITION: alert, block new orders, require human classification"
                      if orphans else "clean"}
