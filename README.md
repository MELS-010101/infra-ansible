# infra-ansible — Production-ready автоматизация инфраструктуры на Ansible

Комплексный проект конфигурационного менеджмента, демонстрирующий развёртывание и
обслуживание серверной инфраструктуры по best practices: подготовка ОС, стек
**Nginx + MariaDB + Docker**, наблюдаемость через **Prometheus-экспортеры** и
автоматические **бэкапы с ротацией**. Код написан идемпотентно, с упором на
безопасность (Ansible Vault, `no_log`, принцип минимальных привилегий) и готов к
переносу в CI/CD.

Проект покрывает четыре направления одним прогоном:

1. **Server Baseline** — апдейты, админ-юзер с ключом, hardening SSH, UFW, автопатчи.
2. **Configuration Management** — Nginx + PHP-FPM, MariaDB, Docker Engine.
3. **Observability** — Node Exporter (метрики ОС) + MySQLd Exporter (метрики СУБД).
4. **Maintenance** — ежедневные дампы БД, шифрование архивов, ротация, обработка ошибок.

---

## Стек

| Компонент | Назначение |
|---|---|
| **Ansible** (>= 2.14) | Конфигурационный менеджер, agentless-модель |
| **MariaDB** | Реляционная СУБД |
| **Nginx + PHP-FPM** | Веб-сервер и обработчик PHP (LEMP) |
| **Docker Engine** | Контейнерный рантайм из официального репозитория |
| **Prometheus Node Exporter** | Метрики ОС (CPU/RAM/disk/net) |
| **Prometheus MySQLd Exporter** | Метрики СУБД (соединения, репликация) |
| **Ansible Vault** | Шифрование секретов в репозитории |
| **UFW / fail2ban** | Хостовой файрвол и защита от брута |

Внешние коллекции (ставятся из `requirements.yml`): `community.mysql`, `community.docker`.

---

## Структура каталогов

```
infra-ansible/
├── ansible.cfg                 # настройки ansible (инвентарь, роли, вьюлты)
├── requirements.yml            # зависимости: внешние коллекции
├── .gitignore                  # .vault_pass и служебные файлы НЕ коммитятся
├── .vault_pass                 # ключ от Vault — ЛОКАЛЬНО, вне git
├── inventory/
│   ├── inventory.ini           # хосты и группы [web] [db]
│   └── group_vars/
│       ├── all.yml             # общие переменные (админ-юзер, SSH-ключ)
│       ├── web.yml             # переменные веб-слоя (имя сайта, порт, PHP)
│       ├── db.yml              # переменные СУБД + пул пользователей
│       └── vault.yml           # СЕКРЕТЫ (зашифровано ansible-vault)
├── playbooks/
│   ├── site.yml                # полный прогон всех ролей по порядку
│   └── deploy.yml              # боевой релиз (без baseline и backup)
└── roles/
    ├── common/                 # Server Baseline
    ├── nginx/                  # веб-слой LEMP
    ├── db/                     # MariaDB + минимальные привилегии + hardening
    ├── docker/                 # Docker Engine
    ├── monitoring/             # экспортеры Prometheus
    └── backup/                 # бэкапы с ротацией (block/rescue/always)
```

Каждая роль следует стандартной структуре Ansible: `defaults/` (значения по
умолчанию), `tasks/` (задачи), `handlers/` (перезапуск сервисов), `templates/`
(Jinja2-шаблоны конфигов). Роль `backup` осознанно **не** содержит `handlers/` —
она не управляет долгоживущими сервисами.

---

## Архитектурные решения и безопасность

### Принцип минимальных привилегий в СУБД
В MariaDB **нет** отдельного root-пароля: управление идёт через плагин
`unix_socket` (модули логинятся через `login_unix_socket` под `become: yes`).
Прикладные пользователи создаются **одним циклом `loop`** из списка в
`group_vars/db.yml`, у каждого — свой набор прав:

- `app_user` — только операции с данными (`SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER`)
  и только в своей базе `app_db`, только со своего хоста.
- `backup_user` — только чтение и блокировка для дампа (`SELECT,LOCK TABLES,SHOW VIEW,TRIGGER`);
  `DROP`/`DELETE`/`INSERT` намеренно не выданы.
- `exporter` — только мониторинг (`PROCESS,REPLICATION CLIENT` + чтение `performance_schema`),
  без доступа к данным приложений.

### Секреты и логирование
- Пароли хранятся **только** в `inventory/group_vars/vault.yml`, зашифрованном
  `ansible-vault`. В открытом виде в репозитории их нет.
- В задачах, где создаются пользователи или раскладываются файлы с паролями
  (creds-файл бэкапа, env-файл экспортера), стоит **`no_log: true`** — секреты не
  попадают ни в вывод терминала, ни в diff, ни в логи CI.
- Пароли **не** вшиваются в тексты скриптов: они лежат в отдельных файлах с правами
  `0600`, которые скрипты читают в рантайме. Поэтому скрипты безопасны для git.

### Hardening, эквивалент `mysql_secure_installation`
Роль `db` воспроизводит `mysql_secure_installation` модулями под управляемыми
флагами: удаление анонимных пользователей, удаление тестовой БД и прав на неё,
запрет удалённого входа под root.

### Идемпотентность, шаблоны и обработчики
- Все конфиги (sshd, sudoers, nginx, my.cnf, daemon.json, systemd-юниты)
  развёртываются через `template` (Jinja2) и заполняются из Ansible Facts и
  переменных хоста — без хардкода.
- Конфиги с критичным синтаксисом пишутся с `validate` (например `sshd -t`,
  `visudo -cf`, `python3 -m json.tool`) — битый файл проверяется **до** записи и
  не ломает систему.
- Сервисы перезапускаются **только** при реальном изменении их конфигов через
  `handlers` (`notify`) — повторный прогон без правок ничего не дёргает.

### Отказоустойчивость бэкапов
Роль `backup` использует конструкцию **`block / rescue / always`**: тестовый прогон
скрипта при деплое ловит ошибку в `rescue`, пишет в лог и выводит алерт-заглушку,
но **не** роняет плейбук — выполнение продолжается. В проде `rescue` заменяется на
реальную отправку уведомления (mail / Telegram / PagerDuty).

### Обслуживание
- Docker: ротация логов контейнеров через `daemon.json` (защита от заполнения диска).
- Бэкапы: шифрование архивов `openssl` (aes-256-cbc, `-pbkdf2`) и ротация по сроку
  хранения (`find -mtime -delete`).
- ОС: только security-обновления через `unattended-upgrades`, синхронизация времени.

---

## Требования

**Управляющая машина** (где запускается ansible):
- Ansible >= 2.14, Python 3, доступ в интернет (для коллекций и пакетов).
- SSH-доступ к целевым хостам **или** запуск локально (`connection=local`).

**Целевые хосты:**
- Ubuntu 22.04/24.04 (amd64), `sudo` у ansible-пользователя.
- Для работы с MariaDB из ansible на целях нужен `python3-pymysql` — роль `db`
  ставит его сама.

> Заметка по окружению: если проект редактируется на Windows, а ansible стоит в
> WSL, файлы доступны через `/mnt/c/...` без копирования. Перед первым прогоном на
> NTFS рекомендуется включить metadata в WSL (см. раздел «Заметки по запуску»),
> иначе ansible выдаст предупреждение «world writable directory» и проигнорирует
> `ansible.cfg`.

---

## Быстрый старт

```bash
# 1. Установить внешние коллекции из requirements.yml
ansible-galaxy collection install -r requirements.yml

# 2. Подготовить ключ от Vault (ЛОКАЛЬНО, в git не коммитится — см. .gitignore)
printf '%s' 'YOUR_VAULT_PASSWORD' > .vault_pass

# 3. Отредактировать инвентарь и переменные под свою среду:
#    - inventory/inventory.ini        (хосты, группы)
#    - inventory/group_vars/all.yml   (админ-юзер, публичный SSH-ключ)
#    - inventory/group_vars/*.yml     (параметры слоёв)

# 4. Полный прогон (все роли по порядку)
ansible-playbook -i inventory/inventory.ini playbooks/site.yml \
  --vault-password-file .vault_pass
```

Пароль от Vault (`YOUR_VAULT_PASSWORD`) — это «ключ от сейфа»: храните его в
менеджере паролей (Bitwarden / KeePass / 1Password), а не в файлах и чатах. В CI
его передают как защищённую переменную окружения и генерируют `.vault_pass` на
лету — в репозитории ключа нет никогда.

---

## Примеры CLI

**Сухая проверка (dry-run)** — показать, что изменится, не трогая систему:
```bash
ansible-playbook -i inventory/inventory.ini playbooks/site.yml \
  --vault-password-file .vault_pass --check --diff
```
> Ограничение `--check`: модули, которые реально скачивают/распаковывают артефакты
> (например `unarchive` с `remote_src`, `get_url`), в dry-run могут отрабатывать
> не полностью — это известное поведение ansible, а не баг роли.

**Запуск одного слоя по тегу** (теги: `baseline`, `docker`, `web`, `db`,
`monitoring`, `backup`, а также `security`, `patching`):
```bash
ansible-playbook -i inventory/inventory.ini playbooks/site.yml \
  --vault-password-file .vault_pass --tags db

# несколько тегов
ansible-playbook ... --tags baseline,security

# пропустить слой (например, не трогать бэкапы при отладке)
ansible-playbook ... --skip-tags backup
```

**Ограничение по хостам** (только веб-слой, только один хост):
```bash
ansible-playbook ... --limit web
ansible-playbook ... --limit db-01
```

**Vault без файла** (интерактивный ввод пароля) — когда файла под рукой нет:
```bash
ansible-playbook -i inventory/inventory.ini playbooks/site.yml --ask-vault-pass
```

**Vault в CI** (пароль из защищённой переменной окружения):
```bash
printf '%s' "$VAULT_PASSWORD" > .vault_pass
ansible-playbook -i inventory/inventory.ini playbooks/site.yml \
  --vault-password-file .vault_pass
rm -f .vault_pass
```

**Боевой релиз** (без первичной подготовки ОС и без бэкапов — только приложение):
```bash
ansible-playbook -i inventory/inventory.ini playbooks/deploy.yml \
  --vault-password-file .vault_pass
```

**Работа с зашифрованным файлом:**
```bash
ansible-vault view    --vault-password-file .vault_pass inventory/group_vars/vault.yml
ansible-vault edit    --vault-password-file .vault_pass inventory/group_vars/vault.yml
ansible-vault rekey   --vault-password-file .vault_pass inventory/group_vars/vault.yml
```

---

## Что проверить после прогона

На целевых хостах:

```bash
# Сервисы подняты
systemctl status nginx php*-fpm mariadb docker node_exporter mysqld_exporter

# Метрики ОС доступны (порт 9100)
curl -s http://localhost:9100/metrics | head

# Метрики СУБД доступны на db-хосте (порт 9101)
curl -s http://localhost:9101/metrics | head

# Пользователи СУБД и их права (войти под root через сокет)
sudo mysql -e "SELECT user,host FROM mysql.user;"

# Бэкап снялся и зашифрован
ls -lh /var/backups/mysql/
cat /var/log/db_backup.log

# Файрвол
sudo ufw status verbose
```

---

## Идемпотентность

Повторный прогон `site.yml` без изменений в переменных не должен вносить правок:
задачи помечаются `ok`, обработчики не срабатывают, сервисы не перезапускаются.
Это проверяется вторым запуском подряд — хороший тест корректности роли.

---

## Лицензия

MIT — используйте и адаптируйте свободно.

## Автор

**MELS** — проект подготовлен как демонстрация навыков системного администрирования
и конфигурационного менеджмента (путь в DevOps).