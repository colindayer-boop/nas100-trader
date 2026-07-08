"""Risk profile loader for mode-based risk governance.

Loads risk profiles from config/risk_profiles.yaml and selects the active
profile based on:
  1. risk_mode in [risk] section of config.ini (if present)
  2. RISK_MODE environment variable
  3. Default to 'live' if neither is set.

Provides a function to get the effective risk scale (broker.RISK_SCALE * risk_multiplier)
for position sizing, applying the selected mode's risk multiplier.
"""

import os
import yaml
import configparser
from pathlib import Path
from typing import Dict, Any, Optional

# Paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
PROFILES_FILE = CONFIG_DIR / "risk_profiles.yaml"
CONFIG_INI = Path(__file__).parent.parent / "config.ini"

# Cache for loaded profiles and active profile name
_profiles_cache: dict = None
_profile_mtime: float = 0.0
_active_profile_name: str = None
_active_profile: dict = None
_active_profile_mtime: float = 0.0


def _load_profiles() -> dict:
    """Load profiles from YAML file, with caching based on file modification time."""
    global _profiles_cache, _profile_mtime
    if not PROFILES_FILE.is_file():
        raise FileNotFoundError(f"Risk profiles file not found: {PROFILES_FILE}")
    
    mtime = PROFILES_FILE.stat().st_mtime
    if _profiles_cache is not None and mtime == _profile_mtime:
        return _profiles_cache
    
    with open(PROFILES_FILE, 'r') as f:
        data = yaml.safe_load(f)
    
    # Resolve inheritance: each profile inherits from *default if present
    if 'default' in data:
        default = data['default']
        for key, profile in list(data.items()):
            if key == 'default':
                continue
            merged = dict(default)  # shallow copy
            merged.update(profile)
            data[key] = merged
        # Remove the default entry from the returned dict (we don't want to return it as a profile)
        data.pop('default', None)
    
    _profiles_cache = data
    _profile_mtime = mtime
    return data


def _get_active_profile_name() -> str:
    """Determine which profile to use."""
    global _active_profile_name
    # Return cached if still valid (we could check config.ini mtime, but simple)
    if _active_profile_name is not None:
        return _active_profile_name
    
    # 1. Check config.ini for risk_mode in [risk] section
    if CONFIG_INI.is_file():
        parser = configparser.ConfigParser()
        try:
            parser.read(CONFIG_INI)
            if 'risk' in parser and 'risk_mode' in parser['risk']:
                mode = parser['risk']['risk_mode'].strip().lower()
                if mode:
                    _active_profile_name = mode
                    return mode
        except Exception as e:
            # Silently ignore and fall back to env var
            pass
    
    # 2. Check environment variable
    mode = os.getenv('RISK_MODE', '').strip().lower()
    if mode:
        _active_profile_name = mode
        return mode
    
    # 3. Default to 'live'
    _active_profile_name = 'live'
    return 'live'


def _get_active_profile() -> dict:
    """Return the active profile dictionary, caching based on profile mtime."""
    global _active_profile, _active_profile_mtime
    profiles = _load_profiles()
    name = _get_active_profile_name()
    if name not in profiles:
        raise ValueError(f"Unknown risk mode '{name}'. Available: {list(profiles.keys())}")
    
    # If we have cached this profile and its mtime hasn't changed, return it
    # For simplicity, we rely on profile mtime (same as _profile_mtime)
    if _active_profile is not None and _active_profile_mtime == _profile_mtime:
        return _active_profile
    
    _active_profile = profiles[name]
    _active_profile_mtime = _profile_mtime
    return _active_profile


def get_effective_risk_scale(broker_risk_scale: float) -> float:
    """
    Return the effective risk scale for position sizing:
        effective = broker_risk_scale * risk_multiplier
    where broker_risk_scale already includes the DD-throttle adjustment.
    
    This function should be called wherever position size is calculated,
    replacing direct use of broker.RISK_SCALE with this value.
    
    Args:
        broker_risk_scale: The broker's RISK_SCALE after DD-throttle had been applied.
    
    Returns:
        The risk scale to use in position sizing calculations.
    """
    profile = _get_active_profile()
    multiplier = float(profile.get("risk_multiplier", 1.0))
    # Note: reduced_risk_mode is not applied here; it could be incorporated later
    # as an additional multiplicative factor if desired.
    return broker_risk_scale * multiplier


def get_profile_names() -> list:
    """Return list of available profile names."""
    return list(_load_profiles().keys())


def reload_profiles():
    """Clear the cache to force reload on next call."""
    global _profiles_cache, _profile_mtime, _active_profile, _active_profile_mtime, _active_profile_name
    _profiles_cache = None
    _profile_mtime = 0.0
    _active_profile = None
    _active_profile_mtime = 0.0
    _active_profile_name = None
