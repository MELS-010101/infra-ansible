#!/usr/bin/env python3
"""Acceptance-проверки стенда infra-ansible.

Выходит с кодом 1, если что-то нездорово — плейбук падает, CI/прогон краснеет.
Только стандартная библиотека Python.
"""
import glob
import os
import subprocess
import sys
import time
import urllib.request

FAILS = []


def check(name, ok, detail=""):
    print("[{}] {}{}".format("OK  " if ok else "FAIL", name, " — " + detail if detail else ""))
    if not ok:
        FAILS.append(name)


def http(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(errors="ignore")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def svc(name):
    for _ in range(3):
        if subprocess.run(["systemctl", "is-active", name],
                          capture_output=True, text=True).returncode == 0:
            return True
        time.sleep(2)
    return False


# 1) Сервисы
for s in ["nginx", "docker", "cron", "fail2ban", "prometheus",
          "grafana-server", "prometheus-mysqld-exporter", "node_exporter"]:
    check("service " + s, svc(s))
check("service mysql|mariadb", svc("mysql") or svc("mariadb"))

# 2) HTTP-контур
st, _ = http("http://localhost/")
check("http :80 -> 200", st == 200)
st, body = http("http://localhost:9101/metrics")
check("mysqld_exporter mysql_up 1", st == 200 and "mysql_up 1" in body)
st, _ = http("http://localhost:9090/-/healthy")
check("prometheus healthy", st == 200)
st, _ = http("http://localhost:3000/api/health")
check("grafana health", st == 200)

# 3) Свежесть бэкапа (< 26 часов)
files = glob.glob("/var/backups/mysql/all-*.sql.gz.enc")
if files:
    newest = max(files, key=os.path.getmtime)
    age_h = (time.time() - os.path.getmtime(newest)) / 3600
    check("backup fresh < 26h", age_h < 26, "{:.1f}h, files={}".format(age_h, len(files)))
else:
    check("backup fresh < 26h", False, "нет шифрованных дампов")

print()
if FAILS:
    print("ACCEPTANCE FAILED ({}): {}".format(len(FAILS), ", ".join(FAILS)))
    sys.exit(1)
print("ACCEPTANCE PASSED")
