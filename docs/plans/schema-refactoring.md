# Schema Refactoring Plan

## Цель и обоснование

Оптимизировать YAML схемы в `flows/pec/schemas/` и убрать дублирование между
YAML-based critic rules и LLM-generated success_criteria.

После перехода Executor на `MedicalDoc` YAML схемы выполняют единственную роль —
fuzzy matching при идентификации типа документа Planner'ом. Всё остальное
(структура извлечения, правила валидации) покрывается `MedicalDoc` и
`success_criteria`, которые Planner генерирует per-document.

`critic_rules` в YAML — статичные дефолты на случай когда LLM не заполнил
`success_criteria`. LLM-generated criteria лучше: они отражают конкретный документ
и формулируются под его содержимое. Fallback из YAML не нужен.

Результат: YAML схемы сжимаются до fuzzy-matching минимума, архитектура
упрощается — ничего нового не создаётся, только удаляется.

---

## Что удаляем и почему

**Оставляем (используется в runtime):**

| Поле YAML | Где используется | Вывод |
|---|---|---|
| `schema_meta.id` | `SchemaCatalog.scan()`, fuzzy matching, `prompt_summary()` | ОСТАВИТЬ |
| `schema_meta.category` | `prompt_summary()` → `{{SCHEMA_CATALOG}}` в Planner | ОСТАВИТЬ |
| `schema_meta.title` | `prompt_summary()` → `{{SCHEMA_CATALOG}}` в Planner | ОСТАВИТЬ |
| `schema_meta.intended_use` | `prompt_summary()` → `{{SCHEMA_CATALOG}}` в Planner | ОСТАВИТЬ — Planner использует для выбора схемы |
| `selection_hints.aliases` | `SchemaCatalog.resolve_schema_id()` fuzzy matching + `prompt_summary()` | ОСТАВИТЬ |

**Удаляем (мертвые или замещенные поля):**

| Элемент | Где | Причина удаления |
|---|---|---|
| `critic_rules.must_verify` | `flows/pec/schemas/*.yaml` | Заменяется LLM-generated `success_criteria` |
| `extraction_contract` | `flows/pec/schemas/*.yaml` | `SCHEMA_REQUIRED_BLOCKS` не используется ни в одном промпте |
| `selection_hints.key_signals` | `flows/pec/schemas/*.yaml` | Загружается в `SchemaDefinition`, нигде не рендерится в промпты |
| Пустые структурные блоки | `flows/pec/schemas/*.yaml` | `document: {}`, `patient: {}` — были шаблонами для LLM, заменены `MedicalDoc` |
| `critic_rules` поле | `flows/pec/schema_catalog.py` | Поле в `SchemaDefinition` и загрузка в `scan()` |
| `key_signals`, `required_blocks` поля | `flows/pec/schema_catalog.py` | Мертвые поля — нигде не используются в рантайме |
| `required_blocks` из `prompt_summary()` | `flows/pec/schema_catalog.py` | Убрать из вывода в Planner каталог |
| `SCHEMA_CRITIC_RULES` | `flows/pec/renderer.py` | `schema.critic_rules` больше не существует |
| `SCHEMA_REQUIRED_BLOCKS` | `flows/pec/renderer.py` | Не используется ни в одном `.md` промпте |
| `schema_critic_rules` секция | `prompts/critic/user.md` | `{{SCHEMA_CRITIC_RULES}}` будет пустым |
| `schema_yaml` секция | `prompts/critic/user.md` | `{{SCHEMA_YAML}}` будет нести только fuzzy-matching мусор |
| Fallback в `_post_process()` | `flows/pec/planner.py:253` | `schema_def.critic_rules` удаляется из `SchemaDefinition` |
| `default_factory=list` из `success_criteria` | `flows/pec/planner.py` (`PlanStepSchema`) | Поле становится обязательным, LLM всегда заполняет |

---

## Шаги реализации

### 1. Минимизация YAML схем

Каждый файл в `flows/pec/schemas/` оставляет только то, что нужно для fuzzy matching.

**`flows/pec/schemas/lab.yaml`** — целевое состояние:
```yaml
schema_meta:
  id: lab
  category: lab
  title: Universal Lab Schema
  intended_use:
    - biochemistry
    - hormones
    - blood_panel
selection_hints:
  aliases:
    - анализы
    - лаборатория
    - blood test
```

**`flows/pec/schemas/diagnostic.yaml`**:
```yaml
schema_meta:
  id: diagnostic
  category: diagnostic
  title: Universal Diagnostic Schema
  intended_use:
    - ultrasound
    - xray
    - imaging
selection_hints:
  aliases:
    - узи
    - xray
    - ultrasound
```

**`flows/pec/schemas/consultation.yaml`**:
```yaml
schema_meta:
  id: consultation
  category: consultation
  title: Universal Consultation Schema
  intended_use:
    - physician_consultation
    - outpatient_note
selection_hints:
  aliases:
    - консультация
    - physician
    - note
```

**`flows/pec/schemas/medication_trace.yaml`**:
```yaml
schema_meta:
  id: medication_trace
  category: medication_trace
  title: Universal Medication Trace Schema
  intended_use:
    - prescriptions
    - medication_history
selection_hints:
  aliases:
    - prescription
    - medication
```

Создать `flows/pec/schemas/README.md`:

```markdown
# PEC Schema Catalog

YAML files in this directory serve a single purpose: **fuzzy matching** during
the Planner phase. The Planner reads them to map a natural-language document
description to a canonical schema ID (`lab`, `diagnostic`, `consultation`,
`medication_trace`).

## What belongs here

Each YAML file contains:

- `schema_meta` — canonical ID, category, title, and intended_use examples
  that help the Planner pick the right schema for a given document
- `selection_hints.aliases` — alternative names the Planner or user may use
  (e.g. "анализы", "blood test" → `lab`)

## What does NOT belong here

- Extraction field templates — defined in `flows/pec/schemas/medical_doc.py`
  (`MedicalDoc` Pydantic model)
- Validation rules — generated per-document by the Planner as
  `PlanStep.success_criteria` and verified by the Critic

## Schema IDs

| ID | Typical documents |
|----|-------------------|
| `lab` | Blood panels, biochemistry, hormone tests, urinalysis |
| `diagnostic` | Ultrasound, X-ray, CT, MRI, imaging reports |
| `consultation` | Physician notes, specialist conclusions, outpatient visits |
| `medication_trace` | Prescriptions, medication lists, therapy history |

## Adding a new schema

1. Create `{schema_id}.yaml` with `schema_meta` and `selection_hints.aliases`
2. Add the new `schema_id` to the `Literal` type in `MedicalDoc.schema_id`
   (`flows/pec/schemas/medical_doc.py`)
3. Add schema-specific `success_criteria` hints to `prompts/planner/system.md`
```

---

### 2. Чистка SchemaCatalog

Файл: `flows/pec/schema_catalog.py`

Из `SchemaDefinition` удалить три поля:
```python
# Удалить:
key_signals: list[str] = Field(default_factory=list)
required_blocks: list[str] = Field(default_factory=list)
critic_rules: list[str] = Field(default_factory=list)
```

Из `SchemaCatalog.scan()` удалить загрузку мертвых секций:
```python
# Удалить:
extraction = data.get("extraction_contract", {})
critic = data.get("critic_rules", {})

# И в SchemaDefinition():
key_signals=list(selection.get("key_signals", [])),
required_blocks=list(extraction.get("required_blocks", [])),
critic_rules=list(critic.get("must_verify", [])),
```

Из `SchemaCatalog.prompt_summary()` удалить вывод `required_blocks`:
```python
# Удалить:
blocks = ", ".join(schema.required_blocks) if schema.required_blocks else "-"
# И строку:
f"  required_blocks: {blocks}"
```

---

### 3. Чистка Renderer

Файл: `flows/pec/renderer.py`

Предварительная проверка подтвердила: `{{SCHEMA_YAML}}`, `{{SCHEMA_CRITIC_RULES}}`,
`{{SCHEMA_REQUIRED_BLOCKS}}` не используются ни в одном executor промпте —
только `{{SCHEMA_CRITIC_RULES}}` и `{{SCHEMA_YAML}}` присутствуют в
`prompts/critic/user.md`, и оба удаляются на шаге 4.

Из `render_step_template()` удалить три переменные:
```python
# Удалить из values:
"SCHEMA_REQUIRED_BLOCKS": "\n".join(schema.required_blocks) if schema else "",
"SCHEMA_CRITIC_RULES": "\n".join(schema.critic_rules) if schema else "",
"SCHEMA_YAML": schema.prompt_excerpt if schema else "",
```

После этого параметр `schema: SchemaDefinition | None` в `render_step_template()`
больше не используется — убрать его из сигнатуры и всех вызовов.

Из `render_critic_template()` удалить две переменные:
```python
# Удалить из values:
"SCHEMA_CRITIC_RULES": "\n".join(schema.critic_rules) if schema else "",
"SCHEMA_YAML": schema.prompt_excerpt if schema else "",
```

После этого параметр `schema: SchemaDefinition | None` в `render_critic_template()`
тоже не используется — убрать его из сигнатуры и из вызова в `critic.py:48`.

---

### 4. Обновление Critic промпта

Файл: `prompts/critic/user.md`

Удалить секции, которые теперь будут пустыми:
```markdown
# Удалить:
schema_critic_rules: |
  {{SCHEMA_CRITIC_RULES}}

schema_yaml: |
  {{SCHEMA_YAML}}
```

`{{SUCCESS_CRITERIA}}` остаётся — это главный источник правил для Critic,
он приходит из `PlanStep.success_criteria` через `render_critic_template()`.

---

### 5. Обновление Planner

**5.1 Убрать fallback в `_post_process()`**

Файл: `flows/pec/planner.py`

```python
# БЫЛО (строка 253):
criteria = step.success_criteria if step.success_criteria else schema_def.critic_rules

# СТАЛО:
criteria = step.success_criteria
```

Также убрать получение `schema_def` если оно используется только для fallback:
```python
# БЫЛО (строка 248):
schema_def = self._schema_catalog.get(schema_name)

# Проверить — если schema_def используется только для critic_rules fallback,
# эту строку тоже удалить.
```

**5.2 Сделать `success_criteria` обязательным**

В `PlanStepSchema` (тот же файл):
```python
# БЫЛО:
success_criteria: list[str] = Field(
    default_factory=list,
    description=(
        "Verification criteria for the Critic. "
        "If empty, defaults will be loaded from the schema catalog."
    ),
)

# СТАЛО:
success_criteria: list[str] = Field(
    min_length=1,
    description=(
        "Verification criteria the Critic will check. "
        "Must not be empty. List specific values, formats, and completeness rules "
        "relevant to this document type."
    ),
)
```

**5.4 Проверить генерацию `success_criteria` после изменений**

После того как `default_factory=list` заменён на `min_length=1`, instructor
будет делать retry если LLM вернёт пустой список — fallback не нужен.

Убедиться что это работает корректно:
- Запустить Planner на реальном документе каждого типа (lab, diagnostic,
  consultation, medication_trace) и проверить что `steps[].success_criteria`
  непустые и содержат schema-specific правила
- Убедиться что instructor не застревает в бесконечных retry из-за пустого
  списка — если prompt правильно обновлён на шаге 5.3, этого не произойдёт

---

**5.3 Обновить system prompt Planner'а**

Файл: `prompts/planner/system.md`

Расширить секцию `## Step Construction` — добавить schema-specific подсказки
чтобы LLM генерировал полные criteria без fallback:

```markdown
## Step Construction

When action is "PLAN", each step must have:
- `id`: Step number (starting from 1)
- `title`: Human-readable description
- `type`: Always "ocr"
- `input`: Always "document_content"
- `output`: Must equal schema_name exactly
- `success_criteria`: Non-empty list of verification rules for the Critic.

Always include base rules:
- "Preserve all dates exactly as written"
- "Preserve all numeric values exactly as written"
- "Preserve all measurement units exactly as written"
- "Preserve all surnames exactly as written"

Add schema-specific rules:

| schema_name      | Add to success_criteria |
|------------------|-------------------------|
| lab              | "No analyte invented or dropped", "Reference ranges preserved when present" |
| diagnostic       | "All organ measurements preserved", "Procedure name captured" |
| consultation     | "All diagnoses listed", "All recommendations captured" |
| medication_trace | "All drug dosages preserved exactly", "Drug names not altered" |
```

---

## Критерии завершения

- [ ] Все 4 YAML файла содержат только `schema_meta` и `selection_hints.aliases`
- [ ] `flows/pec/schemas/README.md` создан
- [ ] `SchemaDefinition` не содержит `key_signals`, `required_blocks`, `critic_rules`
- [ ] `SchemaCatalog.scan()` не читает `extraction_contract`, `critic`, `key_signals`
- [ ] `SchemaCatalog.prompt_summary()` не выводит `required_blocks`
- [ ] `render_step_template()` не содержит `SCHEMA_CRITIC_RULES`, `SCHEMA_REQUIRED_BLOCKS`, `SCHEMA_YAML`
- [ ] `render_step_template()` не принимает параметр `schema`
- [ ] `render_critic_template()` не содержит `SCHEMA_CRITIC_RULES`, `SCHEMA_YAML`
- [ ] `render_critic_template()` не принимает параметр `schema`
- [ ] `prompts/critic/user.md` не содержит `{{SCHEMA_CRITIC_RULES}}`, `{{SCHEMA_YAML}}`
- [ ] `PlanStepSchema.success_criteria` обязателен (`min_length=1`, без `default_factory`)
- [ ] Fallback `schema_def.critic_rules` убран из `_post_process()`
- [ ] `prompts/planner/system.md` содержит schema-specific подсказки для criteria

---

## Файлы для изменения

| Файл | Тип изменений |
|---|---|
| `flows/pec/schemas/lab.yaml` | Оставить только `schema_meta` + `selection_hints.aliases` |
| `flows/pec/schemas/diagnostic.yaml` | Оставить только `schema_meta` + `selection_hints.aliases` |
| `flows/pec/schemas/consultation.yaml` | Оставить только `schema_meta` + `selection_hints.aliases` |
| `flows/pec/schemas/medication_trace.yaml` | Оставить только `schema_meta` + `selection_hints.aliases` |
| `flows/pec/schemas/README.md` | Создать (новый файл) |
| `flows/pec/schema_catalog.py` | Удалить `key_signals`, `required_blocks`, `critic_rules` из модели и `scan()` |
| `flows/pec/renderer.py` | Удалить `SCHEMA_CRITIC_RULES`, `SCHEMA_REQUIRED_BLOCKS`, `SCHEMA_YAML` из обоих методов; убрать параметр `schema` из обеих сигнатур |
| `prompts/critic/user.md` | Удалить `schema_critic_rules` и `schema_yaml` секции |
| `flows/pec/planner.py` | Убрать fallback, обновить `PlanStepSchema.success_criteria` |
| `prompts/planner/system.md` | Добавить schema-specific таблицу criteria |

Изменения минимальные и обратимые. Нет новых классов, нет новых файлов кроме README.
