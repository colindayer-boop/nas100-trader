"""
setup_telegram.py — wire Telegram alerts in ONE command and prove they work.

    python setup_telegram.py <BOT_TOKEN> <CHAT_ID>

Writes [alerts] into config.ini next to this script (creates the file or
updates the section — safe to re-run), verifies the token with getMe, and
sends a test message to the chat so you see it on your phone immediately.
"""
import configparser
import os
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if len(sys.argv) != 3:
        print("usage: python setup_telegram.py <BOT_TOKEN> <CHAT_ID>")
        return 1
    token = sys.argv[1].strip()
    chat_id = sys.argv[2].strip().rstrip("-").strip()   # tolerate a trailing dash typo

    # 1. verify the token before writing anything
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
    if not (r.ok and r.json().get("ok")):
        print(f"TOKEN INVALID: {r.text[:200]}")
        print("Get a fresh one from @BotFather (/token) and re-run.")
        return 1
    bot_name = r.json()["result"].get("username", "?")
    print(f"token OK — bot @{bot_name}")

    # 2. write config.ini (create or update [alerts]; everything else untouched)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
    cfg = configparser.ConfigParser()
    cfg.read(path)
    if not cfg.has_section("alerts"):
        cfg.add_section("alerts")
    cfg.set("alerts", "telegram_token", token)
    cfg.set("alerts", "chat_id", chat_id)
    with open(path, "w") as f:
        cfg.write(f)
    print(f"config written: {path}")

    # 3. send the proof
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id,
                            "text": "nas100-trader alerts wired — signals, fills "
                                    "and session summaries will arrive here."},
                      timeout=15)
    if r.ok and r.json().get("ok"):
        print("TEST MESSAGE SENT — check your Telegram.")
        return 0
    print(f"send failed: {r.text[:200]}")
    print("If it says 'chat not found': open Telegram, send any message to "
          f"@{bot_name} first (bots can't message you until you start them), then re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
