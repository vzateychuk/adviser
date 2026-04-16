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

### Шаг 2.4 — Critic (опционально)  
**Статус:** ⏳ предстоит  
**Результат:**  
- critic принимает `PlanStep + StepResult`, возвращает `CriticResult`
- инвариант: `approved=False → issues непустой` (закреплён в model_validator)
- Проверка: тест approve-сценария и reject-сценария с MockLLMClient

---

## Этап 2.6 — Clarification Chat (уточняющий диалог перед планированием)

Отдельный этап: `clarifier` — самостоятельная роль со своей моделью и prompt'ом. Запускается до Planner'а, результат передаётся в него как контекст.

### Шаг 2.6.0 — ClarificationState: Pydantic модель  
**Статус:** ⏳ предстоит  
**Результат:**  
- `ClarificationState` в `flows/pec/models.py`: summary (str), key_facts (list[str]), open_questions (list[str]), is_ready (bool), turn_count (int), max_turns (int)
- инвариант: `is_ready=True` при непустом `open_questions` не допускается (model_validator)
- Проверка: unit-тесты на валидные и невалидные данные

### Шаг 2.6.1 — Prompt clarifier'а + роль в models.yaml  
**Статус:** ⏳ предстоит  
**Результат:**  
- `prompts/clarifier.md`: роль clarifier, JSON-схема вывода `{summary, key_facts, open_questions, is_ready}`
- `clarifier` добавлен как отдельная роль в `models.yaml` (primary/fallback model alias, независимо от planner)
- Проверка: `load_role_prompt(“clarifier”)` + `render_template` заполняет `{{USER_REQUEST}}` и `{{KEY_FACTS}}`

### Шаг 2.6.2 — ClarificationChat: реализация loop'а  
**Статус:** ⏳ предстоит  
**Результат:**  
- `ClarificationChat` принимает `user_request` и `LLMClient`, возвращает `ClarificationState`
- цикл: вызов clarifier LLM → если `is_ready=false` → задать вопросы пользователю → получить ответ → обновить `key_facts` → повторить
- защита: при `turn_count >= max_turns` принудительно `is_ready=true`
- не хранит raw диалог — только `key_facts` и `summary` (anti “lost in the middle”)
- Проверка: три unit-теста с MockLLMClient:
  - сценарий A: `is_ready=true` сразу — нет вопросов
  - сценарий B: 1 раунд → `is_ready=true`
  - сценарий C: `turn_count >= max_turns` → принудительный выход, loop не зависает

### Шаг 2.6.3 — Интеграция ClarificationChat → Planner  
**Статус:** ⏳ предстоит  
**Результат:**  
- prompt `prompts/planner.md` расширен placeholder'ами `{{SUMMARY}}` и `{{KEY_FACTS}}`
- Planner получает `ClarificationState` и формирует системный промпт через `render_template`
- Проверка: end-to-end с MockLLMClient — clarification → plan; `PlanResult` содержит шаги

---

## Этап 2.5 — RunContext + Hook framework

### Шаг 2.5.0 — Определить RunContext
**Статус:** ⏳ предстоит  
**Результат:** Pydantic-модель RunContext с полями run_id, env, user_request, plan, events (list), retry_counters (dict), metadata (dict). Events — типизированный union с discriminated field type. Нет persistence, только in-memory. Тест: создать RunContext, добавить события, прочитать.

### Шаг 2.5.1 — Определить hook interface и точки расширения
**Статус:** ⏳ предстоит  
**Результат:** Protocol для Hook. Список именованных точек: before_plan, after_plan, before_step, after_step, on_critic_verdict, on_step_reject, on_run_complete, on_error. Хранилище hooks: dict[str, list[Callable]] в классе HookRunner.

### Шаг 2.5.2 — HookRunner (fail-safe)
**Статус:** ⏳ предстоит  
**Результат:** HookRunner.run(hook_name, ctx, **kwargs) — вызывает все зарегистрированные callable'ы для данного hook_name, ошибку в hook'е логирует и продолжает. Тест: hook, бросающий исключение, не прерывает вызов следующего hook'а.

### Шаг 2.5.3 — Smoke-test hook (например, EventLogger)
**Статус:** ⏳ предстоит  
**Результат:** один рабочий hook который подписывается на все точки и пишет structured-лог. Доказательство: hook видит все события при mock-run'е.

---

## Этап 3 — Orchestrator: planner → steps → executor + critic loop + retry

### Шаг 3.0 — Orchestrator MVP (голый, без hooks, без retry)
**Статус:** ⏳ предстоит  
**Результат:** Orchestrator получает RunContext, вызывает Planner (MockLLM), итерирует steps плана, вызывает один Executor (MockLLM), собирает results. Без критика, без retry. Проверка: end-to-end с MockLLM — plan выполняется, финальный ответ возвращается.

### Шаг 3.1 — Интеграция RunContext + HookRunner в Orchestrator
**Статус:** ⏳ предстоит  
**Результат:** Orchestrator вызывает HookRunner в каждой точке pipeline (before_plan, after_plan, before_step, after_step, on_run_complete и т.д.). Нет новой функциональности — только wiring. EventLogger hook подтверждает что все точки вызываются в правильном порядке.

### Шаг 3.2 — Error taxonomy в adapter layer
**Статус:** ⏳ предстоит  
**Результат:** LiteLLMAdapter преобразует исключения SDK в типизированные: TransportError, AuthError, ValidationError, ExecutorError. Тест: mock разных HTTP-ошибок → правильные типы исключений.

### Шаг 3.3 — Retry через tenacity для TransportError и ValidationError
**Статус:** ⏳ предстоит  
**Результат:** Orchestrator обёрнут tenacity для TransportError (exponential backoff). ValidationError от planner/critic → repair-попытка с уточняющим промптом (1 раз). AuthError → fail fast без retry. Тест: mock TransportError → retry; mock AuthError → стоп.

### Шаг 3.4 — Critic + CriticRejectError retry через Router
**Статус:** ⏳ предстоит  
**Результат:** Orchestrator включает Critic. При reject — не tenacity-retry, а вызов Router с hint “не этот executor” → Router возвращает альтернативу. Глобальный retry cap (configurable, default: 2 retry на step, N на run). При исчерпании → run завершается с status=failed. Тест: mock critic always-reject → cap срабатывает, run не зависает.

---

## Этап 3.5 — Persistence (DB-agnostic)

### Шаг 3.5.0 — Определить RunStore interface
**Статус:** ⏳ предстоит  
**Результат:** Protocol/ABC с методами: save_run_metadata, append_event, get_run, list_runs. Никакой реализации. Тест: mypy/pyright проверяет что будущие реализации соответствуют.

### Шаг 3.5.1 — InMemoryRunStore
**Статус:** ⏳ предстоит  
**Результат:** реализация RunStore на dict'ах, без I/O. Используется в тестах. Тест: save → append events → get_run → данные соответствуют.

### Шаг 3.5.2 — SQLiteRunStore
**Статус:** ⏳ предстоит  
**Результат:** реализация RunStore на SQLite, переиспользует init из Step 0.2. Схема: таблица runs (metadata) + таблица run_events (append-only, FK на runs). Тест: запись run через SQLiteRunStore, чтение — данные совпадают.

### Шаг 3.5.3 — Подключение RunStore через hooks
**Статус:** ⏳ предстоит  
**Результат:** PersistenceHook подписывается на after_step и on_run_complete, вызывает RunStore. Orchestrator не вызывает RunStore напрямую. Тест: integration — mock-run с SQLiteRunStore через PersistenceHook → данные в БД.

### Шаг 3.5.4 — Config для выбора backend
**Статус:** ⏳ предстоит  
**Результат:** в models.yaml поле persistence.type: sqlite | in-memory. Pydantic-валидация. test env → InMemoryRunStore автоматически.

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
