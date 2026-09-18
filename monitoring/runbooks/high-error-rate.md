# HighErrorRate

5xx > 1% за 2 минуты (окно 5m).

## Шаги
1. Дашборд SLO / Burn Rate (localhost:3001) — подтвердить всплеск.
2. Последние деплои: `kubectl rollout history rollout/demo-app -n default`.
3. Деплой был за последние 30 минут -> откат: `kubectl rollout undo rollout/demo-app -n default`.
4. Деплоя не было -> логи: `kubectl logs -n default -l app=demo-app --tail=200 | grep -i error`.
5. Зависимости и события: `kubectl get events -n default --sort-by=.lastTimestamp | tail -20`.
6. Ошибки продолжаются -> масштабировать: `kubectl scale rollout demo-app -n default --replicas=5`.

## Эскалация
Одновременно горит ErrorBudgetBurnFast (x14.4) - реагировать немедленно.
