"""opportunity.py -- PHASE 701 Opportunity Registry. An Opportunity is EVIDENCE, not an order.
It must traverse: Belief Graph -> Inference -> Guardian -> Promotion -> Shadow -> Allocation ->
Order Intent. This module imports no broker functions and cannot place a trade.
"""
from __future__ import annotations
import json, os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

REGISTRY = "registry/opportunities.jsonl"


@dataclass
class Opportunity:
    opportunity_id: str
    created_at: str
    instrument: str
    direction: int                    # +1 long / -1 short
    confidence: float                 # 0..1  (evidence weight, NOT a probability of profit)
    expected_volatility: float
    economic_reasoning: str
    technical_confirmation: list = field(default_factory=list)
    regime_compatibility: str = ""
    kill_zone_alignment: str = ""
    risk_estimate: float = 0.0
    stop_suggestion: float = 0.0
    target_suggestion: float = 0.0
    expected_holding_period: str = ""
    evidence_supporting: list = field(default_factory=list)
    evidence_contradicting: list = field(default_factory=list)
    source_event_id: str | None = None
    status: str = "REGISTERED"        # REGISTERED -> EVALUATED -> {SHADOW_ALLOWED|REJECTED}
    pipeline_log: list = field(default_factory=list)

    def to_dict(self): return asdict(self)


class OpportunityRegistry:
    def __init__(self, path=REGISTRY):
        self.path = path

    def register(self, o: Opportunity) -> Opportunity:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a") as f:                      # append-only audit trail
            f.write(json.dumps(o.to_dict()) + "\n")
        return o

    def all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        return [json.loads(l) for l in open(self.path) if l.strip()]


def from_release(event, state, hist_pctile: float | None = None) -> Opportunity | None:
    """Build an opportunity from a RELEASED economic event + current market state.
    Returns None if the event has no official Actual -- opportunities are never pre-generated."""
    if not event.released():
        return None
    s = event.surprise()
    if s is None:
        return None
    sp = event.surprise_pct() or 0.0

    # Directional implication: higher-than-forecast inflation/employment -> currency-positive.
    # This is a documented, falsifiable prior -- NOT a validated edge. Belief Graph decides its weight.
    hawkish = any(k in event.name.upper() for k in ["CPI", "PPI", "NFP", "EMPLOYMENT", "GDP",
                                                    "RETAIL", "ISM", "PMI", "RATE"])
    direction = (1 if s > 0 else -1) if hawkish else 0
    if direction == 0:
        return None

    supporting, contradicting = [], []
    (supporting if state.trend == ("up" if direction > 0 else "down") else contradicting).append(
        f"technical trend={state.trend}")
    if state.kill_zones:
        supporting.append(f"kill_zone={','.join(state.kill_zones)}")
    else:
        contradicting.append("outside kill zone (thinner liquidity)")
    if state.liquidity_sweep != "none":
        supporting.append(f"liquidity_sweep={state.liquidity_sweep}")
    if state.volatility_regime == "high":
        contradicting.append("high-volatility regime: wider stops, worse fills")

    conf = min(1.0, abs(sp) * 2)                       # bigger surprise -> more evidence weight
    conf *= (1.0 if state.kill_zones else 0.7)
    risk = max(state.atr * 1.5, 1e-9)
    stop = state.price - direction * risk
    target = state.price + direction * risk * 2

    return Opportunity(
        opportunity_id=f"OPP-{event.event_id}-{state.symbol}",
        created_at=datetime.now(timezone.utc).isoformat(),
        instrument=state.symbol, direction=direction, confidence=round(conf, 3),
        expected_volatility=round(state.atr, 5),
        economic_reasoning=(f"{event.name}: actual {event.actual} vs forecast {event.forecast} "
                            f"(surprise {s:+.4g}, {sp:+.1%})"
                            + (f", historical percentile {hist_pctile:.0%}" if hist_pctile is not None else "")),
        technical_confirmation=[f"structure={state.structure}", f"fvg={state.fvg}",
                                f"order_block={state.order_block}", f"vwap_dist={state.dist_vwap_pct:+.4f}"],
        regime_compatibility=f"trend={state.trend}/vol={state.volatility_regime}",
        kill_zone_alignment=",".join(state.kill_zones) or "none",
        risk_estimate=round(risk, 5), stop_suggestion=round(stop, 5), target_suggestion=round(target, 5),
        expected_holding_period="intraday-to-2d (event reaction)",
        evidence_supporting=supporting, evidence_contradicting=contradicting,
        source_event_id=event.event_id)
