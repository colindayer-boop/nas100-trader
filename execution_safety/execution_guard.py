"""execution_guard.py -- PHASE 601 legacy-path retirement. The single fail-closed choke on order
submission. A broker may submit an ENTRY only if the authorized executor armed it with a valid gate
decision immediately beforehand. Legacy code (live_trader.py) never arms => every entry it attempts
raises ExecutionBlocked. Default state is BLOCKED; arming is one-shot (can't be replayed).

Usage (authorized executor only, AFTER authorize() returns ALLOW_PAPER):
    with armed(decision_id):
        broker.place_order(...)      # consume_or_block() inside place_order passes exactly once
Anything else calling place_order raises ExecutionBlocked.
"""
from __future__ import annotations
import threading
from contextlib import contextmanager

_local = threading.local()


class ExecutionBlocked(RuntimeError):
    pass


def arm(decision_id: str):
    if not decision_id:
        raise ExecutionBlocked("cannot arm with empty decision id")
    _local.token = decision_id


def disarm():
    _local.token = None


@contextmanager
def armed(decision_id: str):
    arm(decision_id)
    try:
        yield
    finally:
        disarm()


def consume_or_block(context: str = "") -> str:
    """Called at the broker order-send boundary. Raises unless armed; consumes the token (one-shot)."""
    tok = getattr(_local, "token", None)
    if not tok:
        raise ExecutionBlocked(
            f"UNAUTHORIZED_ORDER blocked ({context}). Direct/legacy order submission is retired; "
            "route through authorize() + the authorized executor. Fail closed.")
    _local.token = None            # one-shot: a decision authorizes exactly one submission
    return tok
