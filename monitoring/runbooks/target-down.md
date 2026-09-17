# Runbook: TargetDown (demo-app)

## Описание
Prometheus не видит ни одной живой цели demo-app. Приложение полностью недоступно.

## Диагностика
1. Поды и их статус:
    kubectl get pods -n default -l app=demo-app
2. События владельца (Rollout/Deployment):
    kubectl describe rollout demo-app -n default
    kubectl get events -n default --sort-by=.lastTimestamp | tail -20
3. Рестарты и причины ожидания контейнеров:
    kubectl get pods -n default -l app=demo-app -o wide
4. Логи (если поды живы):
    kubectl logs -n default -l app=demo-app --tail=50
5. Кто управляет подами (owner):
    kubectl get rs -n default -l app=demo-app -o jsonpath='{range .items[*]}{.metadata.name}{" owners: "}{range .metadata.ownerReferences[*]}{.kind}/{.name}{" "}{end}{"\n"}{end}'
6. Статус ArgoCD-приложения:
    kubectl get application demo-app -n argocd

## Частые причины
- Rollout масштабирован в 0 вручную или через GitOps
- CrashLoopBackOff / OOMKilled: смотреть рестарты и limits
- ImagePullBackOff: тег образа или доступ к registry
- Пробы liveness/readiness не проходят
- ArgoCD selfHeal вернул нежелательное состояние

## Действия
1. Плановое отключение — игнорировать алерт
2. CrashLoop — логи пода, последний коммит в demo-app
3. OOMKilled — поднять limits в манифесте demo-app (git!)
4. ImagePull — проверить тег и секреты registry
5. Ничего не помогло — эскалация в канал @mels_alerts_2026_bot
