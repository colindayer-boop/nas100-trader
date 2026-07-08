"""Mode-based risk governance (challenge / funded / live).

This package layers ON TOP of the existing risk engine in live_trader.py
(DD-throttle, kill-switch). It does NOT change strategy entry logic or any
validated STOP/RR parameters. It only scales sizing and gates *new* entries.
"""
