# Gym__Data Startup Flow

Пошаговая схема запуска проекта `Gym__Data` от чистого старта до проверки UI и API.

Этот файл нужен как отдельная “карта запуска”:

- что запускать
- в каком порядке запускать
- зачем нужен каждый шаг
- какой результат ожидается после каждого шага

Основной сценарий рассчитан на запуск через Docker Compose.

## Step 0. Что должно быть готово заранее

Перед запуском проверь:

- установлен Docker Desktop или совместимый Docker Engine
- доступен `docker compose`
- проект открыт из корня репозитория `Gym_Data`
- JSON-источники уже лежат в:
  - `workouts/workouts/*.json`
  - `measurements/measurements/*.json`

Проверка:

```powershell
docker --version
docker compose version
```

Ожидаемый смысл шага:

- убедиться, что запуск не упрётся в отсутствующий Docker
- убедиться, что команды ниже будут работать без донастройки

## Step 0.1. Остановить предыдущий запуск Gym__Data

Если `Gym__Data` уже запускался раньше, перед новым запуском лучше остановить именно его контейнеры.

Команда:

```powershell
docker compose down
```

Что делает шаг:

- останавливает только контейнеры текущего Compose-проекта `Gym__Data`
- не трогает другие Docker-проекты, если они запущены отдельно
- очищает старое runtime-состояние сервисов перед новым стартом

Важно:

- эта команда не должна останавливать твой другой проект, если ты запускаешь её из корня `Gym__Data`
- `docker compose down` не удаляет volumes
- `docker compose down -v` используй только если хочешь полностью сбросить локальное состояние PostgreSQL и ClickHouse

## Step 1. Опционально создать `.env`

Если дефолтные настройки тебя устраивают, этот шаг можно пропустить.

Команда:

```powershell
Copy-Item .env.example .env
```

Что делает шаг:

- создаёт локальный файл окружения
- позволяет переопределить порты и runtime-настройки
- не меняет tracked-конфигурацию репозитория

Важно:

- не перезаписывай существующий `.env`, если в нём уже есть нужные тебе значения

Что можно настраивать через `.env`:

- `BACKEND_HOST_PORT`
- `POSTGRES_HOST_PORT`
- `CLICKHOUSE_HTTP_HOST_PORT`
- `CLICKHOUSE_NATIVE_HOST_PORT`
- `MEASUREMENT_RECOMMENDATION_CADENCE_DAYS`
- `DEFAULT_SUBJECT_PROFILE_ID`

## Step 2. Проверить порты на хосте

Команда:

```powershell
.\scripts\check_ports.ps1
```

Что делает шаг:

- проверяет, свободны ли host-порты, которые будут проброшены из контейнеров

Текущие дефолтные host ports:

- backend: `18080`
- PostgreSQL: `55432`
- ClickHouse HTTP: `18123`
- ClickHouse native: `19000`

Зачем это важно:

- проект специально использует не самые стандартные порты, чтобы не конфликтовать с уже занятыми локальными сервисами
- если порт занят, лучше поменять его в `.env` до старта, а не разбираться с упавшим Compose после

## Step 3. Поднять инфраструктуру и backend

Команда:

```powershell
docker compose up -d --build
```

Что делает шаг:

- собирает Docker images
- запускает:
  - `postgres`
  - `clickhouse`
  - `backend`
- применяет текущие Docker и Compose настройки проекта

Что должно получиться:

- контейнеры стартуют в фоне
- backend становится доступен на `http://localhost:18080`

Проверка:

```powershell
docker compose ps
```

Ожидаемый результат:

- `postgres` и `clickhouse` должны быть `healthy`
- `backend` должен быть `running` или перейти в `healthy`, если healthcheck уже успел выполниться

## Step 4. Загрузить данные в RAW и MART

Команда:

```powershell
docker compose --profile jobs run --rm --build ingestion
```

Что делает шаг:

- читает реальные source-of-truth JSON
- валидирует `workouts` и `measurements`
- применяет data-contract проверки
- загружает RAW слой в PostgreSQL
- перестраивает аналитические MART-слои в ClickHouse

Какие source domains участвуют:

- workouts
- measurements

Что должно получиться:

- PostgreSQL заполняется raw-данными
- ClickHouse получает актуальные marts
- в консоли появляется сводка по загруженным сущностям

Почему здесь используется `--build`:

- `docker compose up -d --build` поднимает основные сервисы
- но `ingestion` находится в profile `jobs` и не всегда пересобирается автоматически вместе с backend
- поэтому для надёжного запуска лучше сразу пересобирать job image именно в момент запуска ingestion

Это избавляет от ситуации, когда:

- backend уже новый
- source snapshot уже считается новым кодом
- а `ingestion` job всё ещё работает со старой логикой flattening/reconciliation

Пример ожидаемой логики результата:

- количество workouts
- количество exercise instances
- количество sets
- количество measurement sessions
- количество measurement values

## Step 5. Проверить согласованность source -> flat -> RAW

Команда:

```powershell
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile
```

Что делает шаг:

- сравнивает source JSON, derived `flat/*.jsonl` и таблицы PostgreSQL RAW
- ищет count mismatch, orphan rows, broken ordering, duplicate logical rows и другие нарушения контракта

Зачем это нужно:

- убедиться, что ingestion ничего не потерял
- убедиться, что derived слой не разошёлся с source-of-truth
- получить операционную проверку, пригодную для CI и smoke-check

Что считается успешным результатом:

- отчёт заканчивается `Status: PASS`
- команда завершается с exit code `0`

Важно как понимать `reconcile`:

- `reconcile` сам по себе ничего не перезагружает
- он только сверяет `source`, `flat` и `raw`
- поэтому перед `reconcile` нужно сначала убедиться, что данные уже были загружены актуальной версией ingestion

Правильная логика такая:

1. пересобрать и запустить `ingestion`
2. загрузить RAW и MART
3. только потом запускать `reconcile`

Именно поэтому в Step 4 используется:

```powershell
docker compose --profile jobs run --rm --build ingestion
```

## Step 6. Прогнать backend tests

Команда:

```powershell
docker compose run --rm --no-deps backend pytest
```

Что делает шаг:

- запускает API и service-level тесты backend
- проверяет endpoints, write/read contracts, profile workspace и UI shell availability

Зачем это нужно:

- подтвердить, что backend-контракт не сломан текущими изменениями
- убедиться, что profile-centric layer работает поверх существующего foundation

Успешный результат:

- все тесты проходят
- команда завершается без ошибок

## Step 7. Прогнать ingestion tests

Команда:

```powershell
docker compose --profile jobs run --rm --no-deps ingestion python -m pytest
```

Что делает шаг:

- запускает тесты ingestion и reconciliation
- проверяет flattening, validation, measurement contracts и другие data-core сценарии

Зачем это нужно:

- отдельно подтвердить корректность загрузочного контура
- убедиться, что изменения в source contracts не ломают pipeline

## Step 8. Открыть UI

Адрес:

```text
http://localhost:18080/ui/
```

Что делает шаг:

- открывает встроенный MVP control panel
- UI отдаётся самим backend, отдельный frontend-контейнер не нужен

Что должно быть видно:

- `Overview`
- `Measurements`
- `Progress`
- форма создания measurement session

Практический смысл:

- это минимальное рабочее profile-centric workspace
- можно смотреть latest measurements, recent workouts и body progress в одном месте

## Step 9. Проверить основные API вручную

Health:

```powershell
Invoke-RestMethod http://localhost:18080/api/health/
```

Profile overview:

```powershell
Invoke-RestMethod http://localhost:18080/api/profile/current/overview
```

Profile timeline:

```powershell
Invoke-RestMethod "http://localhost:18080/api/profile/current/timeline?limit=20"
```

Measurements latest:

```powershell
Invoke-RestMethod http://localhost:18080/api/measurements/latest
```

Workout detail:

```powershell
Invoke-RestMethod http://localhost:18080/api/workouts/2026-03-08
```

Что делает шаг:

- проверяет, что backend отвечает живыми данными из PostgreSQL и ClickHouse
- подтверждает, что UI и мобильный/клиентский read layer уже имеют usable endpoints

## Step 10. Проверить measurement write path

Пример создания measurement session:

```powershell
$payload = @{
    measured_at = "2026-03-27T08:00:00"
    measured_date = "2026-03-27"
    context_time_of_day = "morning"
    fasting_state = $true
    before_training = $true
    notes = "Manual startup-flow example"
    measurements = @(
        @{ measurement_type = "body_weight"; value_numeric = 92.4; unit = "kg" }
        @{ measurement_type = "waist"; value_numeric = 92.0; unit = "cm" }
        @{ measurement_type = "chest"; value_numeric = 108.8; unit = "cm" }
    )
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:18080/api/measurements/ `
    -ContentType "application/json" `
    -Body $payload
```

Что делает шаг:

- создаёт measurement session через backend API
- backend сохраняет source JSON
- затем регенерирует derived flat layer
- затем обновляет PostgreSQL RAW и ClickHouse MART
- затем возвращает актуальный detail response

Важно:

- `body_weight` передаётся как обычный `measurement_type`
- это часть unified measurements contract, а не отдельная raw-сущность

Если не хочешь менять реальный dataset в репозитории, этот шаг можно пропустить.

## Step 11. Запустить полный smoke-check

Только API/UI smoke:

```powershell
.\scripts\smoke_check.ps1
```

Smoke-check с reconciliation:

```powershell
.\scripts\smoke_check.ps1 -WithReconciliation
```

Полный bootstrap-сценарий:

```powershell
.\scripts\smoke_check.ps1 -Bootstrap
```

Что делает шаг:

- проверяет health endpoints
- проверяет workout/exercise/analytics endpoints
- проверяет measurements endpoints
- проверяет profile overview/timeline/highlights
- проверяет встроенный UI shell
- при необходимости запускает reconciliation

Когда использовать:

- перед коммитом
- после существенных изменений в backend или ingestion
- как короткую операционную проверку среды

## Step 12. Полезные операционные команды

Показать статус сервисов:

```powershell
docker compose ps
```

Посмотреть backend logs:

```powershell
docker compose logs -f backend
```

Повторно загрузить данные:

```powershell
docker compose --profile jobs run --rm --build ingestion
```

Повторно прогнать только workouts:

```powershell
docker compose --profile jobs run --rm --build ingestion python -m gym_data_ingestion.cli.main load-workouts
```

Повторно прогнать только measurements:

```powershell
docker compose --profile jobs run --rm --build ingestion python -m gym_data_ingestion.cli.main load-measurements
```

Остановить систему:

```powershell
docker compose down
```

Полностью сбросить контейнеры и volumes:

```powershell
docker compose down -v
```

Используй `down -v` только если действительно хочешь пересоздать локальное состояние БД.

## Step 13. Самый короткий рабочий сценарий

Если нужен минимальный путь без дополнительных проверок:

```powershell
docker compose down
docker compose up -d --build
docker compose --profile jobs run --rm --build ingestion
Start-Process http://localhost:18080/ui/
```

Если нужен безопасный рабочий сценарий с проверкой данных:

```powershell
docker compose down
.\scripts\check_ports.ps1
docker compose up -d --build
docker compose --profile jobs run --rm --build ingestion
docker compose --profile jobs run --rm ingestion python -m gym_data_ingestion.cli.main reconcile
.\scripts\smoke_check.ps1 -WithReconciliation
```

## Step 14. Что считать успешным запуском

Систему можно считать поднятой корректно, если:

- контейнеры `postgres`, `clickhouse`, `backend` работают
- ingestion завершился без ошибок
- reconciliation показывает `PASS`
- smoke-check проходит
- UI открывается на `/ui/`
- `GET /api/profile/current/overview` возвращает данные

Именно это состояние можно считать базовой готовностью Gym__Data к работе после запуска.
