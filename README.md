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

## Стек

| Компонент | Назначение |
|---|---|
| **Ansible** (>= 2.14) | конфигурационный менеджер, agentless |
| **MySQL / MariaDB** | СУБД; flavor определяется автоматически по dpkg |
| **Nginx + PHP-FPM 8.1** | веб-слой LEMP |
| **Docker Engine** | docker-ce, если уже установлен; иначе docker.io (guard от конфликта) |
| **Prometheus Node Exporter** | метрики ОС, :9100 (собственный юнит; пакетный отключён guard'ом) |
| **Prometheus MySQLd Exporter** | метрики СУБД, :9101 (нативный пакет + systemd drop-in) |
| **Prometheus Server** | сбор метрик, :9090; scrape-таргеты + rule_files с алертами |
| **Grafana** | визуализация, :3000; datasource и дашборд provisioned из кода |
| **alert_notify.py (Python)** | bridge: алерты Prometheus → Telegram (FIRING/RESOLVED, ретраи, дедупликация) |
| **fail2ban** | защита SSH от брутфорса (jail sshd, 5 попыток, бан 10 минут) |
| **infra_check.py (Python)** | приёмка стенда: сервисы, HTTP, `mysql_up`, алерт-правила, свежесть бэкапа; только stdlib |
| **Ansible Vault** | шифрование секретов в репозитории |
| **UFW** | хостовой файрвол, default deny |

Внешние коллекции (`requirements.yml`): `community.mysql`, `community.general`, `ansible.posix`.

---

## Структура каталогов

```
infra-ansible/
├── ansible.cfg                 # инвентарь, роли, путь к vault-паролю
├── requirements.yml            # внешние коллекции
├── .ansible-lint               # профиль lint для CI и локальной разработки
├── .github/workflows/ci.yml    # CI: syntax-check + ansible-lint + py_compile
├── .gitignore                  # .vault_pass и служебные файлы НЕ коммитятся
├── inventory/
│   ├── inventory.ini           # [web] и [db] = localhost (connection=local)
│   └── group_vars/
│       ├── all/
│       │   ├── main.yml        # общие переменные (админ-юзер, SSH-ключ)
│       │   └── vault.yml       # СЕКРЕТЫ (зашифровано ansible-vault)
│       ├── web.yml             # переменные веб-слоя (php_fpm_version и т.п.)
│       └── db.yml              # переменные СУБД
├── playbooks/
│   ├── site.yml                # полный прогон всех ролей + acceptance (с тегами)
│   └── deploy.yml              # боевой релиз (без baseline и backup)
└── roles/
    ├── common/                 # Server Baseline + fail2ban
    ├── nginx/                  # веб-слой LEMP + статус-страница
    ├── db/                     # СУБД + пользователи + hardening + mysqld_exporter
    ├── docker/                 # Docker Engine (guard) + ротация логов
    ├── monitoring/             # exporters + Prometheus (rules) + Grafana + Telegram bridge
    ├── backup/                 # шифрованные бэкапы, ротация, rescue-алерты, @reboot
    └── acceptance/             # Python-приёмка стенда (files/infra_check.py)
```

`.vault_pass` (ключ от vault) существует **только локально** и внесён в `.gitignore`.

---

## Архитектурные решения (реальные, из кода)

- **Автоопределение flavor СУБД.** Роль `db` смотрит `dpkg-query` и ставит/использует
  mysql или mariadb; сервисы, пакеты и клиенты выбираются соответственно.
- **Guard по Docker.** `docker.io` ставится, только если Docker совсем отсутствует,
  иначе конфликт с Docker CE (`containerd.io : Conflicts: containerd`).
- **Guard по порту 9100.** Debian-пакет `prometheus-node-exporter` занимает порт
  и роняет наш юнит в `bind: address already in use`; роль останавливает и
  отключает пакетный сервис **до** развёртывания собственного юнита.
- **Наблюдаемость без внешних реестров.** Docker Hub из сети хоста недоступен
  (`connection reset by peer`), поэтому: mysqld_exporter — нативный пакет
  `prometheus-mysqld-exporter` (порт и DSN — через systemd drop-in и env-файл),
  Prometheus — пакет из universe, Grafana — официальный `.deb` с dl.grafana.com
  (fallback, если пакета нет в apt). Наблюдаемость не зависит от Docker Hub.
- **Дашборд как код.** Grafana подхватывает datasource и дашборд LEMP Overview
  через provisioning-файлы и JSON из роли — без ручных кликов, на любом хосте.
- **Алертинг как код.** Prometheus грузит правила из `/etc/prometheus/rules/*.yml`:
  `MySQLDown` (mysql_up==0, 1м), `InstanceDown` (up==0, 2м), `DiskAlmostFull`
  (диск / > 85%, 5м). Приёмка проверяет загрузку правил через `/api/v1/rules`.
- **Алерты в Telegram.** Bridge `alert_notify.py` (stdlib) раз в минуту опрашивает
  `/api/v1/alerts`, шлёт новые FIRING и RESOLVED, дедуплицирует по файлу состояния,
  ретраит отправку при сетевых сбоях. Секреты (token/chat_id) — из vault в
  `/etc/infra-alerts.conf` (0600). Честное ограничение: в сетях, где
  `api.telegram.org` блокируется, доставка требует VPN; bridge не падает и
  дошлёт алерт, когда связность появляется.
- **Приёмка после каждого прогона.** Финальный play гоняет
  `/usr/local/bin/infra_check.py`: сервисы active (с ретраями против окна
  перезапуска), HTTP 200, `mysql_up 1`, алерт-правила загружены, бэкап свежее
  26 часов. Ненулевой код роняет плейбук — «зелёный RECAP» означает
  «стенд реально здоров», а не «задачи отработали».
- **Секреты со спецсимволами.** Все пароли — из vault (`vault_db_*`). DSN в
  env-файле — в кавычках и **без urlencode** (go-драйвер экспортера не
  декодирует `%XX`); в backup-`.cnf` — в кавычках; задачи с секретами —
  `no_log: true`; файлы с секретами — `0600/0640`.
- **Один хост в двух группах.** `localhost` состоит в `[web]` и `[db]`: получает оба
  набора group_vars, apt не ловит lock от двух «разных» хостов.
- **Handlers только по изменению.** Сервисы перезапускаются через `notify` лишь при
  реальной правке конфигов; повторный прогон — `changed=0`.
- **WSL + OneDrive.** Критичные файлы пишутся heredoc из WSL — защита от рассинхрона
  редактора; ansible запускается только из WSL.

---

## Безопасность

- Секреты — только в `inventory/group_vars/all/vault.yml` (зашифрован);
  `.vault_pass` в репозитории нет никогда; роли ссылаются на реальные имена
  секретов vault.
- **Раздельные учётки СУБД по принципу минимальных привилегий:**
  - `exporter` — только мониторинг (`PROCESS, REPLICATION CLIENT, SELECT`);
  - `backup` — права для полного дампа;
  - `app_user` — только `app_db` и только операции данных
    (`SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER`), видит в `SHOW DATABASES` лишь свою базу.
- **Hardening СУБД (эквивалент `mysql_secure_installation`):** удаление анонимных
  пользователей и test-базы, запрет удалённого входа под root (`root@%` absent).
- **fail2ban:** jail `sshd` (maxretry 5, бан 10 минут); в WSL гарантируется наличие
  `/var/log/auth.log` (без rsyslog).
- Бэкапы шифруются `openssl aes-256-cbc -pbkdf2`; ключ `/etc/mysql-backup.key` (0600)
  в git не попадает; старые **незашифрованные** дампы удаляются после появления
  шифрованного; cron: ежедневно 02:30 + `@reboot` (стенд мог быть выключен ночью).
- Docker: ротация логов контейнеров через `daemon.json` (10m × 3 файла, `validate`
  через `json.tool` до записи).
- UFW: default deny; разрешены SSH, HTTP/HTTPS и порты метрик.
- `unattended-upgrades` — только обновления безопасности.

---

## Быстрый старт

```bash
ansible-galaxy collection install -r requirements.yml
printf '%s' 'YOUR_VAULT_PASSWORD' > .vault_pass && chmod 600 .vault_pass
# правка под свою среду: inventory/inventory.ini, inventory/group_vars/*
ansible-playbook playbooks/site.yml --vault-password-file .vault_pass
```

Telegram-алерты (опционально): добавь в vault `vault_telegram_token` и
`vault_telegram_chat_id` — роль сама разложит их в `/etc/infra-alerts.conf`.

---

## Примеры CLI

```bash
ansible-playbook playbooks/site.yml --check --diff        # dry-run
ansible-playbook playbooks/site.yml --tags db             # теги: baseline, docker, web, db, monitoring, backup, acceptance
ansible-playbook playbooks/site.yml --skip-tags backup
ansible-playbook playbooks/site.yml --limit web
ansible-playbook playbooks/deploy.yml                     # боевой релиз
ansible-vault view inventory/group_vars/all/vault.yml
```

---

## Что проверить после прогона

```bash
systemctl status nginx php8.1-fpm docker cron fail2ban
systemctl status mysql            # или mariadb — какой flavor встал
systemctl status prometheus-mysqld-exporter node_exporter prometheus grafana-server

/usr/local/bin/infra_check.py     # ACCEPTANCE PASSED — стенд здоров
/usr/local/bin/alert_notify.py --test   # ✅-сообщение в Telegram (если настроен)

curl -sI localhost | head -n 1                        # HTTP/1.1 200
curl -s localhost:9100/metrics | head                 # node
curl -s localhost:9101/metrics | grep '^mysql_up'     # mysql_up 1
curl -s localhost:9090/-/healthy                      # Prometheus is Healthy
curl -s localhost:9090/api/v1/rules | grep -o '"name":"MySQLDown"'  # алерты загружены
curl -s localhost:3000/api/health                     # Grafana ok

sudo fail2ban-client status sshd                      # Jail list: sshd
sudo mysql -e "SELECT user,host FROM mysql.user;"     # app_user есть, root только localhost
MYSQL_PWD='<пароль app_user>' mysql -u app_user -h 127.0.0.1 -e "SHOW DATABASES;"  # только app_db

ls -lh /var/backups/mysql                             # all-*.sql.gz.enc
tail -n 3 /var/log/db_backup.log                      # OK: ...
crontab -l | grep -E 'mysql-backup|alert_notify'      # 30 2 * * * + @reboot +每分钟
```

**Grafana:** `http://localhost:3000`, логин `admin`, пароль `admin`
(или задай `vault_grafana_admin_password` в vault; смена пароля —
`grafana-cli admin reset-admin-password 'new'`). Дашборд **LEMP Overview**
(CPU/RAM/Disk/Network/MySQL) появляется автоматически из кода.

**Демо боевого алерта:** `systemctl stop mysql` → через ~1–2 минуты в Telegram
прилетит `🚨 [CRITICAL] MySQLDown` → `systemctl start mysql` → придёт
`✅ RESOLVED: MySQLDown`. Приёмка в это время валит плейбук — так и задумано.

**Восстановление БД из шифрованного бэкапа:**

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -pass file:/etc/mysql-backup.key \
  -in /var/backups/mysql/all-*.sql.gz.enc | zcat | mysql
```

---

## CI

`.github/workflows/ci.yml` на каждый push/PR: `ansible-playbook --syntax-check`
+ `ansible-lint` (профиль `min`, осознанные skip — в `.ansible-lint`)
+ `python -m py_compile` обоих Python-скриптов.
Реальный vault-ключ в CI не попадает (`.vault_pass` в gitignore, в CI — заглушка).

---

## Идемпотентность

Повторный прогон `site.yml` без правок в переменных: `failed=0 changed=0`,
сервисы не перезапускаются. Проверено повторным запуском.

---

## Roadmap (запланировано, в коде ещё нет)

- docker-compose-вариант observability для сред с доступным Docker Hub;
- вынос acceptance в отдельный шаг CI с артефактом-отчётом;
- Grafana notification policies поверх Telegram-bridge (дублирующий канал).

---

## Лицензия

MIT — используйте и адаптируйте свободно.

## Автор

**MELS** — демонстрация навыков системного администрирования и конфигурационного
менеджмента (путь в DevOps).