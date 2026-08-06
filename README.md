# infra-ansible — автоматизация инфраструктуры на Ansible

Портфолийный проект конфигурационного менеджмента: production-подобный стенд
по best practices — подготовка ОС, стек **Nginx + PHP-FPM + MySQL/MariaDB** (LEMP),
runtime **Docker**, полная **наблюдаемость** (Node Exporter + Prometheus + Grafana),
**шифрованные бэкапы с ротацией и отказоустойчивостью**, секреты в **Ansible Vault**,
**CI на GitHub Actions**. Код идемпотентен: повторный прогон — `changed=0`.

Одним прогоном покрываются пять направлений:

1. **Server Baseline** — апдейты, админ-юзер с ключом, SSH, UFW, автопатчи безопасности.
2. **Configuration Management** — Nginx + PHP-FPM 8.1, СУБД (MySQL/MariaDB, автоопределение), Docker Engine.
3. **Observability** — Node Exporter (:9100), MySQLd Exporter (:9101), Prometheus (:9090), Grafana (:3000).
4. **Maintenance** — ежедневные шифрованные дампы всех баз, ротация 7 дней, лог, алерты, `block/rescue/always`.
5. **CI** — ansible-lint + syntax-check на каждый push/PR.

---

## Стек

| Компонент | Назначение |
|---|---|
| **Ansible** (>= 2.14) | конфигурационный менеджер, agentless |
| **MySQL / MariaDB** | СУБД; flavor определяется автоматически по dpkg |
| **Nginx + PHP-FPM 8.1** | веб-слой LEMP |
| **Docker Engine** | docker-ce, если уже установлен; иначе docker.io (guard от конфликта) |
| **Prometheus Node Exporter** | метрики ОС, :9100 |
| **Prometheus MySQLd Exporter** | метрики СУБД, :9101 (нативный пакет + systemd drop-in) |
| **Prometheus Server** | сбор метрик, :9090; scrape-таргеты: prometheus/node/mysqld |
| **Grafana** | визуализация, :3000; datasource provisioned автоматически |
| **Ansible Vault** | шифрование секретов в репозитории |
| **UFW** | хостовой файрвол, default deny |

Внешние коллекции (`requirements.yml`): `community.mysql`, `community.general`.

---

## Структура каталогов

```
infra-ansible/
├── ansible.cfg                 # инвентарь, роли, путь к vault-паролю
├── requirements.yml            # внешние коллекции
├── .ansible-lint               # профиль lint для CI и локальной разработки
├── .github/workflows/ci.yml    # CI: syntax-check + ansible-lint
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
│   ├── site.yml                # полный прогон всех ролей по порядку (с тегами)
│   └── deploy.yml              # боевой релиз (без baseline и backup)
└── roles/
    ├── common/                 # Server Baseline
    ├── nginx/                  # веб-слой LEMP + статус-страница
    ├── db/                     # СУБД + пользователи + mysqld_exporter
    ├── docker/                 # Docker Engine (с guard'ом)
    ├── monitoring/             # node_exporter + Prometheus + Grafana
    └── backup/                 # шифрованные бэкапы, ротация, rescue-алерты
```

`.vault_pass` (ключ от vault) существует **только локально** и внесён в `.gitignore`.

---

## Архитектурные решения (реальные, из кода)

- **Автоопределение flavor СУБД.** Роль `db` смотрит `dpkg-query` и ставит/использует
  mysql или mariadb; сервисы, пакеты и клиенты выбираются соответственно.
- **Guard по Docker.** `docker.io` ставится, только если Docker совсем отсутствует,
  иначе конфликт с Docker CE (`containerd.io : Conflicts: containerd`).
- **Наблюдаемость без внешних реестров.** Docker Hub из сети хоста недоступен
  (`connection reset by peer`), поэтому: mysqld_exporter — нативный пакет
  `prometheus-mysqld-exporter` (порт и DSN — через systemd drop-in и env-файл),
  Prometheus — пакет из universe, Grafana — официальный `.deb` с dl.grafana.com
  (fallback, если пакета нет в apt). Наблюдаемость не зависит от Docker Hub.
- **Секреты со спецсимволами.** Пароль из vault с `#` и `!` в DSN уходит через
  `urlencode`, в backup-`.cnf` — в кавычках; задачи с секретами — с `no_log: true`;
  файлы с секретами — `0600/0640`.
- **Один хост в двух группах.** `localhost` состоит в `[web]` и `[db]`: получает оба
  набора group_vars, apt не ловит lock от двух «разных» хостов.
- **Handlers только по изменению.** Сервисы перезапускаются через `notify` лишь при
  реальной правке конфигов; повторный прогон — `changed=0`.
- **WSL + OneDrive.** Критичные файлы пишутся heredoc из WSL — защита от рассинхрона
  редактора; ansible запускается только из WSL.

---

## Безопасность

- Секреты — только в `inventory/group_vars/all/vault.yml` (зашифрован);
  `.vault_pass` в репозитории нет никогда.
- Пользователи СУБД раздельные: `exporter` — только мониторинг
  (`PROCESS, REPLICATION CLIENT, SELECT`); `backup` — права для полного дампа.
- Бэкапы шифруются `openssl aes-256-cbc -pbkdf2`; ключ `/etc/mysql-backup.key` (0600)
  в git не попадает; старые **незашифрованные** дампы удаляются после появления шифрованного.
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

---

## Примеры CLI

```bash
ansible-playbook playbooks/site.yml --check --diff        # dry-run
ansible-playbook playbooks/site.yml --tags db             # теги: baseline, docker, web, db, monitoring, backup
ansible-playbook playbooks/site.yml --skip-tags backup
ansible-playbook playbooks/site.yml --limit web
ansible-playbook playbooks/deploy.yml                     # боевой релиз
ansible-vault view inventory/group_vars/all/vault.yml
```

---

## Что проверить после прогона

```bash
systemctl status nginx php8.1-fpm docker cron
systemctl status mysql            # или mariadb — какой flavor встал
systemctl status prometheus-mysqld-exporter node_exporter prometheus grafana-server

curl -sI localhost | head -n 1                        # HTTP/1.1 200
curl -s localhost:9100/metrics | head                 # node
curl -s localhost:9101/metrics | grep '^mysql_up'     # mysql_up 1
curl -s localhost:9090/-/healthy                      # Prometheus is Healthy
curl -s localhost:3000/api/health                     # Grafana ok
curl -s 'localhost:9090/api/v1/targets' | grep -o '"health":"up"' | uniq -c   # 3 таргета up

ls -lh /var/backups/mysql                             # all-*.sql.gz.enc
tail -n 3 /var/log/db_backup.log                      # OK: ...
crontab -l | grep mysql-backup                        # 30 2 * * *
```

**Grafana:** `http://localhost:3000`, логин `admin`, пароль `admin`
(или задай `vault_grafana_admin_password` в vault; смена пароля —
`grafana-cli admin reset-admin-password 'new'`). Datasource Prometheus
подключён автоматически; для красивых дашбордов импортируй ID 1860 (Node Exporter).

**Восстановление БД из шифрованного бэкапа:**

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -pass file:/etc/mysql-backup.key \
  -in /var/backups/mysql/all-*.sql.gz.enc | zcat | mysql
```

**Telegram-алерты бэкапов (опционально):** создай `/etc/backup-alerts.conf`:

```bash
TELEGRAM_TOKEN=123456:AAA...
TELEGRAM_CHAT_ID=-100...
```

---

## CI

`.github/workflows/ci.yml` на каждый push/PR: `ansible-playbook --syntax-check`
+ `ansible-lint` (профиль `min`, осознанные skip — в `.ansible-lint`).
Реальный vault-ключ в CI не попадает (`.vault_pass` в gitignore, в CI — заглушка).

---

## Идемпотентность

Повторный прогон `site.yml` без правок в переменных: `failed=0 changed=0`,
сервисы не перезапускаются. Проверено повторным запуском.

---

## Roadmap (запланировано, в коде ещё нет)

- `app_user` с минимальными привилегиями на отдельную базу;
- hardening СУБД, эквивалент `mysql_secure_installation`;
- fail2ban; ротация логов Docker через `daemon.json`;
- provisioned-дашборды Grafana из кода;
- docker-compose-вариант observability для сред с доступным Docker Hub;
- Python-скрипт acceptance-проверок (порт/сервис/свежесть бэкапа) + шаг в CI.

---

## Лицензия

MIT — используйте и адаптируйте свободно.

## Автор

**MELS** — демонстрация навыков системного администрирования и конфигурационного
менеджмента (путь в DevOps).
