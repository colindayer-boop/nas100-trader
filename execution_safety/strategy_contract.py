"""strategy_contract.py -- PHASE 601 Stage 2. A strategy may not trade unless a frozen, approved
StrategyContract exists for it. No existing strategy is auto-approved. Fail closed: unknown => no trade.
"""
from __future__ import annotations
import glob, json, os
from dataclasses import dataclass, field, asdict

STATUSES = ["RESEARCH_ONLY", "DISCOVERY", "NEEDS_REPLICATION",
            "PAPER_APPROVED", "LIVE_APPROVED", "SUSPENDED", "RETIRED"]
CONTRACT_DIR = "strategy_contracts"


@dataclass
class StrategyContract:
    strategy_id: str
    strategy_name: str
    strategy_family: str
    version: str                       # frozen code version this contract authorizes
    code_commit: str
    status: str = "RESEARCH_ONLY"      # conservative default -- nothing trades by default
    approved_trial_ids: list = field(default_factory=list)
    dataset_fingerprint: str = ""
    feature_version: str = ""
    model_version: str = ""
    permitted_symbols: list = field(default_factory=list)
    permitted_timeframes: list = field(default_factory=list)
    permitted_sessions: list = field(default_factory=list)
    entry_function: str = ""
    exit_function: str = ""
    stop_function: str = ""
    position_sizing_function: str = ""
    maximum_risk_per_trade: float = 0.0
    maximum_symbol_exposure: float = 0.0
    maximum_portfolio_exposure: float = 0.0
    maximum_concurrent_positions: int = 0
    pyramiding_allowed: bool = False
    maximum_entries_per_symbol: int = 1
    cost_model: str = ""
    expected_trade_frequency: str = ""
    validation_start: str = ""
    validation_end: str = ""
    approval_timestamp: str = ""
    approval_actor: str = ""
    expiration_timestamp: str = ""

    def __post_init__(self):
        assert self.status in STATUSES, f"bad status {self.status}"

    def may_trade_demo(self) -> bool:
        return self.status == "PAPER_APPROVED"

    def may_trade_real(self) -> bool:
        return self.status == "LIVE_APPROVED"


class StrategyRegistry:
    """Loads contracts from strategy_contracts/*.json. Absence => fail closed."""
    def __init__(self, path=CONTRACT_DIR):
        self.path = path
        self.contracts: dict[str, StrategyContract] = {}
        self.load()

    def load(self):
        for f in glob.glob(os.path.join(self.path, "*.json")):
            d = json.load(open(f))
            self.contracts[d["strategy_id"]] = StrategyContract(**d)

    def get(self, strategy_id: str) -> StrategyContract | None:
        return self.contracts.get(strategy_id)      # None => caller must fail closed

    def save(self, c: StrategyContract):
        os.makedirs(self.path, exist_ok=True)
        json.dump(asdict(c), open(os.path.join(self.path, f"{c.strategy_id}.json"), "w"), indent=1)
        self.contracts[c.strategy_id] = c
