"""Challenge mode risk governance.

Instantiates a RiskMode with the 'challenge' profile.
"""

from .risk_profile_loader import RiskMode, get_active_profile, reload_profiles


class ChallengeMode(RiskMode):
    """Risk management for prop trading challenge mode."""
    
    def __init__(self):
        # Load the challenge profile directly to ensure we get the right one
        # Regardless of the active profile set elsewhere, this class always uses challenge.
        from .risk_profile_loader import _load_profiles
        profiles = _load_profiles()
        if 'challenge' not in profiles:
            raise ValueError("Challenge profile not found in risk_profiles.yaml")
        super().__init__(profiles['challenge'])


def get_instance() -> ChallengeMode:
    """Return a singleton-like instance (though we don't enforce singleton)."""
    return ChallengeMode()


# For backward compatibility, also provide a function that returns the risk mode object
def get_risk_mode():
    return get_instance()
