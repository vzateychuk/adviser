# План интеграции Instructor: Универсальная схема

> **ВНИМАНИЕ:** Документ требует периодической актуализации. Фактическая реализация может отличаться от описанной. Перед внесением изменений сверяйтесь с кодовой базой.

## Обзор

Миграция PEC pipeline на structured outputs с использованием **единой универсальной схемы**
для всех типов медицинских документов.

> **Примечание:** Схема `MedicalDoc` находится в `flows/pec/models.py`, а не в отдельном файле `flows/pec/schemas/medical_doc.py`.

---

## Последовательность реализации

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Planner (✅ DONE) │
│ • chat_structured() с PlannerOutputSchema │
│ • 4 schema_id: lab, diagnostic, consultation, medication_trace │
└─────────────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Универсальная схема (✅ DONE) │
│ • MedicalDoc (единая Pydantic модель) в flows/pec/models.py │
│ • MedicalDoc.merge() для инкрементального объединения │
│ • RunContext с полями doc, steps_results │
└─────────────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Executor (✅ DONE) │
│ • chat_structured() с MedicalDoc │
│ • Возвращает StepResult с типизированным doc │
│ • Инкрементальный merge в orchestrator │
└─────────────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Critic (⏳ В ПРОЦЕССЕ) │
│ • critic.py — ✅ chat_structured(CriticResult), новая сигнатура │
│ • renderer.py — ✅ render_critic_final_template() добавлена │
│ • orchestrator.py — ⬜ всё ещё цикл по step_results (надо исправить) │
│ • prompts/critic/*.md — ⬜ всё ещё YAML (надо исправить) │
└─────────────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. RunContext (⏳ ЧАСТИЧНО) ✅ Сериализация | ⬜ CLI │
│ • MedicalDoc.merge() — ✅ DONE (models.py:582-655) │
│ • RunContext — ✅ DONE (models.py:663-708) │
│ • Сериализация — ✅ DONE (models.py:766-812) │
│ • CLI команды — ⬜ не реализовано │
└─────────────────────────────────────────────────────────────────────────┘
---

## Фаза 1: Planner ✅ DONE

Уже реализовано:
- `PlannerOutputSchema` с instructor
- `chat_structured()` вместо `chat()` + YAML parsing
- Промпты обновлены на JSON формат
- Mock scenarios для тестов

---

## Фаза 2: Универсальная схема извлечения

### 2.1 Цель

Заменить 4 разных YAML структуры на **одну Pydantic модель** `MedicalDoc`.

### 2.2 Схема MedicalDoc

**Файл:** `flows/pec/models.py` (класс `MedicalDoc`, строки 406-655)

```python
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Метаданные документа."""
    
    date: str | None = Field(
        default=None,
        description="Дата документа в формате как в источнике (например, '2020-02-09')"
    )
    organization: str | None = Field(
        default=None,
        description="Название медицинского учреждения"
    )
    doctor: str | None = Field(
        default=None,
        description="ФИО врача"
    )
    specialty: str | None = Field(
        default=None,
        description="Специальность врача (например, 'УЗИ-диагностика', 'Терапевт')"
    )


class PatientInfo(BaseModel):
    """Информация о пациенте."""
    
    full_name: str | None = Field(
        default=None,
        description="Полное ФИО пациента"
    )
    birth_date: str | None = Field(
        default=None,
        description="Дата рождения в формате как в источнике"
    )
    gender: Literal["male", "female", "unknown"] | None = Field(
        default=None,
        description="Пол пациента"
    )


class Measurement(BaseModel):
    """Универсальное измерение.
    
    Используется для:
    - Лабораторных показателей (гемоглобин, глюкоза)
    - Измерений на УЗИ/КТ/МРТ (размеры органов)
    - Физикальных данных (АД, пульс, температура)
    """
    
    name: str = Field(
        description="Название показателя (например, 'Гемоглобин', 'Толщина стенки')"
    )
    value: str = Field(
        description="Значение как в документе (например, '140', '12', '120/80')"
    )
    unit: str | None = Field(
        default=None,
        description="Единица измерения (например, 'г/л', 'мм', 'мм рт.ст.')"
    )
    reference_range: str | None = Field(
        default=None,
        description="Референсный диапазон (например, '120-160', '< 5.5')"
    )
    status: Literal["normal", "low", "high", "abnormal", "unknown"] = Field(
        default="unknown",
        description="Статус относительно нормы"
    )
    notes: str | None = Field(
        default=None,
        description="Дополнительные комментарии к показателю"
    )


class Medication(BaseModel):
    """Информация о препарате."""
    
    name: str = Field(
        description="Название препарата"
    )
    dosage: str | None = Field(
        default=None,
        description="Дозировка (например, '500 мг', '10 мл')"
    )
    frequency: str | None = Field(
        default=None,
        description="Частота приёма (например, '2 раза в день', 'утром натощак')"
    )
    duration: str | None = Field(
        default=None,
        description="Длительность курса (например, '14 дней', '1 месяц')"
    )
    route: str | None = Field(
        default=None,
        description="Способ приёма (например, 'перорально', 'в/м', 'наружно')"
    )


class MedicalDoc(BaseModel):
    """Универсальная схема медицинского документа.
    
    Единая структура для всех типов документов:
    - lab: лабораторные анализы
    - diagnostic: УЗИ, рентген, КТ, МРТ
    - consultation: консультации врачей
    - medication_trace: назначения, рецепты
    
    LLM заполняет релевантные поля, остальные остаются пустыми.
    """
    
    # === ИДЕНТИФИКАЦИЯ ===
    schema_id: Literal["lab", "diagnostic", "consultation", "medication_trace"] = Field(
        description="Тип документа, определённый Planner'ом"
    )
    
    # === ОБЩИЕ СЕКЦИИ ===
    document: DocumentInfo = Field(
        default_factory=DocumentInfo,
        description="Метаданные документа"
    )
    patient: PatientInfo = Field(
        default_factory=PatientInfo,
        description="Информация о пациенте"
    )
    
    # === ИЗМЕРЕНИЯ (lab, diagnostic) ===
    measurements: list[Measurement] = Field(
        default_factory=list,
        description=(
            "Числовые измерения: "
            "для lab — анализы (гемоглобин, глюкоза); "
            "для diagnostic — размеры органов, объёмы"
        )
    )
    
    # === ТЕКСТОВЫЕ НАХОДКИ (diagnostic, consultation) ===
    findings: list[str] = Field(
        default_factory=list,
        description=(
            "Текстовые находки и наблюдения: "
            "описания на УЗИ, результаты осмотра, жалобы"
        )
    )
    
    # === ДИАГНОЗЫ (consultation, diagnostic) ===
    diagnoses: list[str] = Field(
        default_factory=list,
        description="Диагнозы (основной и сопутствующие)"
    )
    
    # === РЕКОМЕНДАЦИИ (все типы) ===
    recommendations: list[str] = Field(
        default_factory=list,
        description="Рекомендации врача, назначения на обследования"
    )
    
    # === ПРЕПАРАТЫ (medication_trace, consultation) ===
    medications: list[Medication] = Field(
        default_factory=list,
        description="Назначенные или принимаемые препараты"
    )
    
    # === ЗАКЛЮЧЕНИЕ ===
    conclusion: str | None = Field(
        default=None,
        description="Общее заключение документа"
    )
    
    # === ДОПОЛНИТЕЛЬНО ===
    procedure_name: str | None = Field(
        default=None,
        description="Название процедуры/исследования (для diagnostic)"
    )
    notes: str | None = Field(
        default=None,
        description="Дополнительные заметки, не вошедшие в другие поля"
    )
```

### 2.3 Маппинг schema_id → поля

| schema_id | Основные поля | Второстепенные |
|-----------|---------------|----------------|
| `lab` | `measurements[]` | `notes` |
| `diagnostic` | `measurements[]`, `findings[]`, `conclusion` | `procedure_name`, `diagnoses[]` |
| `consultation` | `findings[]`, `diagnoses[]`, `recommendations[]` | `medications[]` |
| `medication_trace` | `medications[]` | `recommendations[]`, `notes` |

### 2.4 Задачи Фазы 2 ✅ DONE

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 2.1 | Создать `MedicalDoc` модель | `flows/pec/models.py` | ✅ DONE |
| 2.2 | Добавить `MedicalDoc.merge()` | `flows/pec/models.py:582-655` | ✅ DONE |
| 2.3 | Обновить `StepResult` модель с `doc` полем | `flows/pec/models.py:136-153` | ✅ DONE |
| 2.4 | Создать `RunContext` с `doc` и `add_doc()` | `flows/pec/models.py:663-708` | ✅ DONE |

---

## Фаза 3: Executor

### 3.1 Текущее состояние

```python
# flows/pec/ocr_executor.py (текущее)
resp = await self._llm.chat(ChatRequest(...))
return StepResult(
    step_id=step.id,
    executor="ocr",
    content=resp.text.strip(),  # ← сырой YAML string
)
```

### 3.2 Целевое состояние

```python
# flows/pec/ocr_executor.py (после рефакторинга)
doc = await self._llm.chat_structured(
    ChatRequest(...),
    response_model=MedicalDoc,
    max_retries=self._max_retries,
)
return StepResult(
    step_id=step.id,
    executor="ocr",
    doc=doc,  # ← типизированный объект
)
```

### 3.3 Изменения в Orchestrator
Orchestrator делает инкрементальный merge после каждого шага:

```python
class Orchestrator:
    async def run(self, file_path: str, doc_content: str) -> OcrResult:
        runCtx = RunContext(user_request=file_path, document_content=doc_content)
        await self.plan(runCtx)

        if runCtx.status == RunStatus.SKIPPED:
            return ...

        # 1. Execute все шаги (executor, без critic)
        await self.execute(runCtx)

        # 2. Review (critic) — после всех шагов
        await self.critic(runCtx)

        return OcrResult(...)
```

Critic вызывается ПОСЛЕ всех шагов, но (пока) проверяет каждый step_result отдельно.

### 3.4 Executor возвращает StepResult с типизированным doc

```python
class OcrExecutor:
    async def execute(self, context: RunContext, step_id: int) -> StepResult:
        """Выполнить шаг и вернуть типизированный результат."""

        # ... render prompts ...

        doc: MedicalDoc = await self._llm.chat_structured(
            ChatRequest(messages=[...]),
            response_model=MedicalDoc,
            max_retries=self._max_retries,
        )

        return StepResult(
            step_id=step.id,
            executor="ocr",
            doc=doc,
        )
```

**Примечание:** Executor возвращает `StepResult` с типизированным `doc`. Merge выполняется в orchestrator.

### 3.4 Обновление промптов

**`prompts/ocr_executor/system.md`:**

```markdown
Role: Executor

You extract structured medical data from documents.

## Your Task

1. Read the document content carefully
2. Extract ALL relevant medical information
3. Preserve values EXACTLY as written (dates, numbers, units)
4. Return structured JSON matching the schema

## Extraction Rules

- Copy numeric values exactly as written (e.g., "140", not "140.0")
- Copy dates exactly as written (e.g., "09.02.2020", not "2020-02-09")
- Copy measurement units exactly (e.g., "г/л", "мм")
- Do NOT invent or assume missing values — use null
- Do NOT normalize or convert units

## What to Extract by Document Type

| schema_id | Focus on |
|-----------|----------|
| lab | measurements (analytes, values, units, reference ranges) |
| diagnostic | measurements (organ sizes), findings (descriptions), conclusion |
| consultation | findings (examination), diagnoses, recommendations, medications |
| medication_trace | medications (name, dosage, frequency, duration) |

## Output Format

Respond with JSON matching the MedicalDoc schema.
```

**`prompts/ocr_executor/user.md`:**

```markdown
Extract medical data from this document.

## Context

- Schema ID: {{ACTIVE_SCHEMA}}
- Step: {{STEP_TITLE}}

## Document Content

{{DOCUMENT_CONTENT}}

## Previous Extraction Results

{{PREVIOUS_RESULTS}}

## Critic Feedback (if retry)

{{CRITIC_FEEDBACK}}

## Task

Extract all relevant medical data into structured JSON.
Focus on fields relevant for schema_id "{{ACTIVE_SCHEMA}}".

Respond with valid JSON.
```

### 3.5 Задачи Фазы 3 ✅ DONE

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 3.1 | Рефакторинг `OcrExecutor.execute()` на `chat_structured()` | `flows/pec/ocr_executor.py:94-102` | ✅ DONE |
| 3.2 | Обновить `StepResult` модель | `flows/pec/models.py:136-153` | ✅ DONE |
| 3.3 | Обновить system.md | `prompts/ocr_executor/system.md` | ✅ DONE |
| 3.4 | Обновить user.md | `prompts/ocr_executor/user.md` | ✅ DONE |
| 3.5 | Инкрементальный merge в orchestrator | `flows/pec/orchestrator.py:98` | ✅ DONE |
| 3.6 | Обновить `build_pec.py` (max_retries) | `flows/pec/build_pec.py` | ✅ DONE |
| 3.7 | Тесты | `tests/` | ⬜ (опционально) |

---

## Фаза 4: Critic

### 4.1 Что уже сделано / Что осталось

**DONE — `flows/pec/critic.py` переделан:**

```python
# Новая сигнатура — только RunContext, без StepResult
async def review(self, context: RunContext) -> CriticResult:
    ...
    return await self._llm.chat_structured(
        ChatRequest(messages=[...]),
        response_model=CriticResult,
    )
# load_llm_yaml, SchemaCatalog — удалены
```

**DONE — `flows/pec/renderer.py`:**
- `render_critic_final_template(context, template)` — добавлена
- `render_critic_template(context, step, result, template)` — удалена
- Агрегирует `success_criteria` всех шагов, передаёт `context.doc` как JSON

**ОСТАЛОСЬ — `flows/pec/orchestrator.py:104-141` — ВСЕГДА НЕПРАВИЛЬНО:**

```python
# orchestrator.py (сейчас — НЕПРАВИЛЬНО, надо исправить)
for step_result in context.steps_results:
    verdict = await self._critic.review(context, step_result)  # ← старая сигнатура!
```

**ОСТАЛОСЬ — промпты:**
```
# prompts/critic/system.md — всё ещё требует YAML вывод
# prompts/critic/user.md — всё ещё минимальный, ссылается на {{STEP}}
```

### 4.2 Целевое состояние

```python
# flows/pec/critic.py (после рефакторинга) — УЖЕ РЕАЛИЗОВАНО
return await self._llm.chat_structured(
    ChatRequest(...),
    response_model=CriticResult,
)
```

### 4.3 Изменения в Critic

1. Перейти на `chat_structured()` с `CriticResult`
2. Изменить вызов — **один раз** после всех шагов
3. Проверять **финальный merged** `context.doc` (не пошагово)
4. При неудаче — отправлять на retry/replan

```python
# orchestrator.py (целевой вариант — ЕЩЁ НЕ РЕАЛИЗОВАН)
async def critic(self, context: RunContext) -> None:
    """Проверить финальный merged документ — один вызов после всех шагов."""
    if context.plan is None:
        raise ValueError("RunContext.plan is required for review")
    if not context.steps_results:
        raise ValueError("No step results to review")

    verdict = await self._critic.review(context)  # только context, без step_result
    context.critic_feedback = verdict.issues
    context.status = RunStatus.COMPLETED if verdict.approved else RunStatus.FAILED

    if verdict.approved:
        log.info("Critic approved: %s", verdict.summary)
    else:
        log.error("Critic rejected: %s", verdict.summary)
```

### 4.4 CLI интеграция (уже реализовано)

Critic можно вызывать из CLI отдельно для отладки:

```bash
# Полный pipeline
advisor ocr-flow document.txt

# Пошагово (для отладки)
advisor plan "лабораторный анализ" > context.yaml
advisor exec context.yaml > context.yaml
advisor critic context.yaml > context.yaml
```

**CLI команды** (`cli/commands/critic.py`):
- Вход: `context.yaml` с заполненными `plan` и `steps_results`
- Выход: обновлённый `context.yaml` с `status` и `critic_feedback`

Это позволяет отлаживать Critic изолированно от остального pipeline.

### 4.4 Обновление промптов

**Текущее:** `prompts/critic/system.md` требует YAML-вывод:
```
Output rules
- Return ONLY valid YAML.
- No JSON.
```

**Изменить на:**
```
Output rules
- Return valid JSON.
- No YAML.
- No markdown fences.
```

**`prompts/critic/user.md`:** изменить `{{STEP_RESULT}}` на `{{FINAL_DOC}}` (финальный merged doc).

### 4.5 ЧТО НЕ ДЕЛАТЬ при реализации Critic

**Методов и переменных которых НЕ СУЩЕСТВУЕТ — не использовать:**

- `context.final_extraction` — нет такого поля. Правильно: `context.doc`
- `critic.review_final(context, final_doc)` — нет такого метода. Правильно: `critic.review(context)`
- `RunStatus.NEEDS_RETRY` — нет такого статуса. Правильно: `RunStatus.FAILED`
- `render_critic_template(context, step, result, template)` — УДАЛЕНА. Правильно: `render_critic_final_template(context, template)`
- `load_llm_yaml()` — удалена из critic.py. Не импортировать снова.

**Архитектурные запреты:**

- НЕ вызывать `critic.review()` в цикле по `step_results` — только ОДИН вызов после всех шагов
- НЕ передавать `StepResult` в `critic.review()` — новая сигнатура принимает только `RunContext`
- НЕ добавлять `schema_catalog` в `Critic.__init__` — было удалено, не нужно
- НЕ добавлять `max_retries` в `Critic.__init__` — не планируется в текущей фазе
- НЕ возвращать к YAML-парсингу в critic — только `chat_structured()`

---

### 4.6 Задачи Фазы 4 (В ПРОЦЕССЕ)

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 4.1 | Рефакторинг `Critic.review()` на `chat_structured()` | `flows/pec/critic.py` | ✅ DONE |
| 4.2 | Убрать `load_llm_yaml`, `SchemaCatalog` из critic.py | `flows/pec/critic.py` | ✅ DONE |
| 4.3 | Добавить `render_critic_final_template()`, удалить старую | `flows/pec/renderer.py` | ✅ DONE |
| 4.4 | Исправить `orchestrator.critic()` — один вызов на `context.doc` | `flows/pec/orchestrator.py:104-141` | ⬜ |
| 4.5 | Обновить system.md — JSON вместо YAML | `prompts/critic/system.md` | ⬜ |
| 4.6 | Обновить user.md — финальный doc, агрегированные критерии | `prompts/critic/user.md` | ⬜ |
| 4.7 | Написать тесты | `tests/` | ⬜ (опционально) |
| 4.8 | CLI интеграция | `cli/commands/critic.py` | ✅ УЖЕ ЕСТЬ |

---

## Фаза 5: Сохранение RunContext

### 5.1 Проблема: Множественные шаги → множественные extractions

```
Planner создаёт 3 шага:
  Step 1: Extract patient info
  Step 2: Extract measurements  
  Step 3: Extract conclusion

Executor возвращает 3 × MedicalDoc:
  extraction_1: {patient: {...}, measurements: []}
  extraction_2: {patient: null, measurements: [...]}  
  extraction_3: {conclusion: "...", recommendations: [...]}

Нужен ОДИН финальный объект для БД!
```

### 5.2 Решение: Инкрементальный merge после каждого шага

**Почему инкрементальный merge лучше:**

| Merge в конце | Инкрементальный merge |
|---------------|------------------------|
| Хранить `list[MedicalDoc]` | Хранить один `MedicalDoc` |
| Merge только перед Critic | Merge сразу после каждого шага |
| `final_extraction` — computed | `doc` — актуальный документ |
| Сложнее отладка | Всегда видно текущее состояние |

**Flow:**

```
Executor(шаг 1) → ext_1 → context.doc = ext_1
                              ↓
Executor(шаг 2) → ext_2 → context.doc = doc.merge(ext_2)
                              ↓
Executor(шаг 3) → ext_3 → context.doc = doc.merge(ext_3)
                              ↓
                   context.doc = {полный объект}
                              ↓
                         Critic (один раз)
                              ↓
                         Save to DB
```

### 5.3 MedicalDoc.merge()

```python
class MedicalDoc(BaseModel):
    # ... existing fields ...
    
    def merge(self, other: "MedicalDoc") -> "MedicalDoc":
        """Объединить два извлечения в одно.
        
        Стратегия:
        - schema_id: берём из self (должны совпадать)
        - Скалярные поля: берём non-null, приоритет у other (более поздний)
        - Списки: конкатенация с дедупликацией
        """
        return MedicalDoc(
            schema_id=self.schema_id,
            
            # Document: merge fields
            document=DocumentInfo(
                date=other.document.date or self.document.date,
                organization=other.document.organization or self.document.organization,
                doctor=other.document.doctor or self.document.doctor,
                specialty=other.document.specialty or self.document.specialty,
            ),
            
            # Patient: merge fields  
            patient=PatientInfo(
                full_name=other.patient.full_name or self.patient.full_name,
                birth_date=other.patient.birth_date or self.patient.birth_date,
                gender=other.patient.gender or self.patient.gender,
            ),
            
            # Lists: concatenate and deduplicate
            measurements=self._merge_measurements(self.measurements, other.measurements),
            findings=self._unique_list(self.findings + other.findings),
            diagnoses=self._unique_list(self.diagnoses + other.diagnoses),
            recommendations=self._unique_list(self.recommendations + other.recommendations),
            medications=self._merge_medications(self.medications, other.medications),
            
            # Scalars: prefer later non-null
            conclusion=other.conclusion or self.conclusion,
            procedure_name=other.procedure_name or self.procedure_name,
            notes=self._merge_notes(self.notes, other.notes),
        )
    
    @staticmethod
    def _unique_list(items: list[str]) -> list[str]:
        """Дедупликация с сохранением порядка."""
        seen = set()
        return [x for x in items if not (x in seen or seen.add(x))]
    
    @staticmethod
    def _merge_measurements(a: list[Measurement], b: list[Measurement]) -> list[Measurement]:
        """Объединить измерения, дедупликация по name."""
        by_name = {m.name: m for m in a}
        for m in b:
            by_name[m.name] = m  # later wins
        return list(by_name.values())
    
    @staticmethod
    def _merge_medications(a: list[Medication], b: list[Medication]) -> list[Medication]:
        """Объединить препараты, дедупликация по name."""
        by_name = {m.name: m for m in a}
        for m in b:
            by_name[m.name] = m
        return list(by_name.values())
    
    @staticmethod
    def _merge_notes(a: str | None, b: str | None) -> str | None:
        """Объединить заметки через newline."""
        parts = [x for x in [a, b] if x]
        return "\n".join(parts) if parts else None
```

### 5.4 Финальная структура RunContext

```python
@dataclass
class RunContext:
    """Shared state passed through the PEC pipeline."""

    # === INPUT (immutable) ===
    user_request: str
    document_content: str

    # === PLANNING ===
    plan: PlanResult | None = None
    active_schema: str | None = None

    # === EXECUTION ===
    steps_results: list[StepResult] = field(default_factory=list)  # результаты по шагам
    doc: MedicalDoc | None = None  # накопленный merged документ

    # === REVIEW ===
    critic_feedback: list[CriticIssue] = field(default_factory=list)

    # === STATUS ===
    status: RunStatus = RunStatus.PENDING
    retry_count: int = 0
```

**Примечание:** Merge выполняется в orchestrator.py:98:
```python
context.doc = context.doc.merge(result.doc) if context.doc else result.doc
```

### 5.5 Сериализация

```python
def save_run_context(context: RunContext, path: Path) -> None:
    """Сохранить RunContext в JSON файл."""
    data = {
        "user_request": context.user_request,
        "document_content": context.document_content,
        "plan": context.plan.model_dump() if context.plan else None,
        "active_schema": context.active_schema,
        
        # Сохраняем актуальный документ (уже merged)
        "doc": context.doc.model_dump() if context.doc else None,
        
        # Метаданные
        "status": context.status.value,
        "retry_count": context.retry_count,
        "started_at": context.started_at.isoformat() if context.started_at else None,
        "completed_at": context.completed_at.isoformat() if context.completed_at else None,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

### 5.6 Пример работы инкрементального merge

```
Шаг 1 → extraction_1:
  patient: {full_name: "Иванов И.И.", birth_date: "1971-02-23"}
  measurements: []
  
Шаг 2 → extraction_2:
  patient: {full_name: null, birth_date: null}
  measurements: [{name: "Гемоглобин", value: "140", unit: "г/л"}]
  
Шаг 3 → extraction_3:
  patient: {full_name: null, birth_date: null}
  conclusion: "Норма"
  recommendations: ["Повторный анализ через 6 мес."]

Финальный merge:
  patient: {full_name: "Иванов И.И.", birth_date: "1971-02-23"}  ← из шага 1
  measurements: [{name: "Гемоглобин", value: "140", unit: "г/л"}]  ← из шага 2
  conclusion: "Норма"  ← из шага 3
  recommendations: ["Повторный анализ через 6 мес."]  ← из шага 3
```

### 5.7 Задачи Фазы 5 (ЧАСТИЧНО РЕАЛИЗОВАНО)

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 5.1 | `MedicalDoc.merge()` | `flows/pec/models.py:582-655` | ✅ DONE |
| 5.2 | `RunContext` с `doc` и `steps_results` | `flows/pec/models.py:663-708` | ✅ DONE |
| 5.3 | Сериализация `run_context_to_yaml()` | `flows/pec/models.py:780-786` | ✅ DONE |
| 5.4 | Десериализация `load_run_context()` | `flows/pec/models.py:811-812` | ✅ DONE |
| 5.5 | Тесты на merge | `tests/test_medical_doc_merge.py` | ⬜ (опционально) |
| 5.6 | Интеграция с БД (опционально) | `db/` | ⬜ |
| 5.7 | CLI команда для просмотра результатов | `cli/commands/` | ⬜ |

---

## Сводная таблица изменений

| Фаза | Файлы | Оценка |
|------|-------|--------|
| 2. Универсальная схема | `flows/pec/schemas/medical_doc.py`, `models.py` | 1-2 часа |
| 3. Executor | `ocr_executor.py`, `prompts/ocr_executor/*`, `mock_scenarios.py` | 2-3 часа |
| 4. Critic | `critic.py`, `prompts/critic/*`, `renderer.py` | 2 часа |
| 5. RunContext | `models.py`, `db/`, CLI | 1-2 часа |
| **Итого** | | **6-9 часов** |

---

## Диаграмма данных (фактическое поведение vs целевое)

### Как сейчас (НЕПРАВИЛЬНО):

```
Executor → [step1, step2, step3] → steps_results[]
                                    ↓
                              context.doc (merged)
                                    ↓
Critic → for step in steps_results:
          review(step_result)  ← проверяет отдельно!
```

### Как должно быть (после Фазы 4):

```
┌──────────────┐
│   Planner    │ ←──── retry с feedback
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Executor   │ ──▶ steps_results[] ──▶ context.doc (merged)
└──────┬───────┘
       │
       ▼
┌──────────────┐    context.doc    ┌──────────────────┐
│    Critic    │ ──▶ (final) ──▶ │ COMPLETED / FAIL │
│  (один раз)  │                  │  (retry/replan)  │
└──────────────┘                  └──────────────────┘
```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Planner    │────▶│  PlannerOutputSchema │────▶│    PlanResult    │
│              │     │  (instructor)        │     │   steps=[1,2,3]  │
└──────────────┘     └─────────────────────┘     └─────────┬────────┘
                                                        │
                    ┌──────────────────────────────────┴─────────────────┐
                    │                                                     │
        ┌───────────┴────────────────────────────────────────────────────┐
        │                        ORCHESTRATOR LOOP                        │
        │                                                                  │
        │   for step in plan.steps:                                        │
        │       ext = executor.execute(step)                               │
        │       context.add_extraction(ext)  ←── инкрементальный merge     │
        │                                                                  │
        └──────────────────────────────────────────────────────────────────┘
                                        │
        ┌────────────────────────────────┴────────────────────────────────┐
        │                                                                  │
        │  Step 1: Executor → ext_1 {patient}                             │
        │          context.doc = ext_1                                    │
        │                     ↓                                            │
        │  Step 2: Executor → ext_2 {measurements}                        │
        │          context.doc = ext_1.merge(ext_2)                       │
        │                     ↓                                            │
        │  Step 3: Executor → ext_3 {conclusion}                          │
        │          context.doc = merged.merge(ext_3)                      │
        │                     ↓                                            │
        │  context.doc = {полный объект}                           │
        │                                                                  │
        └──────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                ┌────────────────────────┐     ┌──────────────────┐
                │        Critic          │────▶│   CriticResult   │
                │ review(context.doc)    │     │ approved/issues  │
                └────────────────────────┘     └─────────┬────────┘
                                                        │
                                                        ▼
                                              ┌──────────────────┐
                                              │   JSON / DB      │
                                              │    context.doc    │
                                              └──────────────────┘
```

---

## CLI интерфейс (пошаговое выполнение)

Каждый компонент PEC pipeline доступен из CLI отдельно для отладки:

```bash
# 1. Plan — создать план из запроса
advisor plan "лабораторный анализ крови" > context.yaml
# Выход: context.yaml с plan, schema_name, steps[]

# 2. Exec — выполнить шаги без critic
advisor exec context.yaml > context.yaml
# Вход: context.yaml с plan
# Выход: context.yaml с steps_results[], doc (merged)

# 3. Critic — проверить результаты
advisor critic context.yaml > context.yaml
# Вход: context.yaml с steps_results, doc
# Выход: context.yaml с status, critic_feedback[]

# 4. OCR Flow — полный pipeline (plan + exec + critic)
advisor ocr-flow document.txt
```

**Команды:**
- `cli/commands/plan.py` — создание плана
- `cli/commands/exec.py` — выполнение шагов
- `cli/commands/critic.py` — проверка результатов
- `cli/commands/ocr_flow.py` — полный pipeline

**Паттерн:** Каждая команда читает `RunContext` из YAML, выполняет свой этап, выводит обновлённый `RunContext` в YAML. Это позволяет:
- Отлаживать каждый этап изолированно
- Вмешиваться в процесс между этапами
- Повторно использовать промежуточные результаты

---

## Критерии готовности
### Фаза 2 ✅ DONE:
- [x] `MedicalDoc` модель создана (в `flows/pec/models.py:406`)
- [x] `MedicalDoc.merge()` реализован (в `flows/pec/models.py:582`)
- [x] `RunContext` создан с полями `doc`, `steps_results` (в `flows/pec/models.py:663`)

### Фаза 3 ✅ DONE:
- [x] Executor использует `chat_structured()` с `MedicalDoc` (`flows/pec/ocr_executor.py:94`)
- [x] Инкрементальный merge работает (`flows/pec/orchestrator.py:98`)
- [x] Промпты обновлены на JSON
- [ ] Unit тесты проходят (опционально)

### Фаза 4 ⏳ В ПРОЦЕССЕ:
- [x] `Critic.review(context)` использует `chat_structured(response_model=CriticResult)` (`flows/pec/critic.py`)
- [x] `load_llm_yaml` и `SchemaCatalog` удалены из `critic.py`
- [x] `render_critic_final_template()` добавлена в `renderer.py`, старая удалена
- [ ] `Orchestrator.critic()` — один вызов `critic.review(context)`, без цикла (`flows/pec/orchestrator.py:104-141`)
- [ ] `prompts/critic/system.md` — JSON формат, без YAML
- [ ] `prompts/critic/user.md` — финальный merged doc, агрегированные success_criteria
- [x] CLI команда `advisor critic` уже есть (`cli/commands/critic.py`)
- [ ] Unit тесты (опционально)

### Фаза 5 ⏳ PARTIAL:
- [x] RunContext сохраняется/загружается корректно (`run_context_to_yaml`, `load_run_context`)
- [x] Интеграция с моделями работает
- [ ] CLI команда для просмотра результатов
- [ ] Интеграционный тест полного pipeline
