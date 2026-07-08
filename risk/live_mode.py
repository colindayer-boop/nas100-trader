"""Live mode risk governance.

Instantiates a RiskMode with the 'live' profile.
"""

from .risk_profile_loader import RiskMode, _load_profiles


class LiveMode(RiskMode):
    """Risk management for live personal account mode."""
    
    def __init__(self):
        profiles = _load_profiles()
        if 'live' not in profiles:
            raise ValueError("Live profile not found in risk_profiles.yaml")
        super().__init__(profiles['live'])


def get_instance() -> LiveMode:
    return LiveMode()


def get_risk_mode():
    return get_instance()
