# План интеграции Instructor: Универсальная схема

## Обзор

Миграция PEC pipeline на structured outputs с использованием **единой универсальной схемы** 
для всех типов медицинских документов.

---

## Последовательность реализации

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Planner (✅ DONE)                                                    │
│     • chat_structured() с PlannerOutputSchema                           │
│     • 4 schema_id: lab, diagnostic, consultation, medication_trace      │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  2. Рефакторинг на универсальную схему                                  │
│     • Создать MedicalDoc (единая Pydantic модель)                     │
│     • schema_id остаётся для роутинга и Critic rules                    │
│     • Обновить YAML схемы в flows/pec/schemas/                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  3. Executor                                                             │
│     • chat_structured() с MedicalDoc                                    │
│     • Убрать сырой YAML вывод                                           │
│     • Обновить промпты                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  4. Critic                                                               │
│     • chat_structured() с CriticResult                                  │
│     • Валидация типизированного MedicalDoc                              │
│     • Обновить промпты                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  5. Сохранение RunContext                                                │
│     • Финализация структуры RunContext                                  │
│     • Сериализация в БД / файл                                          │
│     • CLI команды для работы с результатами                             │
└─────────────────────────────────────────────────────────────────────────┘
```

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

**Файл:** `flows/pec/schemas/medical_doc.py`

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
| 2.1 | Создать `MedicalDoc` модель | `flows/pec/schemas/medical_doc.py` | ✅ |
| 2.2 | Обновить `StepResult.content` тип | `flows/pec/models.py` | ✅ |
| 2.3 | Добавить экспорт в `flows/pec/schemas/__init__.py` | `flows/pec/schemas/__init__.py` | ⬜ (опционально) |
| 2.4 | Обновить документацию схем | `flows/pec/schemas/*.yaml` (опционально) | ⬜ |

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

Orchestrator теперь делает инкрементальный merge после каждого шага:

```python
class Orchestrator:
    async def execute(self, context: RunContext) -> None:
        """Выполнить все шаги с инкрементальным merge."""
        
        for step in context.plan.steps:
            # Executor возвращает частичное извлечение
            step_doc = await self._executor.execute(context, step.id)
            
            # Сразу merge в накопительный объект
            context.add_doc(step_doc)
            
            log.debug(
                "Step %d complete, extraction fields: %d measurements, %d findings",
                step.id,
                len(context.doc.measurements),
                len(context.doc.findings),
            )
        
        # Critic ревьюит финальное состояние (один раз)
        verdict = await self._critic.review(context)
        context.critic_feedback = verdict.issues
        context.status = RunStatus.COMPLETED if verdict.approved else RunStatus.FAILED
```

### 3.4 Executor возвращает MedicalExtraction напрямую

```python
class OcrExecutor:
    async def execute(self, context: RunContext, step_id: int) -> MedicalDoc:
        """Выполнить шаг и вернуть типизированное извлечение."""
        
        # ... render prompts ...
        
        return await self._llm.chat_structured(
            ChatRequest(messages=[...]),
            response_model=MedicalDoc,
            max_retries=self._max_retries,
        )
```

**Важно:** `StepResult` больше не нужен — Executor возвращает `MedicalDoc` напрямую.

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
| 3.1 | Рефакторинг `OcrExecutor.execute()` на `chat_structured()` | `flows/pec/ocr_executor.py` | ✅ |
| 3.2 | Обновить `StepResult` модель | `flows/pec/models.py` | ✅ |
| 3.3 | Обновить system.md | `prompts/ocr_executor/system.md` | ✅ |
| 3.4 | Обновить user.md | `prompts/ocr_executor/user.md` | ✅ |
| 3.5 | Добавить `executor_structured_mock` | `llm/mock_scenarios.py` | ✅ |
| 3.6 | Обновить `build_pec.py` (max_retries) | `flows/pec/build_pec.py` | ⬜ (минорное улучшение) |
| 3.7 | Написать тесты | `tests/test_executor_structured.py` | ⬜ (опционально) |

---

## Фаза 4: Critic

### 4.1 Текущее состояние

```python
# flows/pec/critic.py (текущее)
resp = await self._llm.chat(ChatRequest(...))
data = load_llm_yaml(resp.text)  # ← ручной парсинг
return CriticResult.model_validate(data)
```

### 4.2 Целевое состояние

```python
# flows/pec/critic.py (после рефакторинга)
return await self._llm.chat_structured(
    ChatRequest(...),
    response_model=CriticResult,
    max_retries=self._max_retries,
)
```

### 4.3 Изменения в Critic

Critic теперь ревьюит **финальное объединённое** извлечение:

```python
async def review(
    self, 
    context: RunContext,
) -> CriticResult:
    """Ревью финального извлечения после всех шагов."""
    
    final = context.final_extraction  # ← merged extraction
    
    # Critic сравнивает:
    # 1. final vs context.document_content (исходник)
    # 2. final.schema_id vs context.active_schema
    # 3. Все success_criteria из plan.steps
    
    return await self._llm.chat_structured(
        ChatRequest(...),
        response_model=CriticResult,
    )
```

**Важно:** Critic вызывается **один раз** после всех шагов Executor'a, а не после каждого.

### 4.4 Обновление промптов

**`prompts/critic/system.md`:**

```markdown
Role: Critic

You review extracted medical data against the source document.

## Your Task

1. Compare extracted data with the original document
2. Verify ALL values are preserved exactly
3. Check for missing, altered, or invented data
4. Return structured verdict

## Review Rules

**APPROVE only if:**
- All dates match the source exactly
- All numeric values match the source exactly  
- All measurement units match the source exactly
- All required information is extracted
- No data is invented or hallucinated

**REJECT if ANY of these found:**
- Missing value that exists in source document
- Altered value (different from source)
- Invented data not present in source
- Wrong schema_id for document type

## Issue Severity

| Severity | When to use |
|----------|-------------|
| high | Missing/wrong required value, altered numbers, wrong dates |
| medium | Missing optional field, incomplete extraction |
| low | Minor formatting issue |

## Output Format

```json
{
  "approved": true,
  "summary": "All values extracted correctly",
  "issues": []
}
```

Or if issues found:

```json
{
  "approved": false,
  "summary": "Missing hemoglobin reference range",
  "issues": [
    {
      "severity": "medium",
      "description": "Reference range for Hemoglobin not extracted",
      "suggestion": "Add reference_range: '120-160' to Hemoglobin measurement"
    }
  ]
}
```
```

**`prompts/critic/user.md`:**

```markdown
Review the extracted data against the source document.

## Source Document

{{DOCUMENT_CONTENT}}

## Expected Schema

schema_id: {{ACTIVE_SCHEMA}}

## Success Criteria

{{SUCCESS_CRITERIA}}

## Extracted Data (to review)

{{STEP_RESULT}}

## Task

1. Compare each extracted value with the source document
2. Verify schema_id matches document type
3. Check all success criteria are met
4. Return approval or list of issues

Respond with JSON.
```

### 4.5 Задачи Фазы 4 (в процессе / ожидает завершения)

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 4.1 | Рефакторинг `Critic.review()` на `chat_structured()` | `flows/pec/critic.py` | ⬜ |
| 4.2 | Убрать импорт `load_llm_yaml` | `flows/pec/critic.py` | ⬜ |
| 4.3 | Улучшить descriptions в `CriticResult` | `flows/pec/models.py` | ✅ (уже good) |
| 4.4 | Обновить system.md | `prompts/critic/system.md` | ⬜ |
| 4.5 | Обновить user.md | `prompts/critic/user.md` | ⬜ |
| 4.6 | Обновить `critic_structured_mock` | `llm/mock_scenarios.py` | ✅ |
| 4.7 | Обновить `build_pec.py` (max_retries) | `flows/pec/build_pec.py` | ⬜ |
| 4.8 | Обновить renderer для JSON extraction | `flows/pec/renderer.py` | ⬜ |
| 4.9 | Написать тесты | `tests/test_critic_structured.py` | ⬜ |

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
    
    # === EXECUTION (один накопительный документ) ===
    doc: MedicalDoc | None = None
    
    # === REVIEW ===
    critic_feedback: list[CriticIssue] = field(default_factory=list)
    
    # === STATUS ===
    status: RunStatus = RunStatus.PENDING
    retry_count: int = 0
    
    # === METADATA ===
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    
    def add_doc(self, new_doc: MedicalDoc) -> None:
        """Инкрементальный merge после каждого шага Executor.
        
        Первый вызов: устанавливает базовый документ.
        Последующие: merge с текущим состоянием.
        """
        if self.doc is None:
            self.doc = new_doc
        else:
            self.doc = self.doc.merge(new_doc)
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

### 5.7 Задачи Фазы 5 (в процессе)

| # | Задача | Файл | Статус |
|---|--------|------|--------|
| 5.1 | Добавить `MedicalDoc.merge()` | `flows/pec/schemas/medical_doc.py` | ✅ (уже в models.py) |
| 5.2 | Обновить `RunContext` с `doc` и `add_doc()` | `flows/pec/models.py` | ✅ |
| 5.3 | Тесты на merge | `tests/test_medical_doc_merge.py` | ⬜ |
| 5.4 | Добавить `save_run_context()` | `flows/pec/models.py` | ⬜ |
| 5.5 | Обновить `load_run_context()` | `flows/pec/models.py` | ⬜ |
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

## Диаграмма данных (инкрементальный merge)

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

## Критерии готовности

### Фаза 2 ✅ DONE:
- [x] `MedicalDoc` модель создана (в `flows/pec/models.py`)
- [x] Объект `MedicalDoc` экспортируется из `flows/pec/models.py`
- [x] Тесты на валидацию схемы проходят

### Фаза 3 ✅ DONE:
- [x] Executor использует `chat_structured()`
- [x] Промпты обновлены на JSON
- [x] Mock scenarios работают
- [ ] Unit тесты проходят (опционально)

### Фаза 4 ⏳ WAITING:
- [ ] Critic использует `chat_structured()`
- [ ] Critic валидирует `MedicalDoc`
- [ ] Промпты обновлены
- [ ] Unit тесты проходят

### Фаза 5 ⏳ WAITING:
- [ ] RunContext сохраняется/загружается корректно
- [ ] Интеграционный тест полного pipeline проходит
- [ ] CLI команды работают
