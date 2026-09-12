# infra-ansible — автоматизация инфраструктуры на Ansible


Портфолийный проект конфигурационного менеджмента: production-подобный стенд
по best practices — подготовка ОС, стек **Nginx + PHP-FPM + MySQL/MariaDB** (LEMP),
runtime **Docker**, полная **наблюдаемость** (Node Exporter + Prometheus + Grafana:
дашборд и алерт-правила из кода, уведомления в Telegram), **шифрованные бэкапы
с ротацией и отказоустойчивостью**, **security-hardening** (fail2ban,
least-privilege, эквивалент mysql_secure_installation), секреты в
**Ansible Vault**, **CI на GitHub Actions** и **Python-приёмка**, которая после
каждого прогона доказывает, что стенд реально здоров.

Одним прогоном покрываются восемь направлений:

1. **Server Baseline** — апдейты, админ-юзер с ключом, SSH, UFW, автопатчи безопасности, fail2ban.
2. **Configuration Management** — Nginx + PHP-FPM 8.1, СУБД (MySQL/MariaDB, автоопределение), Docker Engine с ротацией логов.
3. **Security** — hardening СУБД, прикладной пользователь с минимальными привилегиями, раздельные учётки.
4. **Observability** — Node Exporter (:9100), MySQLd Exporter (:9101), Prometheus (:9090) с алерт-правилами, Grafana (:3000) + provisioned-дашборд.
5. **Alerting** — боевые алерты (MySQLDown / InstanceDown / DiskAlmostFull) + доставка в Telegram через bridge на Python.
6. **Maintenance** — ежедневные шифрованные дампы всех баз (+ дамп при загрузке), ротация 7 дней, лог, алерты, `block/rescue/always`.
7. **Acceptance** — Python-скрипт (stdlib) проверяет сервисы, HTTP, метрики, алерт-правила и свежесть бэкапа; плейбук падает, если стенд нездоров.
8. **CI** — ansible-lint + syntax-check + compile-check Python на каждый push/PR.

---

## Terraform (контейнерный слой)

Контейнерная часть стенда описана как IaC в `terraform/`: Terraform собирает образ из **того же Dockerfile**, что использует Ansible, и поднимает `demo-app-tf` на :8081.

```bash
cd terraform
terraform init && terraform apply -auto-approve
curl localhost:8081/
```

## Remote state (MinIO)

Стейт Terraform хранится в S3-совместимом хранилище: локально — MinIO (бакет `terraform-state`), в проде — реальный S3 + DynamoDB для блокировок.

```bash
bash scripts/bootstrap-minio.sh
cd terraform && terraform init -migrate-state   # одноразовая миграция
```

Консоль MinIO: http://localhost:9001 (minioadmin/minioadmin).

## Как это выглядит

![Grafana LEMP Overview](screenshots/grafana-lemp-overview.png)
*Grafana, дашборд LEMP Overview: MySQL up, CPU, RAM, Disk, Network, MySQL connections — всё provisioned из кода*

![Prometheus: node load](screenshots/prometheus-node-load1.png)
*Prometheus: load1 по ядрам — пики во время прогонов плейбука и приёмки*

![Prometheus: network & MySQL](screenshots/prometheus-network-mysql.png)
*Prometheus: сетевой трафик хоста и MySQL-метрики (connections, queries, buffers)*

![Telegram alert demo](screenshots/telegram-alert-demo.jpg)
*Боевой алерт в Telegram: stop mysql → 🚨 CRITICAL MySQLDown → start mysql → ✅ RESOLVED*
