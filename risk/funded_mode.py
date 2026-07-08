"""Funded mode risk governance.

Instantiates a RiskMode with the 'funded' profile.
"""

from .risk_profile_loader import RiskMode, _load_profiles


class FundedMode(RiskMode):
    """Risk management for funded account mode."""
    
    def __init__(self):
        profiles = _load_profiles()
        if 'funded' not in profiles:
            raise ValueError("Funded profile not found in risk_profiles.yaml")
        super().__init__(profiles['funded'])


def get_instance() -> FundedMode:
    return FundedMode()


def get_risk_mode():
    return get_instance()
