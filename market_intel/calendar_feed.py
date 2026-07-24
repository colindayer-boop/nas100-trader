"""calendar_feed.py -- PHASE 701 economic calendar. PLUGGABLE by design:
  1. MT5 built-in calendar (if the installed MetaTrader5 build exposes it)
  2. A user-supplied CSV  (market_intel/calendar.csv) -- export from any provider you're licensed for
  3. Empty (engine degrades to technical-only; never fabricates events)
No scraping: sites like Forex Factory publish data but their ToS restricts automated collection, so
the operator supplies the feed. This module NEVER invents an 'actual' value.
"""
from __future__ import annotations
import csv, os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta

CSV_PATH = "market_intel/calendar.csv"
HIGH_IMPACT = {"CPI", "CORE CPI", "PPI", "NFP", "NON-FARM", "FOMC", "ECB", "BOE", "GDP",
               "RETAIL SALES", "ISM", "PMI", "EMPLOYMENT", "INTEREST RATE", "CONSUMER CONFIDENCE",
               "UNEMPLOYMENT", "RATE DECISION"}


@dataclass
class Event:
    event_id: str
    name: str
    currency: str
    scheduled: str                 # ISO UTC
    impact: str                    # high | medium | low
    previous: float | None = None
    forecast: float | None = None
    actual: float | None = None    # None until officially released
    unit: str = ""
    source: str = ""

    # --- surprise maths: only valid once `actual` exists ---
    def released(self) -> bool:
        return self.actual is not None

    def surprise(self):
        if self.actual is None or self.forecast is None:
            return None
        return self.actual - self.forecast

    def surprise_pct(self):
        s = self.surprise()
        if s is None or not self.forecast:
            return None
        return s / abs(self.forecast)

    def to_dict(self): return asdict(self)


def _impact_of(name: str, given: str = "") -> str:
    if given:
        return given.lower()
    up = name.upper()
    return "high" if any(k in up for k in HIGH_IMPACT) else "medium"


def _f(x):
    try:
        return float(str(x).replace("%", "").replace("K", "").replace("M", "").strip())
    except Exception:
        return None


def from_mt5() -> list[Event]:
    """Use MT5's economic calendar if this build exposes it (not all do)."""
    try:
        import MetaTrader5 as mt5
        if not hasattr(mt5, "calendar_value_history"):
            return []
        now = datetime.now(timezone.utc)
        vals = mt5.calendar_value_history(now - timedelta(days=2), now + timedelta(days=7))
        out = []
        for v in vals or []:
            ev = mt5.calendar_event_by_id(v.event_id)
            if ev is None:
                continue
            out.append(Event(event_id=str(v.id), name=ev.name, currency=getattr(ev, "currency", ""),
                             scheduled=str(v.time), impact=_impact_of(ev.name),
                             previous=getattr(v, "prev_value", None),
                             forecast=getattr(v, "forecast_value", None),
                             actual=getattr(v, "actual_value", None), source="mt5"))
        return out
    except Exception:
        return []


def from_csv(path: str = CSV_PATH) -> list[Event]:
    """CSV columns: scheduled,name,currency,impact,previous,forecast,actual,unit"""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            out.append(Event(event_id=f"csv-{i}", name=row.get("name", "?"),
                             currency=row.get("currency", ""), scheduled=row.get("scheduled", ""),
                             impact=_impact_of(row.get("name", ""), row.get("impact", "")),
                             previous=_f(row.get("previous")), forecast=_f(row.get("forecast")),
                             actual=_f(row.get("actual")), unit=row.get("unit", ""), source="csv"))
    return out


def load() -> list[Event]:
    """MT5 first, then CSV. Never fabricates."""
    return from_mt5() or from_csv()


def upcoming(events: list[Event], now: datetime | None = None, hours=24) -> list[Event]:
    now = now or datetime.now(timezone.utc)
    out = []
    for e in events:
        try:
            t = datetime.fromisoformat(e.scheduled.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now <= t <= now + timedelta(hours=hours):
            out.append(e)
    return sorted(out, key=lambda x: x.scheduled)


def just_released(events: list[Event]) -> list[Event]:
    """Events whose official Actual now exists -> the ONLY ones allowed to create opportunities."""
    return [e for e in events if e.released()]
