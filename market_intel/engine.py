"""engine.py -- PHASE 701 orchestrator. Observes markets + calendar, emits PRE-EVENT reports and
(post-release only) Opportunities, then routes each through the PHASE 601 pipeline.
STRUCTURAL GUARANTEE: this package imports no order function. It cannot place a trade.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from . import calendar_feed as cal
from .state import classify, MarketState
from .opportunity import Opportunity, OpportunityRegistry, from_release

INTEL_LOG = "registry/intel_log.jsonl"


def log(kind: str, payload: dict, path=INTEL_LOG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                            "kind": kind, **payload}, default=str) + "\n")


def pre_event_report(event, state: MarketState) -> dict:
    """Context BEFORE a release. Explicitly contains no direction and creates no opportunity."""
    r = {"event": event.name, "scheduled": event.scheduled, "impact": event.impact,
         "instrument": state.symbol, "positioning": {"trend": state.trend,
         "trend_strength": state.trend_strength, "volatility_regime": state.volatility_regime,
         "atr": state.atr}, "nearby_liquidity": {"prev_day_high": state.prev_day_high,
         "prev_day_low": state.prev_day_low, "prev_week_high": state.prev_week_high,
         "prev_week_low": state.prev_week_low, "opening_range": [state.opening_range_low,
         state.opening_range_high]}, "kill_zone": state.kill_zones or ["none"],
         "key_levels": {"vwap": state.vwap, "resistance": state.nearest_resistance,
         "support": state.nearest_support}, "structure": state.structure,
         "direction": None, "note": "PRE-EVENT context only. No opportunity until Actual is published."}
    log("pre_event_report", r)
    return r


def evaluate_through_pipeline(opp: Opportunity, registry=None, belief=None, guardian_ok=None) -> dict:
    """Route an opportunity through PHASE 601. Returns the decision. NEVER submits an order.
    Missing components => fail closed (RESEARCH_ONLY), never an implicit allow."""
    from execution_safety.gate import Signal, authorize
    from execution_safety.strategy_contract import StrategyRegistry
    reg = registry or StrategyRegistry()
    if belief is None or guardian_ok is None:
        opp.status = "REJECTED"
        opp.pipeline_log.append("FAIL_CLOSED: belief graph and/or guardian not wired")
        log("opportunity_rejected", {"id": opp.opportunity_id, "reason": "components_unwired"})
        return {"decision": "RESEARCH_ONLY", "reason_codes": ["COMPONENTS_UNWIRED"]}
    sig = Signal(signal_id=opp.opportunity_id, strategy_id="market_intel_event",
                 strategy_version="v1", symbol=opp.instrument, direction=opp.direction,
                 entry=opp.target_suggestion, stop_loss=opp.stop_suggestion)
    dec = authorize(sig, registry=reg, inference=lambda s: belief, guardian_ok=guardian_ok,
                    equity=0.0, account_is_demo=True, open_positions=[], shadow=True)
    opp.status = "SHADOW_ALLOWED" if dec["decision"] == "ALLOW_PAPER" else "REJECTED"
    opp.pipeline_log.append(f"{dec['decision']}: {dec['reason_codes']}")
    log("opportunity_evaluated", {"id": opp.opportunity_id, "decision": dec["decision"],
                                  "reasons": dec["reason_codes"]})
    return dec


def scan(symbol: str, m5, d1, events=None, now=None) -> dict:
    """One full intelligence cycle for one instrument."""
    st = classify(symbol, m5, d1, now=now)
    log("market_state", st.to_dict())
    events = events if events is not None else cal.load()
    up = cal.upcoming(events, now=now)
    pre = [pre_event_report(e, st) for e in up if e.impact == "high"]
    opps, R = [], OpportunityRegistry()
    for e in cal.just_released(events):
        o = from_release(e, st)
        if o:
            R.register(o); log("opportunity_generated", {"id": o.opportunity_id})
            opps.append(o)
    return {"state": st, "upcoming": up, "pre_event_reports": pre, "opportunities": opps}
