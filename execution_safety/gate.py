"""gate.py -- PHASE 601 Stages 4/6/9 core. The single fail-closed authorization pipeline. A signal
NEVER calls a broker. It calls authorize(); only if EVERY gate approves does an OrderIntent get
created (and in SHADOW mode even that places nothing). Missing information => BLOCK.

The eight requirements (all mandatory):
  1 registered strategy contract   2 frozen-version match   3 approved research trial
  4 inference decision ALLOW       5 Guardian approval       6 deterministic risk + volume
  7 broker-side stop present        8 audit trail (returned decision record)
A strong entry belief cannot override a failed risk/execution gate: any single failure => BLOCK.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict

DECISIONS = ["ALLOW_PAPER", "BLOCK", "SUSPEND", "RESEARCH_ONLY"]


@dataclass
class Signal:
    signal_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    direction: int                    # +1 long / -1 short
    entry: float
    stop_loss: float                  # MUST be present and broker-side
    take_profit: float | None = None


@dataclass
class OrderIntent:
    intent_id: str
    decision_id: str
    strategy_id: str
    strategy_version: str
    signal_id: str
    symbol: str
    direction: int
    entry_type: str
    requested_entry: float
    stop_loss: float
    take_profit: float | None
    risk_amount: float
    risk_fraction: float
    calculated_volume: float
    magic_number: int
    comment: str
    created_at: float


def _deterministic_volume(equity, risk_fraction, entry, stop, contract_value=1.0):
    dist = abs(entry - stop)
    if dist <= 0:
        return None
    return round(equity * risk_fraction / (dist * contract_value), 4)


def authorize(signal: Signal, *, registry, inference, guardian_ok: bool, equity: float,
              account_is_demo: bool, open_positions: list, now=None, shadow=True) -> dict:
    """Return a decision record. decision in DECISIONS. Creates an OrderIntent ONLY on ALLOW_PAPER.
    Fail closed on ANY missing/invalid input."""
    now = now or time.time()
    reasons, missing = [], []
    def block(code): reasons.append(code)

    # 1. registered contract
    c = registry.get(signal.strategy_id)
    if c is None:
        block("NO_CONTRACT"); missing.append("strategy_contract")
        return _decision(signal, "BLOCK", reasons, missing, now)

    # 2. status gate (demo needs PAPER_APPROVED; real needs LIVE_APPROVED)
    if account_is_demo and not c.may_trade_demo(): block("NOT_PAPER_APPROVED")
    if not account_is_demo and not c.may_trade_real(): block("NOT_LIVE_APPROVED")

    # 3. frozen version match
    if signal.strategy_version != c.version: block("VERSION_MISMATCH")

    # 4. approved research trial present
    if not c.approved_trial_ids: block("NO_APPROVED_TRIAL"); missing.append("approved_trial_ids")

    # 5. symbol permitted
    if signal.symbol not in c.permitted_symbols: block("SYMBOL_NOT_PERMITTED")

    # 6. broker-side stop present + plausible
    if signal.stop_loss is None or signal.stop_loss <= 0: block("MISSING_STOP"); missing.append("stop_loss")
    else:
        dist = abs(signal.entry - signal.stop_loss)
        if dist <= 0: block("STOP_DISTANCE_ZERO")
        if dist / max(signal.entry, 1e-9) > 0.15: block("STOP_DISTANCE_IMPLAUSIBLE")  # >15% => suspect (the BTC bug)

    # 7. position / pyramiding limits
    same = [p for p in open_positions if p.get("symbol") == signal.symbol]
    if same and not c.pyramiding_allowed: block("PYRAMIDING_BLOCKED")
    if len(open_positions) >= c.maximum_concurrent_positions > 0 and not same:
        block("MAX_CONCURRENT_POSITIONS")

    # 8. risk within contract
    rf = c.maximum_risk_per_trade
    if rf <= 0: block("NO_RISK_BUDGET")
    vol = _deterministic_volume(equity, rf, signal.entry, signal.stop_loss or 0)
    if vol is None or vol <= 0: block("VOLUME_UNCOMPUTABLE"); missing.append("volume")

    # 9. inference decision (predictive + expectancy + drawdown + prop beliefs, separately)
    infd = inference(signal) if callable(inference) else inference
    if infd != "ALLOW_PAPER": block(f"INFERENCE_{infd}")

    # 10. Guardian final veto
    if not guardian_ok: block("GUARDIAN_VETO")

    if reasons:
        return _decision(signal, "BLOCK", reasons, missing, now)

    # ALL gates passed -> create the intent (shadow: record only, place nothing)
    dec = _decision(signal, "ALLOW_PAPER", ["ALL_GATES_PASSED"], [], now)
    dec["order_intent"] = asdict(OrderIntent(
        intent_id=f"OI-{signal.signal_id}", decision_id=dec["decision_id"],
        strategy_id=signal.strategy_id, strategy_version=signal.strategy_version,
        signal_id=signal.signal_id, symbol=signal.symbol, direction=signal.direction,
        entry_type="market", requested_entry=signal.entry, stop_loss=signal.stop_loss,
        take_profit=signal.take_profit, risk_amount=round(equity * rf, 2), risk_fraction=rf,
        calculated_volume=vol, magic_number=770001,
        comment=f"{signal.strategy_id}:{signal.strategy_version}", created_at=now))
    dec["shadow"] = shadow          # in shadow mode the executor must NOT submit this
    return dec


def _decision(signal, decision, reasons, missing, now):
    return {"decision_id": f"D-{signal.signal_id}-{int(now)}", "timestamp": now,
            "strategy_id": signal.strategy_id, "strategy_version": signal.strategy_version,
            "signal_id": signal.signal_id, "instrument": signal.symbol,
            "direction": signal.direction, "decision": decision,
            "reason_codes": reasons, "missing_evidence": missing,
            "expires_at": now + 60, "allow_trade": decision == "ALLOW_PAPER"}
