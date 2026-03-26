# Структура Проекта

Русскоязычная annotated-версия структуры репозитория `Gym__Data` с пояснением по каждой папке.

## Общая идея

Проект разделён на несколько независимых слоёв:

- `workouts/` — исходные и производные данные тренировок
- `ingestion/` — загрузка и валидация данных
- `sql/` — детерминированная инициализация БД
- `backend/` — API и слой чтения данных
- `docs/` — документация по архитектуре и запуску
- `scripts/` — утилиты для локальной проверки и smoke-test
- `data/` — резерв под будущие выгрузки и служебные артефакты

## Структура

```text
Gym__Data/
|-- .env.example
|-- .gitignore
|-- compose.yaml
|-- README.md
|-- project_structure.md
|-- project_structure_ru.md
|-- backend/
|-- data/
|-- docs/
|-- ingestion/
|-- scripts/
|-- sql/
`-- workouts/
```

## Пояснение По Корню

### `backend/`

Бэкенд-сервис проекта. Здесь находится API, конфигурация приложения, доступ к PostgreSQL и ClickHouse, а также сервисный слой, который отделяет HTTP-роуты от SQL-запросов.

Структура:

- `backend/app/` — основной Python-код backend-сервиса
- `backend/Dockerfile` — контейнеризация backend
- `backend/pyproject.toml` — зависимости и packaging backend

### `data/`

Резервная папка под будущие производные данные, временные экспорты, snapshots, выгрузки для аналитики и прочие non-source артефакты. На текущем этапе почти не используется, но заложена как extension point.

### `docs/`

Документация по проекту. Здесь собраны описание архитектуры, data contract, runbook по Docker и roadmap развития платформы.

### `ingestion/`

Отдельный ingestion-слой. Его задача:

- читать `workouts/workouts/*.json`
- валидировать структуру
- разворачивать nested JSON в реляционные строки
- загружать RAW-слой в PostgreSQL
- пересобирать MART-слой в ClickHouse

### `scripts/`

Вспомогательные PowerShell-скрипты для локальной эксплуатации проекта:

- проверка, что нужные порты свободны
- минимальный smoke-check после запуска контейнеров

### `sql/`

SQL-инициализация баз данных. Разделено по движкам и по порядку запуска скриптов.

### `workouts/`

Папка с датасетом тренировок. Это главный domain-data слой текущего этапа. Здесь лежит source of truth, схема JSON и уже подготовленный flat-слой.

## Детализация Папок

### `backend/app/`

Главный пакет backend-приложения.

#### `backend/app/api/`

HTTP/API слой. Содержит маршрутизацию и регистрацию endpoint-ов.

#### `backend/app/api/routes/`

Конкретные API-роуты:

- `health.py` — health endpoints
- `workouts.py` — чтение workout-данных из RAW
- `exercises.py` — чтение exercise dimension/aggregates
- `summary.py` — аналитическая summary из ClickHouse

#### `backend/app/core/`

Базовая конфигурация backend-сервиса. Сейчас здесь хранится настройка окружения и app settings.

#### `backend/app/db/`

Доступ к базам данных:

- клиент для PostgreSQL
- клиент для ClickHouse

Это инфраструктурный слой, который изолирует детали подключения от API и сервисов.

#### `backend/app/domain/`

Заготовка bounded contexts. Это важно для будущего роста платформы без превращения проекта в один большой монолит.

Содержимое:

- `workouts/` — текущий основной контекст тренировок
- `exercises/` — текущий контекст упражнений
- `analytics/` — текущий аналитический контекст
- `identity/` — будущая auth/session/roles зона
- `clubs/` — будущая мультитенантность клубов
- `trainers/` — будущий контекст тренеров
- `clients/` — будущий контекст клиентов
- `memberships/` — будущие абонементы и подписки
- `payments/` — будущие платежи и биллинг
- `attendance/` — будущая посещаемость
- `programs/` — будущие планы и тренировочные программы

#### `backend/app/services/`

Прикладной слой backend. Здесь живёт логика чтения и подготовки ответа:

- работа с health status
- выборка workouts
- выборка exercises
- сборка summary
- сериализация типов из БД в JSON-friendly формат

### `data/README.md`

Короткое пояснение, зачем существует `data/` и как она будет использоваться позже.

### `docs/`

Документационные артефакты проекта:

- `PROJECT_OVERVIEW.md` — что это за проект и как устроен stage 1
- `DATA_CONTRACT.md` — контракт данных и бизнес-правила
- `RUNBOOK_DOCKER.md` — как запускать и проверять систему
- `ROADMAP.md` — куда расширять платформу дальше

### `ingestion/gym_data_ingestion/`

Основной пакет ingestion-сервиса.

#### `ingestion/gym_data_ingestion/cli/`

Точка входа для ingestion job. Сейчас через CLI запускается полный цикл `load-all`.

#### `ingestion/gym_data_ingestion/loaders/`

Слой загрузки в целевые системы:

- `postgres.py` — загрузка RAW-слоя и логов ingestion run
- `clickhouse.py` — пересборка аналитических MART-таблиц

#### `ingestion/gym_data_ingestion/validation/`

Валидация входных workout JSON по схеме и по правилам data contract.

#### `ingestion/gym_data_ingestion/models.py`

Модели и flattening-логика. Здесь nested workout JSON преобразуется в набор строк для таблиц:

- workouts
- exercise_instances
- sets
- cardio_segments
- recovery_events
- exercise_dictionary

#### `ingestion/gym_data_ingestion/settings.py`

Конфигурация ingestion через переменные окружения.

### `scripts/`

#### `scripts/check_ports.ps1`

Проверяет, что host-порты, выбранные для Docker Compose, не заняты.

#### `scripts/smoke_check.ps1`

Минимальная end-to-end проверка:

- health endpoint
- workouts endpoint
- exercises endpoint
- summary endpoint

### `sql/`

Разделено по целевым хранилищам.

#### `sql/postgres/`

SQL для PostgreSQL RAW и operational layer.

##### `sql/postgres/init/`

Скрипты, которые применяются в фиксированном порядке:

- `00_schemas.sql` — создание схем
- `01_raw_tables.sql` — RAW-таблицы тренировок
- `02_ops_tables.sql` — operational таблицы ingestion run
- `03_indexes.sql` — индексы для чтения

#### `sql/clickhouse/`

SQL для аналитического слоя.

##### `sql/clickhouse/init/`

Скрипты инициализации ClickHouse:

- `00_database.sql` — создание аналитической БД
- `01_mart_tables.sql` — MART-таблицы и аналитические views

### `workouts/`

Главная data-domain папка текущего этапа.

#### `workouts/workouts/`

Исходные JSON-файлы тренировок. Это source of truth.

Один файл = одна тренировка или одна тренировочная сессия.

#### `workouts/flat/`

Производный плоский слой в формате `jsonl`. Нужен как дополнительный аналитический/экспортный слой, но не является главным источником правды для ingestion stage 1.

Файлы:

- `workouts.jsonl`
- `exercise_instances.jsonl`
- `sets.jsonl`
- `cardio_segments.jsonl`
- `recovery_events.jsonl`
- `exercise_dictionary.jsonl`

#### `workouts/schema/`

JSON Schema для workout-документов.

#### `workouts/index.json`

Индекс по датасету. Может использоваться для навигации и быстрых ссылок на тренировки.

#### `workouts/manifest.json`

Метаданные по выгрузке:

- количество тренировок
- количество detailed/summary workouts
- объёмы плоских слоёв
- дополнительные заметки по данным

#### `workouts/README.md`

Локальное описание структуры workout-датасета и инженерных правил его использования.

## Роль Ключевых Корневых Файлов

### `.env.example`

Пример переменных окружения для запуска проекта без риска затереть реальный `.env`.

### `.gitignore`

Правила исключения служебных файлов из git.

### `compose.yaml`

Главная точка запуска всей системы через Docker Compose.

### `README.md`

Краткая входная точка в проект: что это, как запустить и где лежат docs.

### `project_structure.md`

Краткая англоязычная tree-структура репозитория.

### `project_structure_ru.md`

Эта русскоязычная annotated-версия структуры.

## Как Читать Эту Архитектуру

Если смотреть сверху вниз, то логика проекта такая:

1. Источник данных лежит в `workouts/workouts/`
2. `ingestion/` валидирует и загружает эти данные
3. `sql/postgres/` и `sql/clickhouse/` задают целевые структуры хранения
4. `backend/` читает RAW и MART по назначению
5. `docs/` и `scripts/` помогают безопасно запускать и расширять систему

Это хороший фундамент для следующего этапа, где уже можно наращивать:

- detail endpoints
- richer analytics
- auth/roles
- clubs/trainers/clients
- memberships/payments
- attendance
- будущий UI и mobile surfaces
