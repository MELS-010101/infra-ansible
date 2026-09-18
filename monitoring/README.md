# Monitoring as Code: demo-app SLO

## Схема

    demo-app (default)                 ArgoCD (argocd)
      Service/rollout                    apps-root ──> monitoring-app ──> monitoring/*
           │ metrics /metrics                    └──> demo-app-app  ──> charts/demo-app
           ▼
    Prometheus (monitoring, retention 35d)
      ├─ ServiceMonitor demo-app
      ├─ PrometheusRule demo-app-slo: recording (slo:demo_app:*) + 5 alerts (team=demo)
      ▼
    Alertmanager (AlertmanagerConfig am-base)
      ├─ team=demo        -> Telegram (runbook + kubectl-диагностика, inhibit: TargetDown глушит error-rate)
      └─ всё остальное    -> null
      ▼
    CronJob slo-daily-report (09:00) -> Prometheus API -> Telegram:
      availability 24h/7d/30d, budget 30d, прогноз, сбои отправки, инциденты

## Файлы
| Файл | Назначение |
|---|---|
| prometheusrule-demo-app-slo.yaml | recording rules + 5 алертов |
| alertmanagerconfig-am-base.yaml | роутинг, шаблон сообщения, inhibit |
| servicemonitor-demo-app.yaml | цель скрейпа demo-app |
| cronjob-slo-report.yaml + slo-report.py | ежедневный отчёт |
| configmap-grafana-slo-burn.yaml + templates/*.json | дашборд SLO/Burn |
| sealedsecret-telegram.yaml | токен бота (шифротекст) |
| runbooks/*.md | инструкции по каждому алерту |
| helm-values-monitoring.yaml (../helm) | values стека: retention 35d и т.д. |
| RESTORE.md | дрейфы, инциденты, восстановление |

## Правила контура
1. Всё изменение = коммит в main; ArgoCD применяет (selfHeal+prune).
2. Ручные kubectl-правки только как аварийные; фиксируются в RESTORE.md.
3. Секреты в git только как SealedSecret.
4. CI: ansible-lint, docker build, promtool check rules; cd-bot bump'ит тег образа.
