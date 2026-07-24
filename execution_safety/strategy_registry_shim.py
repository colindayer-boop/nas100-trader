from .strategy_contract import StrategyRegistry
class Reg(StrategyRegistry):
    def __init__(self, contracts): self.contracts = {c.strategy_id: c for c in contracts}
