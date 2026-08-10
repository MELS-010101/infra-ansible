#!/usr/bin/env python3
"""Bridge: алерты Prometheus -> Telegram (stdlib only).

Каждую минуту (cron) опрашивает /api/v1/alerts, шлёт новые FIRING и RESOLVED.
Состояние — в /var/lib/infra-alerts/state.json (без спама дублями).
Без конфига/токена молча выходит 0. --test — проверочное сообщение.
"""
import json
import os
import sys
import time
import urllib.request

CONF = "/etc/infra-alerts.conf"
STATE_DIR = "/var/lib/infra-alerts"
STATE = os.path.join(STATE_DIR, "state.json")
PROM_ALERTS = "http://localhost:9090/api/v1/alerts"


def read_conf():
    cfg = {}
    if not os.path.exists(CONF):
        return cfg
    with open(CONF, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def tg(token, chat, text):
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    data = json.dumps({"chat_id": chat, "text": text}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r).get("ok", False)
        except Exception as exc:  # noqa: BLE001
            print("tg attempt %d failed: %s" % (attempt + 1, exc))
            time.sleep(5)
    return False


def get_alerts():
    with urllib.request.urlopen(PROM_ALERTS, timeout=10) as r:
        return json.load(r)["data"]["alerts"]


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sent": []}


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f)


def main():
    cfg = read_conf()
    if "--test" in sys.argv:
        if not cfg.get("TELEGRAM_TOKEN"):
            print("нет TELEGRAM_TOKEN в %s" % CONF)
            return 1
        ok = tg(cfg["TELEGRAM_TOKEN"], cfg.get("TELEGRAM_CHAT_ID"),
                "✅ infra-ansible: канал алертов работает")
        print("sent" if ok else "send failed")
        return 0 if ok else 1

    if not cfg.get("TELEGRAM_TOKEN") or not cfg.get("TELEGRAM_CHAT_ID"):
        return 0  # канал не настроен — не ошибка

    firing = {}
    for a in get_alerts():
        if a.get("state") == "firing":
            firing[a["labels"].get("alertname", "?")] = a

    st = load_state()
    sent = set(st.get("sent", []))
    changed = False

    for name, a in firing.items():
        if name not in sent:
            txt = "🚨 [%s] %s\n%s\ninstance: %s" % (
                a["labels"].get("severity", "warning").upper(), name,
                a["annotations"].get("summary", ""),
                a["labels"].get("instance", ""))
            if tg(cfg["TELEGRAM_TOKEN"], cfg["TELEGRAM_CHAT_ID"], txt):
                sent.add(name)
                changed = True

    for name in list(sent):
        if name not in firing:
            if tg(cfg["TELEGRAM_TOKEN"], cfg["TELEGRAM_CHAT_ID"],
                  "✅ RESOLVED: %s" % name):
                sent.discard(name)
                changed = True

    if changed:
        save_state({"sent": sorted(sent)})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("alert_notify error: %s" % exc)
        sys.exit(0)  # не роняем cron
