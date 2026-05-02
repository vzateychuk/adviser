# План реализации персональных баз знаний для пациентов

## Концепция системы персональных баз знаний

Система персональных баз знаний (Knowledge Base - KB) для пациентов предназначена для создания "долговременной памяти" AI-ассистента. База знаний хранит структурированные медицинские данные пациента в виде отдельных SQLite файлов, что позволяет:

- Анализировать историю болезни пациента за длительный период
- Выявлять закономерности, хронические состояния и реакции на лечение
- Формировать персонализированные медицинские рекомендации на основе полной истории
- Поддерживать принятие решений врача с доступом к полной картине состояния пациента

### Принципы работы системы:
- **Конфиденциальность**: каждому пациенту соответствует отдельный файл базы знаний, который можно хранить локально или переносить на внешних носителях
- **Стандартизация**: использование кодов МКБ-10 обеспечивает совместимость с медицинскими системами и точность поиска
- **Масштабируемость**: система поддерживает добавление новых типов медицинских документов и тегов
- **Интеграция**: база знаний интегрируется с существующим PEC flow для автоматического сохранения результатов обработки

## Цель реализации

Создание системы персональных баз знаний (Knowledge Base - KB) для каждого пациента, которая будет:
- Хранить структурированные медицинские данные пациента
- Обеспечивать эффективный поиск по медицинским терминам и симптомам
- Поддерживать стандарты МКБ-10 для классификации медицинских данных
- Работать как "долговременная память" для AI-ассистента

## Архитектура системы

### Компоненты:
- **Маппинг МКБ-10** — YAML файл `config/icd10_mapping.yaml` с соответствием медицинских терминов кодам (общий для всех окружений, не зависит от dev/prod/test)
- **Персональные базы знаний** — отдельные SQLite файлы для каждого пациента
- **Система идентификации пациентов** — нормализация ФИО и даты рождения, формирование стабильного хэша
- **Интерфейс Sink** — абстракция для сохранения результатов PEC pipeline; внедряется в Orchestrator
- **Интеграция с PEC flow** — автоматическое сохранение результатов после успешной проверки Critic

### Принятые архитектурные решения:

**Поле tags в MedicalDoc:**
`MedicalDoc.tags` заполняется LLM-экстрактором (свободные теги). Для МКБ-10 отдельное поле в модели не добавляется. Вместо этого `Sink` пост-процессит кандидатов из `doc.tags + doc.diagnoses + doc.findings` через маппер и сохраняет результат только в базе знаний.

**Интерфейс ResultSink:**
Отдельный протокол Python (`typing.Protocol`), внедряемый в `Orchestrator` в момент его создания через `build_pec()`. Orchestrator вызывает `sink.store(result, doc)` после того как Critic одобрил результат. Mapper (`ICD10Mapper`) инжектируется в `LoggingSink` — это позволяет менять стратегию маппинга без изменения Sink.

**Путь к файлу маппинга МКБ-10:**
Добавить поле `icd10_mapping: Path` в `AppConfig` (`common/types.py`) с дефолтом `Path("config/icd10_mapping.yaml")`. Все три окружения явно декларируют путь в своих `app.yaml`. Это сохраняет совместимость с существующими конфигами и позволяет переопределить путь при необходимости.

---

## Предварительная работа: исправление бага

**Файл:** `flows/pec/models.py`, строки 206–214

В классе `CriticResult` поля `summary` и `issues` объявлены дважды. Удалить дублирующее объявление (строки 206–214), оставив только первое (строки 190–197).

---

## Идентификация пациента

### Алгоритм нормализации имени: `normalize_patient_name(name: str | None) -> str`

Нормализует ФИО пациента к стабильному виду `"фамилия и о"` (строчные буквы, пробелы).

Шаги:
1. Вернуть `"unknown"` если `name` равен `None` или пустой строке.
2. Привести всё к нижнему регистру.
3. Разделить склеенные инициалы: паттерн `([а-яёa-z])\.([а-яёa-z])` заменить на `\1. \2` (повторять до стабилизации).
4. Разбить по пробелам; убрать точки на конце каждого токена.
5. Первый токен — фамилия; если его длина равна 1 (одиночная буква) — raise `ValueError("surname not found")`.
6. Из оставшихся токенов взять первую букву каждого как инициал.
7. Если инициалов меньше двух — raise `ValueError("patronymic not found")`.
8. Вернуть `f"{фамилия} {инициал1} {инициал2}"`.

Примеры:

| Входные данные | Результат |
|---|---|
| `"Затейчук Владимир Евгеньевич"` | `"затейчук в е"` |
| `"Затейчук В.Е."` | `"затейчук в е"` |
| `"Затейчук В. Евген."` | `"затейчук в е"` |
| `"затейчук Vladimir E"` | `"затейчук в е"` |
| `"Затейчук Е. В."` | `"затейчук е в"` (другой хэш — это ожидаемо) |
| `"Затейчук В."` | `ValueError: patronymic not found` |
| `"В. Затейчук"` | `ValueError: surname not found` |
| `None` | `"unknown"` |

### Алгоритм нормализации даты: `normalize_birth_date(date_str: str | None) -> str`

Нормализует дату рождения к ISO 8601 `"YYYY-MM-DD"`.

Шаги:
1. Вернуть `"unknown"` если входная строка `None` или пустая после strip.
2. Перебирать паттерны в порядке приоритета:
   - `YYYY[-/.]MM[-/.]DD` (сначала 4-значный год)
   - `DD[-/.]MM[-/.]YYYY`
   - `DD Month YYYY` (названия месяцев на русском и английском)
   - `DD[-/.]MM[-/.]YY` (2-значный год — последний)
3. Правило 2-значного года: `год >= 25` → `1900 + год`; `год < 25` → `2000 + год`.
4. Если год не удалось определить — raise `ValueError("year not found")`.
5. Вернуть `f"{год:04d}-{месяц:02d}-{день:02d}"`.

Примеры:

| Входные данные | Результат |
|---|---|
| `"1971-02/23"` | `"1971-02-23"` |
| `"23.2.1971"` | `"1971-02-23"` |
| `"23 Feb 1971"` | `"1971-02-23"` |
| `"23.02.71"` | `"1971-02-23"` |
| `"02/23/ "` | `ValueError: year not found` |
| `None` | `"unknown"` |

### Алгоритм формирования patient_id: `generate_patient_id(full_name, birth_date) -> str`

```python
def generate_patient_id(full_name, birth_date):
    norm_name = _safe_normalize_name(full_name)   # перехватывает ValueError -> "unknown"
    norm_date = _safe_normalize_date(birth_date)  # перехватывает ValueError -> "unknown"
    patient_string = f"{norm_name}_{norm_date}"
    return hashlib.md5(patient_string.encode()).hexdigest()
```

Внутренние хелперы `_safe_normalize_*` перехватывают `ValueError` и возвращают `"unknown"`, поэтому публичный API никогда не бросает исключений.

**Новый файл:** `flows/pec/patient_id.py`

---

## Маппинг терминов в теги МКБ-10

### Конфигурация пути к файлу

**Файл:** `common/types.py` — добавить поле в класс `AppConfig`:
```python
icd10_mapping: Path = Path("config/icd10_mapping.yaml")
```
Дефолт обеспечивает обратную совместимость с существующими конфигами.

**Файлы:** `config/dev/app.yaml`, `config/prod/app.yaml`, `config/test/app.yaml` — добавить в каждый:
```yaml
icd10_mapping: "config/icd10_mapping.yaml"
```

### Формат файла `config/icd10_mapping.yaml`

Файл общий для всех окружений (МКБ-10 коды не зависят от dev/prod/test). Начинаем с минимального словаря (~20 терминов), расширяем по мере необходимости.

```yaml
mappings:
  "головная боль": "G44.0"
  "мигрень": "G43"
  "аллергия": "T78.4"
  "высыпания": "L30.9"
  "температура": "R50.9"
  "гипертония": "I10"
  "диабет": "E11"
  "сахарный диабет": "E11"
  "анемия": "D64.9"
  "бронхит": "J40"
  "пневмония": "J18.9"
  "артрит": "M19.9"
  "остеохондроз": "M42.9"
  "гастрит": "K29.7"
  "холецистит": "K81.9"
  "цистит": "N30.9"
  "отит": "H66.9"
  "конъюнктивит": "H10.9"
  "варикоз": "I83.9"
  "ишемия": "I25.9"
```

### Класс `ICD10Mapper`

**Новый файл:** `flows/pec/icd10_mapper.py`

```python
class ICD10Mapper:
    def __init__(self, mapping_path: Path):
        self._mappings = self._load(mapping_path)  # dict[str, str], ключи в нижнем регистре

    def map_terms(self, terms: list[str]) -> list[str]:
        """Маппит медицинские термины в коды МКБ-10. Неизвестные термины пропускаются. Дедупликация кодов."""
        seen, result = set(), []
        for term in terms:
            code = self._mappings.get(term.lower().strip())
            if code and code not in seen:
                seen.add(code)
                result.append(code)
        return result

    def _load(self, path: Path) -> dict[str, str]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {k.lower(): v for k, v in data.get("mappings", {}).items()}
```

---

## Интерфейс Sink

**Новый файл:** `flows/pec/sink.py`

### Протокол ResultSink

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ResultSink(Protocol):
    async def store(self, result: OcrResult, doc: MedicalDoc) -> None: ...
```

### LoggingSink (реализация по умолчанию)

Используется в тестах и как реализация по умолчанию до появления KBSink (SQLite).

```python
class LoggingSink:
    def __init__(self, mapper: ICD10Mapper):
        self._mapper = mapper  # ICD10Mapper инжектируется — можно менять стратегию

    async def store(self, result: OcrResult, doc: MedicalDoc) -> None:
        patient_id = generate_patient_id(doc.patient.full_name, doc.patient.birth_date)
        candidates = doc.tags + doc.diagnoses + doc.findings
        icd10_tags = self._mapper.map_terms(candidates)
        log.info(
            "KB sink: patient_id=%s schema=%s status=%s icd10_tags=%s",
            patient_id, result.schema_name, result.status, icd10_tags,
        )
```

---

## Интеграция с PEC flow

### Процесс сохранения:
1. Orchestrator завершает полный цикл plan → execute → critic
2. Critic одобряет результат (`runCtx.status == RunStatus.COMPLETED`)
3. Orchestrator вызывает `await self._sink.store(ocr_result, runCtx.doc)` перед возвратом
4. Sink генерирует `patient_id`, маппит кандидатов в МКБ-10 коды, сохраняет/логирует

### Изменения в `flows/pec/orchestrator.py`:

Добавить `sink` в конструктор:
```python
def __init__(self, *, planner, executor, critic, max_retries, sink: ResultSink | None = None):
    self._sink = sink
```

В конце метода `run()` перед `return`:
```python
if self._sink is not None and runCtx.doc is not None:
    await self._sink.store(ocr_result, runCtx.doc)
return ocr_result
```

### Изменения в `flows/pec/build_pec.py`:

```python
def build_pec(*, llm_factory, app_cfg, models_registry, sink: ResultSink | None = None) -> Orchestrator:
    ...
    return Orchestrator(..., sink=sink)
```

### Изменения в `cli/main.py`:

```python
mapper = ICD10Mapper(app_cfg.icd10_mapping)
ctx.obj["sink"] = LoggingSink(mapper)
```

### Изменения в `cli/commands/ocr_flow.py`:

```python
orchestrator = build_pec(
    llm_factory=ctx.obj["llm_factory"],
    app_cfg=ctx.obj["app_cfg"],
    models_registry=ctx.obj["models_registry"],
    sink=ctx.obj.get("sink"),
)
```

---

## Структура базы знаний (будущий этап — KBSink)

### Таблицы:
```sql
-- Таблица документов пациента (хранение полных данных)
CREATE TABLE kb_documents (
    id TEXT PRIMARY KEY,
    schema_type TEXT,
    created_at DATETIME,
    tags TEXT,          -- JSON array с кодами МКБ-10 (результат ICD10Mapper)
    content TEXT,       -- YAML dump результата (для восстановления полного документа)
    processed_data TEXT -- JSON структура MedicalDoc
);

-- FTS5 таблица для полнотекстового поиска (только чистый текст, без JSON/YAML)
CREATE VIRTUAL TABLE kb_search USING fts5(
    id,
    tags,               -- "G43 T78.4" (коды МКБ-10 через пробел)
    conclusion,         -- doc.conclusion (итоговый вывод документа)
    diagnoses,          -- "диагноз1 диагноз2" (через пробел)
    medications,        -- "лекарство1 лекарство2" (через пробел)
    findings,           -- "находка1 находка2" (через пробел)
    recommendations     -- "рекомендация1 рекомендация2" (через пробел)
);
```

**Примечание:** `kb_documents` хранит структурированные данные (YAML, JSON) для полного восстановления документа. `kb_search` содержит только чистый текст для эффективного полнотекстового поиска — FTS5 токенизирует текст, поэтому JSON/YAML структура была бы помехой (ключи структуры стали бы поисковыми терминами вместо медицинских терминов).

### Структура директории:
```
.kb/
├── patient_hash12345.db    # База знаний пациента с ID hash12345
├── patient_hash67890.db    # База знаний пациента с ID hash67890
└── ...
```

---

## Поиск по базе знаний (будущий этап)

### Использование FTS5:
- Поиск по тегам с кодами МКБ-10
- Поиск по медицинским терминам
- Поиск по диагнозам и рекомендациям

### Функциональность поиска:
1. **Лексический поиск** — по тегам МКБ-10 для быстрого поиска документов
2. **Семантический поиск** — по содержимому документов для формирования контекста
3. **Интеграция с AI-ассистентом** — использование базы знаний для генерации рекомендаций

---

## Поэтапный план реализации

### Шаг 0: Исправление бага (предварительная работа)
- Удалить дублирующиеся поля `summary` и `issues` из `CriticResult` в `flows/pec/models.py` (строки 206–214)

### Шаг 1: Идентификация пациентов
- Создать `flows/pec/patient_id.py` с функциями `normalize_patient_name`, `normalize_birth_date`, `generate_patient_id`

### Шаг 2: Маппинг МКБ-10
- Добавить поле `icd10_mapping: Path` в `AppConfig` (`common/types.py`)
- Добавить `icd10_mapping` в `config/dev/app.yaml`, `config/prod/app.yaml`, `config/test/app.yaml`
- Создать `config/icd10_mapping.yaml` с минимальным словарём (~20 терминов)
- Создать `flows/pec/icd10_mapper.py` с классом `ICD10Mapper`

### Шаг 3: Интерфейс Sink
- Создать `flows/pec/sink.py` с протоколом `ResultSink` и реализацией `LoggingSink`

### Шаг 4: Интеграция с PEC flow
- Добавить `sink` в `Orchestrator` (`flows/pec/orchestrator.py`)
- Добавить `sink` в `build_pec()` (`flows/pec/build_pec.py`)
- Обновить `cli/commands/ocr_flow.py` — передавать `sink` из `ctx.obj`
- Обновить `cli/main.py` — создавать `LoggingSink` и добавлять в `ctx.obj`

### Шаг 5: Тесты

**`tests/flows/pec/test_patient_id.py`:**

| Тест | Что проверяет |
|------|---------------|
| `test_normalize_name_full_cyrillic` | "Затейчук Владимир Евгеньевич" → "затейчук в е" |
| `test_normalize_name_dotted_initials` | "Затейчук В.Е." → "затейчук в е" |
| `test_normalize_name_abbreviated_mixed` | "Затейчук В. Евген." → "затейчук в е" |
| `test_normalize_name_latin_first` | "затейчук Vladimir E" → "затейчук в е" |
| `test_normalize_name_wrong_initial_order` | "Затейчук Е. В." → "затейчук е в" (другой хэш — нет ошибки) |
| `test_normalize_name_missing_patronymic` | "Затейчук В." → `ValueError` |
| `test_normalize_name_initial_first` | "В. Затейчук" → `ValueError` |
| `test_normalize_name_none` | `None` → "unknown" |
| `test_normalize_date_iso_mixed_sep` | "1971-02/23" → "1971-02-23" |
| `test_normalize_date_dd_m_yyyy` | "23.2.1971" → "1971-02-23" |
| `test_normalize_date_month_name_en` | "23 Feb 1971" → "1971-02-23" |
| `test_normalize_date_two_digit_year` | "23.02.71" → "1971-02-23" |
| `test_normalize_date_missing_year` | "02/23/ " → `ValueError` |
| `test_normalize_date_none` | `None` → "unknown" |
| `test_generate_patient_id_stable` | одинаковые входные данные → одинаковый хэш |
| `test_generate_patient_id_different_patients` | разные пациенты → разные хэши |
| `test_generate_patient_id_format_invariant` | "Затейчук В.Е." и "Затейчук Владимир Евгеньевич" → одинаковый хэш |

**`tests/flows/pec/test_icd10_mapper.py`** (использует `tmp_path` для изоляции от реального файла):

| Тест | Что проверяет |
|------|---------------|
| `test_known_term_returns_code` | "мигрень" → ["G43"] |
| `test_unknown_term_dropped` | "неизвестный термин" → [] |
| `test_case_insensitive` | "МИГРЕНЬ" → тот же результат что и "мигрень" |
| `test_multiple_terms` | ["мигрень", "аллергия"] → ["G43", "T78.4"] |
| `test_deduplication` | один код не дублируется |
| `test_empty_list` | [] → [] |
| `test_load_from_file` | корректная загрузка из YAML через `tmp_path` |

### Шаг 6: KBSink и SQLite хранилище

**Конфигурация пути к директории KB:**

Добавить поле `kb_dir: Path` в `AppConfig` (`common/types.py`):
```python
kb_dir: Path = Path(".kb")
```
Добавить в `config/dev/app.yaml`, `config/prod/app.yaml`, `config/test/app.yaml`:
```yaml
kb_dir: ".kb"
```

**Новый файл:** `flows/pec/kb_sink.py`

Класс `KBSink` реализует протокол `ResultSink`. Lazy creation — SQLite создаёт файл автоматически при первом соединении. Приватный метод `_bootstrap(conn)` выполняет `CREATE TABLE IF NOT EXISTS` и `CREATE VIRTUAL TABLE IF NOT EXISTS` — idempotent, вызывается при каждом соединении.

```python
class KBSink:
    def __init__(self, kb_dir: Path, mapper: ICD10Mapper):
        self._kb_dir = kb_dir
        self._mapper = mapper

    async def store(self, result: OcrResult, doc: MedicalDoc) -> None:
        patient_id = generate_patient_id(doc.patient.full_name, doc.patient.birth_date)
        db_path = self._kb_dir / f"{patient_id}.db"
        self._kb_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            self._bootstrap(conn)
            self._insert(conn, result, doc)

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kb_documents (
                id TEXT PRIMARY KEY,
                schema_type TEXT,
                created_at DATETIME,
                tags TEXT,
                content TEXT,
                processed_data TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_search USING fts5(
                id, tags, conclusion, diagnoses, medications, findings, recommendations
            );
        """)

    def _insert(self, conn: sqlite3.Connection, result: OcrResult, doc: MedicalDoc) -> None:
        candidates = doc.tags + doc.diagnoses + doc.findings
        icd10_tags = self._mapper.map_terms(candidates)
        doc_id = f"{result.document_path}_{result.schema_name}"
        conn.execute(
            "INSERT OR REPLACE INTO kb_documents VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, result.schema_name, datetime.utcnow().isoformat(),
             json.dumps(icd10_tags, ensure_ascii=False),
             result.context,
             json.dumps(doc.model_dump(), ensure_ascii=False)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO kb_search VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, " ".join(icd10_tags), doc.conclusion or "",
             " ".join(doc.diagnoses), " ".join(m.name for m in doc.medications),
             " ".join(doc.findings), " ".join(doc.recommendations)),
        )
```

Будущее расширение: таблица `schema_version` для поддержки миграций.

**Обновить `cli/main.py`:** использовать `KBSink` вместо `LoggingSink`:
```python
mapper = ICD10Mapper(app_cfg.icd10_mapping)
ctx.obj["sink"] = KBSink(kb_dir=app_cfg.kb_dir, mapper=mapper)
```

**Тесты: `tests/flows/pec/test_kb_sink.py`** (используют `tmp_path`):

| Тест | Что проверяет |
|------|---------------|
| `test_creates_db_file_on_first_store` | файл пациента создаётся при первом вызове `store()` |
| `test_bootstrap_creates_tables` | `kb_documents` и `kb_search` созданы после `_bootstrap` |
| `test_insert_document` | запись появляется в `kb_documents` с правильными полями |
| `test_icd10_tags_stored` | МКБ-10 коды из маппера записаны в поле `tags` |
| `test_different_patients_separate_files` | два пациента → два отдельных `.db` файла |
| `test_store_idempotent` | повторный `store()` того же документа не дублирует запись (INSERT OR REPLACE) |

---

## Карта изменений файлов

| Действие | Файл |
|----------|------|
| Исправить баг | `flows/pec/models.py` |
| Изменить | `common/types.py` (добавить `icd10_mapping` и `kb_dir` в `AppConfig`) |
| Изменить | `config/dev/app.yaml` |
| Изменить | `config/prod/app.yaml` |
| Изменить | `config/test/app.yaml` |
| Создать | `config/icd10_mapping.yaml` |
| Создать | `flows/pec/patient_id.py` |
| Создать | `flows/pec/icd10_mapper.py` |
| Создать | `flows/pec/sink.py` |
| Изменить | `flows/pec/orchestrator.py` |
| Изменить | `flows/pec/build_pec.py` |
| Изменить | `cli/commands/ocr_flow.py` |
| Изменить | `cli/main.py` |
| Создать | `flows/pec/kb_sink.py` |
| Создать | `tests/flows/pec/test_patient_id.py` |
| Создать | `tests/flows/pec/test_icd10_mapper.py` |
| Создать | `tests/flows/pec/test_kb_sink.py` |

## Проверка

```bash
uv run pytest tests/flows/pec/test_patient_id.py tests/flows/pec/test_icd10_mapper.py tests/flows/pec/test_kb_sink.py -v
uv run pytest tests/flows/pec/ -v   # весь PEC тест-сьют должен оставаться зелёным
uv run ruff check flows/pec/patient_id.py flows/pec/icd10_mapper.py flows/pec/sink.py flows/pec/kb_sink.py
```
