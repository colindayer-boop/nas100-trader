"""
alerts.py — Send fill/error/daily-summary notifications.

Priority order:
  1. Telegram  — if config.ini [alerts] has telegram_token + chat_id
  2. Email     — if config.ini [alerts] has smtp_host + smtp_user + smtp_pass + to_email
  3. Console   — always (fallback; never silently drops)
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText

import requests

from broker import load_config

logger = logging.getLogger("trader")
_cfg   = load_config("alerts")


_HEALTH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "logs", "alert_health.json")


def send(msg: str) -> bool:
    """Dispatch an alert through available channels; always prints to console.
    Returns True if a REMOTE channel delivered. Records delivery health so a silently
    broken channel (bad token / network down on the headless VPS) becomes DETECTABLE
    via alert_health() / status.py -- was: failures only printed and vanished."""
    print(f"[ALERT] {msg}")
    logger.info(f"ALERT {msg}")
    tg = _try_telegram(msg)   # True/False = attempted; None = not configured
    em = _try_email(msg)
    delivered = bool(tg or em)
    configured = (tg is not None) or (em is not None)
    _record_health(configured, delivered, msg)
    return delivered


def _record_health(configured: bool, delivered: bool, msg: str) -> None:
    """Persist last-success / consecutive-failure so absence of delivery is visible.
    Fail-safe: never raises (an alert path must not crash the trader)."""
    import json
    from datetime import datetime, timezone
    try:
        h = {}
        if os.path.exists(_HEALTH_PATH):
            with open(_HEALTH_PATH) as f:
                h = json.load(f)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        h["last_attempt"] = now
        h["configured"] = configured
        if delivered:
            h["last_success"] = now
            h["consecutive_failures"] = 0
            h["last_error"] = ""
        elif configured:
            h["consecutive_failures"] = int(h.get("consecutive_failures", 0)) + 1
            h["last_error"] = f"no remote channel delivered: {msg[:80]}"
        os.makedirs(os.path.dirname(_HEALTH_PATH), exist_ok=True)
        with open(_HEALTH_PATH, "w") as f:
            json.dump(h, f)
    except Exception as e:
        logger.warning(f"alert health record failed: {e}")


def alert_health() -> dict:
    """Read the persisted alert-delivery health (for status.py / daily_check)."""
    import json
    try:
        with open(_HEALTH_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def ping_watchdog(ok: bool = True) -> bool:
    """Opt-in dead-man's-switch heartbeat. Pings [watchdog] ping_url on each successful
    session; an EXTERNAL service (e.g. healthchecks.io) alarms if pings STOP -> detects
    a dead VPS/scheduler that no internal alert could report. No-op when unset. Fail-safe;
    logs only the error, NEVER the URL (it is a per-check secret)."""
    try:
        url = load_config("watchdog").get("ping_url", "").strip()
    except Exception:
        url = ""
    if not url or url.startswith("YOUR_"):
        return False
    try:
        requests.get(url if ok else url.rstrip("/") + "/fail", timeout=8)
        return True
    except Exception as e:
        logger.warning(f"watchdog ping failed: {e}")
        return False


def _try_telegram(msg: str) -> None:
    # .strip() removes stray spaces/newlines from pasted secrets (#1 cause of failures)
    token   = _cfg.get("telegram_token", "").strip()
    chat_id = _cfg.get("chat_id", "").strip()
    # chat_id sometimes pasted as "Id: 12345" — keep only the (signed) number
    if chat_id and not chat_id.lstrip("-").isdigit():
        chat_id = "".join(c for c in chat_id if c.isdigit() or c == "-")
    if not token or not chat_id or token.startswith("YOUR_"):
        print(f"[TELEGRAM] skipped — token set: {bool(token)}, chat_id set: {bool(chat_id)} "
              f"(check secrets TELEGRAM_TOKEN/CHAT_ID + workflow env)")
        return None
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10,
        )
        if resp.ok:
            print("[TELEGRAM] sent ✓")
            return True
        print(f"[TELEGRAM] FAILED: {resp.text}")
        logger.warning(f"Telegram alert failed: {resp.text}")
        return False
    except Exception as e:
        print(f"[TELEGRAM] error: {e}")
        logger.warning(f"Telegram alert error: {e}")
        return False


def _try_email(msg: str) -> None:
    host     = _cfg.get("smtp_host", "")
    user     = _cfg.get("smtp_user", "")
    password = _cfg.get("smtp_pass", "")
    to_addr  = _cfg.get("to_email", "")
    if not all([host, user, password, to_addr]) or host.startswith("YOUR_"):
        return None
    try:
        port = int(_cfg.get("smtp_port", 587))
        mime = MIMEText(msg)
        mime["Subject"] = f"[Trader] {msg[:60]}"
        mime["From"]    = user
        mime["To"]      = to_addr
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.ehlo(); s.starttls(); s.login(user, password)
            s.send_message(mime)
        return True
    except Exception as e:
        logger.warning(f"Email alert error: {e}")
        return False
