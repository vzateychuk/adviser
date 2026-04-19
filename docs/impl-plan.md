# План реализации Advisor Strategy System (статус + следующие шаги)

Формат: этапы → шаги → ожидаемый результат.  
Цель: двигаться маленькими инкрементами, каждый шаг даёт проверяемый результат (CLI/тесты/артефакты).

---

## Этап 0 — Базовая инфраструктура

### Шаг 0.0 — Скелет проекта, запуск, README, Hello world  
**Статус:** ✅ выполнено  
**Результат:** проект запускается через `uv run advisor`, есть базовый README.

### Шаг 0.1 — Переключение окружений через `--env` (dev/prod/test)  
**Статус:** ✅ выполнено  
**Результат:** приложение стартует с указанной средой выполнения через CLI.

### Шаг 0.2 — Логирование и подключение к SQLite  
**Статус:** ✅ выполнено  
**Результат:** есть базовое логирование (с file:line) и SQLite; при запуске создаётся БД и пишется запись о запуске.

### Шаг 0.3 — Загрузка конфигов по окружению + Pydantic-валидация  
**Статус:** ✅ выполнено  
**Результат:** `models.yaml` грузится из `config/<env>/`, валидируется; есть тесты на загрузку и smoke запуск CLI.

---

## Этап 1 — Базовый LLM слой (vendor-agnostic)

### Шаг 1.0 — Нейтральные типы сообщений + интерфейс клиента (LLMClient) + Mock  
**Статус:** ✅ выполнено  
**Результат:** есть внутренний “контракт” для сообщений и запросов; есть `MockLLMClient` и тест на него.

### Шаг 1.1 — Реальный LLM клиент через LiteLLM proxy (Messages API, без streaming)  
**Статус:** ✅ выполнено  
**Результат:** OpenAI-compatible LLM adapter добавлен, коммит `a93acd7`. В dev/prod выполняется запрос к LLM через LiteLLM proxy.

### Шаг 1.2 — Выбор LLM реализации по env  
**Статус:** ✅ выполнено  
**Результат:** env-based LLM selection + ask command + tests, коммит `ea0f2ad`. `--env test` → mock; `--env dev/prod` → реальный LiteLLM-адаптер.

---

## Этап 2 — Prompts + агентные роли + структурированные артефакты

### Шаг 2.0 — Prompts для ролей из файловой системы (FS)  
**Статус:** ✅ выполнено  
**Результат:**  
- директория `prompts/` существует  
- для ролей (clarifier/planner/generic_executor/code_executor/critic) есть текстовые prompt-файлы  
- единый механизм загрузки: `load_role_prompt(role)` + `render_template(template, values)` в `tools/prompts.py`  
- путь к `prompts/` резолвится относительно пакета, не зависит от CWD

### Шаг 2.1 — Structured артефакты (Pydantic модели) для Plan/Step/Critique  
**Статус:** ✅ выполнено  
**Результат:** `flows/pec/models.py` содержит `PlanResult`, `PlanStep`, `StepResult`, `CriticResult`, `CriticIssue`; инварианты защищены model_validator'ами.

### Шаг 2.2 — Planner: генерирует план в JSON, валидируется  
**Статус:** ✅ выполнено  
**Результат:** planner возвращает валидный `PlanResult`; prompt загружается из `prompts/planner.md`.

### Шаг 2.3 — Executors: GenericExecutor и CodeExecutor  
**Статус:** ✅ выполнено  
**Результат:** два executor'а работают по одному интерфейсу, принимают `PlanStep`, возвращают `StepResult`.

## Этап 2.4 — Critic

**Статус:** ✅ выполнено

### Результат
- critic принимает `PlanStep + StepResult`, возвращает `CriticResult`
- инвариант: `approved=False → issues непустой`
- тесты: approve/reject сценарии с MockLLMClient

---

# Этап 3 — Execution Kernel (Orchestrator-first)

## Цель
Сформировать минимальный runtime-контур:
Planner → Orchestrator → Executor → Result

Без hooks, retry, persistence и сложных state систем.

---

## 3.0 — Orchestrator MVP (execution kernel)

**Статус:** ✅ выполнено

### Функциональность
- принимает `user_request`
- вызывает Planner
- получает `PlanResult`
- последовательно выполняет шаги
- вызывает Executor (Generic / Code)
- возвращает итоговый результат

### Ограничения
- нет hooks
- нет retry
- нет persistence
- нет RunContext как сложной модели
- нет event system

### Результат
user_request → plan → execution → result

---

## 3.1 — RunContext (минимальная версия)

**Статус:** ✅ выполнено

### Назначение
Минимальный контейнер состояния выполнения.

### Поля
- run_id
- user_request
- plan
- step_results
- status

### Ограничения
- без events
- без retry counters
- без metadata graph

---

## 3.2 — Clarification Chat (preprocessing)

**Статус:** ⏳ предстоит

### Назначение
Уточняющий слой перед планированием.

### Важное место в pipeline
INPUT → CLARIFIER → ORCHESTRATOR → PLANNER

### 3.2.1 — ClarificationState
- summary: str
- key_facts: list[str]
- open_questions: list[str]
- is_ready: bool
- turn_count: int
- max_turns: int

Инвариант:
- is_ready=True несовместим с open_questions

### 3.2.2 — Prompt + роль
- prompts/clarifier.md
- добавлен в models.yaml
- placeholders: USER_REQUEST, KEY_FACTS

### 3.2.3 — ClarificationChat (v0)
- ограниченный LLM цикл
- обновление key_facts
- max_turns защита

### 3.2.4 — Интеграция с Planner
Planner получает summary + key_facts

---

## 3.3 — Critic integration (light mode)

**Статус:** ⏳ предстоит

### Функциональность
- critic вызывается после step
- возвращает CriticResult
- не влияет на retry

---

## 3.4 — Hooks (наблюдаемость)

**Статус:** ⏳ предстоит

### Hooks
- before_step
- after_step
- after_run

### Ограничения
- только наблюдение
- не влияет на execution flow

---

## 3.5 — Retry policy

**Статус:** ⏳ предстоит

### Политики
- retry TransportError
- exponential backoff
- fail-fast AuthError

### Ограничения
- вводится только после стабилизации Orchestrator

---

## 3.6 — Persistence (DB-agnostic)

**Статус:** ⏳ предстоит

### 3.6.1 — RunStore interface
- save_run_metadata
- append_event
- get_run
- list_runs

### 3.6.2 — InMemoryRunStore
- реализация на dict

### 3.6.3 — SQLiteRunStore
- runs + run_events

### 3.6.4 — Integration via hooks
- PersistenceHook
- Orchestrator не зависит от storage

### 3.6.5 — Config selection
- sqlite | in-memory

---

# Итоговая последовательность

1. 3.0 Orchestrator MVP
2. 3.1 RunContext
3. 3.2 Clarification Chat
4. 3.3 Critic integration
5. 3.4 Hooks
6. 3.5 Retry policy
7. 3.6 Persistence

# Далее пока не исправлялось, будет пересмотрено по итогам этапа 3.

---

## Этап 4 — Роутинг и конфиги для ролей (минимум)

### Шаг 4.0 — Router executor’ов по ключевым словам  
**Статус:** ⏳ предстоит  
**Результат:** выбор CodeExecutor vs GenericExecutor по простым правилам. Router — это **функция/компонент внутри оркестратора**, не отдельный агент, не отдельный LLM-вызов. Router используется в двух контекстах: (1) при входе в step — определить executor для step’а (по step.type / ключевым словам), (2) при CriticReject retry (Step 3.4) — Router получает hint "не executor X" и возвращает альтернативный executor.

### Шаг 4.1 — Связка ролей с моделями из `models.yaml` (primary/fallback)  
**Статус:** ⏳ предстоит  
**Результат:** planner/executor/critic получают правильные model alias по роли и среде через RunContext. Router также использует models.yaml fallback-список при выборе альтернативного executor’а.

---

## Этап 5 — Run history: просмотр артефактов через CLI

Persistence реализована в Stage 3.5. Stage 5 — CLI-интерфейс к данным:

### Шаг 5.0 — Команда `history` (список последних run'ов)
**Статус:** ⏳ предстоит  
**Результат:** `advisor history` выводит последние N run'ов: run_id, status, user_request (truncated), env, started_at, duration.

### Шаг 5.1 — Команда `show <run_id>` (детали run'а)
**Статус:** ⏳ предстоит  
**Результат:** вывод plan + step results + critic verdicts для конкретного run_id.

---

## Этап 6 — CLI команды продукта

### Шаг 6.0 — `list-models` (alias’ы из YAML)  
**Статус:** ⏳ предстоит  
**Результат:** отображение доступных alias моделей по окружению.

### Шаг 6.1 — `ask` (одиночный запуск orchestrator)  
**Статус:** ⏳ предстоит  
**Результат:** “один запрос → один run → сохранённые артефакты”.

### Шаг 6.2 — `chat` (интерактив)  
**Статус:** ⏳ предстоит  
**Результат:** интерактивный режим сессии (streaming добавим позже).

---

## Этап 7 — Tools (vendor-agnostic registry + security)

### Шаг 7.0 — Tool interface + Tool registry (vendor-agnostic)
**Статус:** ⏳ предстоит  
**Результат:** Protocol Tool с полями name, description, parameter_schema (JSON Schema dict), invoke callable. ToolRegistry — глобальный реестр: register(tool), get(name), list_available(). Tool schema хранится в нейтральном формате.

### Шаг 7.1 — Vendor-agnostic schema → provider format в adapter
**Статус:** ⏳ предстоит  
**Результат:** LiteLLMAdapter конвертирует нейтральный список Tool'ов в формат провайдера (OpenAI functions schema) при построении запроса. При ответе — парсит tool_call обратно в нейтральный ToolCall объект.

### Шаг 7.2 — Tool scoping в конфиге агентов
**Статус:** ⏳ предстоит  
**Результат:** каждый агент в конфиге (agents.yaml) имеет поле allowed_tools: list[str]. Orchestrator передаёт агенту только разрешённые tools. Planner не получает file_write.

### Шаг 7.3 — Tool execution layer + audit
**Статус:** ⏳ предстоит  
**Результат:** ToolExecutor.invoke(tool_call) — выполняет tool, возвращает ToolResult. Каждый tool_call и tool_result записывается как event в RunContext (через HookRunner). Ошибка в tool → возвращается как ToolResult с is_error=True, не бросается исключение.

### Шаг 7.4 — Security guardrails для shell tools
**Статус:** ⏳ предстоит  
**Результат:** CommandTool имеет allow-list допустимых команд (configurable). Опасные паттерны (rm -rf, sudo и т.д.) блокируются до исполнения. Path traversal prevention для file tools (restricted to working directory).

---

## Этап 8 — Streaming (позже)
**Статус:** ⏳ отложено  
**Результат:** streaming в LLM client + UX в CLI.

---

## Этап 9 — Документация и “готово для MVP”
**Статус:** ⏳ предстоит  
**Результат:** README с быстрым стартом, описанием env/конфигов, примерами CLI и пояснениями по архитектурным решениям.

---

## Этап 10 — Design Principle Audit (pre-MVP checklist)

**Статус:** ⏳ предстоит  

Цель: убедиться что накопленный код соответствует зафиксированным принципам из Section 0 architecture.md. Не добавляет функциональности — только проверка и точечный рефакторинг.

**Чеклист:**
- Нет импортов vendor SDK (openai, anthropic) вне директории adapters/
- Orchestrator core не вызывает RunStore напрямую (только через HookRunner)
- Все ошибки LLM-вызовов типизированы через taxonomy (TransportError / AuthError / ...)
- Каждая hook-точка покрыта хотя бы одним тестом
- Добавление нового RunStore backend (например, JSONL-файлы) не требует правок orchestrator
- Retry cap configurable и проверен тестом “хронический reject → run завершается, не зависает”
- Выбор flow (пока один) и persistence backend управляется конфигом, не флагами в коде

---

## Этап 11 — Session Management (post-MVP)

Задел на будущее: расширение MVP для поддержки долгоживущих сессий пользователя (для интерактивного режима chat и multi-turn conversations).

### Шаг 11.0 — Расширить RunContext + RunStore interface
**Статус:** ⏳ предстоит  
**Результат:**  
- RunContext получает опциональное поле `session_id: str | None`
- RunStore интерфейс расширен методами: `create_session()`, `get_session()`, `list_sessions()`, `append_session_context()`
- Backward-compatibility: старые run'ы без session_id по-прежнему работают

### Шаг 11.1 — SQLiteRunStore: таблицы sessions + расширение runs
**Статус:** ⏳ предстоит  
**Результат:**  
- новая таблица `sessions` (session_id, user_id, started_at, completed_at, status, context JSON)
- таблица `runs` расширена FK на sessions (nullable для старых run'ов)
- миграция schema без потери данных

### Шаг 11.2 — CLI команды для session management
**Статус:** ⏳ предстоит  
**Результат:**  
- `advisor chat [--session <session_id>]` — начать/продолжить сессию
- `advisor sessions list [--user <user_id>]` — история сессий
- `advisor sessions show <session_id>` — детали сессии + список run'ов

### Шаг 11.3 — Session context в planner
**Статус:** ⏳ предстоит  
**Результат:**  
- перед вызовом planner в сессии: передать history предыдущих run'ов (опционально через конфиг)
- planner может использовать контекст сессии при планировании

### Шаг 11.4 — Integration tests + session scenarios
**Статус:** ⏳ предстоит  
**Результат:**  
- e2e тест: создать сессию → выполнить несколько run'ов → проверить историю
- тест: переключение между сессиями, изоляция run'ов по session_id
