# Восстановление мониторинга demo-app

Порядок применения:
1. Вставить токен бота в secret-telegram-TEMPLATE.yaml и: kubectl apply -f secret-telegram-TEMPLATE.yaml
2. kubectl apply -f servicemonitor-demo-app.yaml
3. kubectl apply -f prometheusrule-demo-app-slo.yaml
4. kubectl apply -f alertmanagerconfig-am-base.yaml

ДВА КРИТИЧЕСКИХ патча (без них алерты молчат):
  kubectl patch prometheus kube-prometheus-stack-prometheus -n monitoring --type=merge -p '{"spec":{"ruleSelector":{},"ruleNamespaceSelector":{}}}'
  kubectl patch alertmanager kube-prometheus-stack-alertmanager -n monitoring --type=merge -p '{"spec":{"alertmanagerConfiguration":{"name":"am-base"}}}'

Грабли, на которые мы наступили (чтобы не повторять):
- up==0 молчит, если поды исчезли совсем (цель пропадает из discovery). Для 'приложение исчезло' нужно absent(up{...}).
- Поды demo-app воскрешает Rollout/demo-app: ронять надо сам rollout, а не ReplicaSet.
- AlertmanagerConfig по умолчанию лишь ДОБАВОК к базовому конфигy (receiver null). Базовым он становится только через spec.alertmanagerConfiguration.name.
- Экспортированные из кластера yaml НЕЛЬЗЯ коммитить как есть: вырезай status/, metadata.resourceVersion, metadata.uid, metadata.creationTimestamp, иначе apply падает с 'the object has been modified'.
- Дашборд SLO/Burn: правим monitoring/grafana-slo-burn-dashboard.json, затем регенерируем манифест:
  kubectl create configmap slo-burn-dashboard -n monitoring --from-file=slo-burn-dashboard.json=monitoring/grafana-slo-burn-dashboard.json --dry-run=client -o yaml | kubectl label --local --dry-run=client -o yaml -f - grafana_dashboard=1 > monitoring/configmap-slo-burn-dashboard.yaml
  kubectl apply -f monitoring/configmap-slo-burn-dashboard.yaml
- Prometheus CR patched live: spec.serviceMonitorSelector={} (было release=monitoring). После любого helm upgrade повторить:
  kubectl patch prometheus kube-prometheus-stack-prometheus -n monitoring --type=merge -p '{"spec":{"serviceMonitorSelector":{}}}'
- node-exporter отключён live-патчем DaemonSet (nodeSelector-заглушка; причина: CreateContainerError в WSL). Вернуть: убрать nodeSelector или helm upgrade с nodeExporter.enabled=true
- helm release kube-prometheus-stack: status=failed (upgrade оборвался по сети). Values для повторного upgrade: helm/helm-values-monitoring.yaml; команда: helm upgrade kube-prometheus-stack kube-prometheus-stack -n monitoring --version 10.1.1 --reuse-values -f helm/helm-values-monitoring.yaml
