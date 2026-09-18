# infra-ansible: GitOps + Monitoring as Code

Учебно-продакшен стенд: полный жизненный цикл мониторинга demo-app в Kubernetes —
от метрик и SLO до алертов в Telegram с runbook и ежедневных отчётов.
Любое изменение = коммит в main; кластер применяет ArgoCD.

## Архитектура

    GitHub: infra-ansible
      argocd-apps/  monitoring/  charts/demo-app/  .github/
                    │ pull (selfHeal + prune)
                    ▼
      ArgoCD: apps-root (app-of-apps)
        ├─ monitoring  -> monitoring/*
        └─ demo-app    -> charts/demo-app
                    │
      ┌─────────────┼──────────────────────────────┐
      ▼             ▼                              ▼
    demo-app      Prometheus                   Alertmanager (am-base)
    rollout 3rep  retention 35d                team=demo  -> Telegram
    /metrics ───▶ SLO recording rules ───────▶ остальные  -> null
                  5 alerts team=demo           inhibit: TargetDown
      │                                        глушит error-rate
      ▼
    CronJob 09:00: SLO-отчёт ──▶ Telegram
    (availability 24h/7d/30d, budget, прогноз, инциденты)

## Структура репозитория

| Путь | Назначение |
|---|---|
| argocd-apps/ | Application'ы ArgoCD + apps-root (app-of-apps) |
| charts/demo-app/ | Helm-чарт приложения (rollout, hpa, ingress, dashboard) |
| monitoring/ | Monitoring as Code: правила, роутинг, отчёты, runbooks, README контура |
| helm/ | values стека kube-prometheus-stack (retention, селекторы) |
| .github/workflows/ | CI: lint, build, promtool; cd-bot bump тега |
| playbooks/, inventory/ | Ansible-часть курса |

## Дизайн мониторинга

SLO: 99% доступности, error budget 1%, окно 30 дней.
21 recording rule (окна 5m/30m/1h/6h/30d, burn rate, budget remaining).

Алерты команды (team=demo -> Telegram):

| Alert | Условие | for |
|---|---|---|
| HighErrorRate | 5xx > 1% (окно 5m) | 2m |
| SLOBreach | доступность 1h < 99% | 5m |
| TargetDown | нет ни одной цели demo-app | 10s |
| ErrorBudgetBurnFast | burn x14.4 (5m и 1h) | 5m |
| ErrorBudgetBurnSlow | burn x6 (30m и 6h) | 30m |

Каждое сообщение в Telegram: summary, description, ссылка на runbook,
kubectl-диагностика. RESOLVED приходят тоже.
Inhibit: TargetDown глушит HighErrorRate/SLOBreach того же team.
Всё без метки team=demo (кластерный шум) уходит в null-приёмник.

Ежедневный отчёт (CronJob 09:00): доступность 24ч/7д/30д, error budget,
прогноз дней до исчерпания бюджета, сбои отправки алертов, инциденты за 24ч.

## Правила GitOps

1. Любое изменение = коммит в main; ArgoCD применяет (selfHeal + prune).
2. Ручные kubectl/helm-правки только как аварийные; фиксируются в monitoring/RESTORE.md.
3. Секреты в git только как SealedSecret (controller v0.24.5).
4. CRD не обновляются через app sync (argo-rollouts: ignoreDifferences).

## Восстановление кластера (quick start)

    # 1. Стек мониторинга (helm, версия запинена)
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
      -n monitoring --create-namespace --version 10.1.1 \
      -f helm/helm-values-monitoring.yaml

    # 2. Контроллер SealedSecrets
    kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.5/controller.yaml

    # 3. Всё остальное ставит ArgoCD (app-of-apps)
    kubectl apply -f argocd-apps/root-apps.yaml
    # telegram-credentials восстановится сам из SealedSecret

## CI/CD

| Job | Назначение |
|---|---|
| ansible-lint + syntax check | валидация ansible-части |
| docker build + smoke test | сборка и запуск demo-app |
| push image to GHCR | публикация образа |
| bump image tag (cd-bot) | автообновление тега в values чарта |
| promtool-check | синтаксис Prometheus-правил на каждый push |

## Доступ к UI

    kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3001:80
    kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9096:9090


## Автозапуск Grafana (systemd)

Вместо ручного `kubectl port-forward` при каждой сессии — создаём systemd-сервис,
который автоматически поднимает туннель при старте WSL.

### Одноразовая настройка

    sudo tee /etc/systemd/system/grafana-tunnel.service > /dev/null <<'EOF'
    [Unit]
    Description=Port-forward Grafana 3001:80
    After=network.target

    [Service]
    Type=simple
    User=root
    Environment=KUBECONFIG=/root/.kube/config
    Environment=HOME=/root
    ExecStart=/usr/local/bin/kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3001:80
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    EOF

    sudo systemctl daemon-reload
    sudo systemctl enable grafana-tunnel.service
    sudo systemctl start grafana-tunnel.service

### Управление

    grafana-start    # запустить туннель
    grafana-stop     # остановить
    grafana-status   # посмотреть статус

### Проверка

После перезапуска WSL (`wsl --shutdown` в PowerShell) порт 3001 должен слушаться
автоматически: `ss -tln | grep 3001`.

Для Prometheus (порт 9096) создать аналогичный сервис `prometheus-tunnel.service`,
заменив имя и порт.


## Инциденты и уроки

Полный журнал: monitoring/RESTORE.md. Ключевые:
- repo-server CrashLoopBackOff (liveness timeout) -> rollout restart + профилактика в docs
- ServiceMonitor с двумя хозяевами (chart и monitoring) -> единственный владелец monitoring/
- SealedSecret "already exists and is not managed" -> пересоздание объекта
- гонка cd-bot с пушами -> pull --rebase в workflow
- promtool не понимает Kubernetes-обёртку -> извлечение spec.groups в CI
- YAML 1.1: голая "=" это тег value -> кавычки

## Стек

Kubernetes, ArgoCD, Argo Rollouts, Prometheus, Alertmanager, Grafana,
kube-state-metrics, SealedSecrets, Helm, GitHub Actions, Telegram Bot API, Ansible

---
Автор: MELS, учебный трек sysadmin -> devops.
