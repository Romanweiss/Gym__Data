# Roman workouts structured export

## Что внутри
- `workouts/*.json` — один JSON на одну тренировку
- `flat/workouts.jsonl` — плоская таблица тренировок
- `flat/exercise_instances.jsonl` — экземпляры упражнений внутри тренировки
- `flat/sets.jsonl` — каждый подход отдельной строкой
- `flat/cardio_segments.jsonl` — сегменты кардио
- `flat/recovery_events.jsonl` — сауна / растяжка / душ и т.д.
- `flat/exercise_dictionary.jsonl` — словарь канонических упражнений и алиасов
- `schema/workout.schema.json` — базовая схема workout JSON

## Инженерные правила
- каноническое имя упражнения лежит в `exercise_name_canonical`
- вариации упражнения вынесены в `attributes`
- bodyweight-движения хранятся как `weight_kg=0`
- для неполной записи `125х` повторы поставлены в `1` и помечены `parse_note`
- `source_quality` отделяет детальные и summary-only источники

## Рекомендуемая загрузка
1. Читаешь `workouts/*.json` как source of truth
2. Для аналитики грузишь `flat/*.jsonl` в PostgreSQL / ClickHouse / Spark
3. CSV / Parquet строишь уже своим пайплайном
