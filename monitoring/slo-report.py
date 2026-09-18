import json, os, urllib.request, urllib.parse

PROM = "http://kube-prometheus-stack-prometheus.monitoring.svc:9090"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]

def q(expr):
    url = PROM + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    with urllib.request.urlopen(url, timeout=30) as r:
        res = json.load(r)["data"]["result"]
    return float(res[0]["value"][1]) if res else None

def avail(window):
    err = q('sum(increase(http_requests_total{job="demo-app", status=~"5.."}[%s])) or vector(0)' % window)
    tot = q('sum(increase(http_requests_total{job="demo-app"}[%s]))' % window)
    if tot is None or tot == 0:
        return None
    return 100.0 - (err / tot) * 100.0

a24, a7, a30 = avail("24h"), avail("7d"), avail("30d")
budget = q("slo:demo_app:budget_remaining_percent30d")
amfail = q('sum(increase(alertmanager_notification_failures_total[24h])) or vector(0)')
burn6 = q('slo:demo_app:burn_rate6h')
if budget is None or burn6 is None or burn6 <= 0.05:
    forecast = 'бюджет не расходуется (burn ~0)'
else:
    d = budget / burn6 * 0.3
    forecast = ('~%.0f дн. до исчерпания бюджета' % d) if d <= 30 else '>30 дн. (расход минимальный)'

url = PROM + "/api/v1/query?" + urllib.parse.urlencode({
    "query": 'count by (alertname)(count_over_time(ALERTS_FOR_STATE{alertname=~"TargetDown|HighErrorRate|SLOBreach|ErrorBudgetBurn.*"}[24h]))'})
with urllib.request.urlopen(url, timeout=30) as r:
    inc = json.load(r)["data"]["result"]
inc_lines = "\n".join("  - %s: %d раз(а)" % (i["metric"]["alertname"], int(float(i["value"][1]))) for i in inc) or "  - нет"

def fmt(v):
    return "n/a" if v is None else "%.3f%%" % v

msg = ("<b>📊 Ежедневный SLO-отчёт: demo-app</b>\n"
       "Доступность 24ч: %s\n"
       "Доступность 7д: %s\n"
       "Доступность 30д: %s\n"
       "Error budget (30д) осталось: %s\nПрогноз: %s\nСбоев отправки алертов (24ч): %d\n"
       "Инциденты за 24ч:\n%s" % (fmt(a24), fmt(a7), fmt(a30), fmt(budget), forecast, int(amfail or 0), inc_lines))

req = urllib.request.Request(
    "https://api.telegram.org/bot%s/sendMessage" % TOKEN,
    data=urllib.parse.urlencode({"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}).encode())
with urllib.request.urlopen(req, timeout=30) as r:
    print(json.load(r))
