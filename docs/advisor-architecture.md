# ARCHITECTURE.md

## 0. Design Principles

Архитектура advisor'а опирается на 6 явных принципов, которые служат критерием при code review и архитектурных решениях:

- KISS — ядро оркестратора фокусируется на execution control flow (planner → executor → critic → retry). Cross-cutting concerns (persistence, metrics, logging) — за пределами ядра, через hooks. Retry-механизм в ядре, но retry-политики могут быть customizable через конфиг.
- **Vendor neutrality** — прикладной код (agents, orchestrator) не импортирует SDK провайдеров (`openai`, `anthropic`). Взаимодействие только через internal types и `LLMClient`.
- **Structured artifacts between components** — между компонентами ходят типизированные Pydantic-объекты, не строки.
- **Fail-safe для cross-cutting concerns** — сбой persistence / metrics / logging не валит run. Сбой planner/executor — валит. Разграничить обязательные компоненты от best-effort.
- **Explicit over implicit** — retry-политики, routing, конфиг прописаны явно, не через "магию".
- **SOLID** — single responsibility между ролями агентов, open/closed через hooks, dependency inversion через `LLMClient` и `RunStore`.

---

## 1. Назначение
Проект реализует **vendor-agnostic LLM advisor strategy system**: архитектуру planner–executor с опциональным critic loop. Система должна быть:
- независимой от конкретных провайдеров/SDK (OpenAI, Anthropic/Claude и т.д.),
- конфигурируемой через YAML,
- управляемой через CLI,
- надежной (retry, логирование),
- трассируемой (SQLite persistence артефактов).

---

## 2. Workflow: Clarification → Planner → Executors → Critic (MVP Flow)

**Важно:** Planner-Executor-Critic — это **MVP default flow**, один из возможных паттернов мультиагентного исполнения. Система спроектирована так, чтобы flow был сменяемой стратегией, а не зашитой логикой. Альтернативные flows (Hub-and-Spoke, ReAct, Reflection) могут быть добавлены без изменений ядра оркестратора — см. раздел "Future Extensions".

```mermaid
flowchart TD
  U[User Input] --> CL[Clarification Loop]
  CL -->|open_questions not empty| Q[Ask User]
  Q -->|user answer| CL
  CL -->|is_ready=true| PS[ClarificationState\nsummary + key_facts]
  PS --> P[Planner LLM]
  P -->|Plan JSON| O[Orchestrator]

  O --> R{Router\nkeywords}
  R --> GE[GenericExecutor]
  R --> CE[CodeExecutor]

  GE --> SR[StepResult]
  CE --> SR

  SR --> C[Critic optional]

  C -->|approve| NX[Next Step / Final]
  C -->|reject| RT[Retry same step\nwith other executor/model]

  RT --> R
  NX --> F[Final Answer]
```

Основной поток выполнения:

```
User Input
↓
Clarification Loop (задаёт уточняющие вопросы пока is_ready=false)
↓ ClarificationState (summary + key_facts)
Planner (Advisor LLM) -> возвращает структурированный Plan (JSON)
↓
Для каждого шага плана:
  Router выбирает executor (по step.type / ключевым словам)
  ↓
  Executor выполняет шаг -> возвращает StepResult
  ↓
  (Опционально) Critic проверяет -> возвращает CriticResult
  ↓
  если reject:
    retry шага с альтернативным executor/model (без перепланирования)
↓
Final Answer
```

Ключевые правила:
- **Clarification до планирования**: система не составляет план по неполному запросу. Clarification Loop завершается прежде чем Planner получает задание.
- **Anti "lost in the middle"**: Planner получает не историю диалога, а `summary + key_facts` из `ClarificationState`. Это предотвращает размытие важных деталей в длинном контексте.
- **Если critic недоволен — не перепланировать сразу**: сначала retry шага с другим executor/model согласно политике.

---

## 2.1. Clarification Loop

Clarification Loop — необязательный, но рекомендуемый шаг перед планированием. Запускается один раз за run. Реализован как простой цикл с одной LLM-ролью (`clarifier`), не отдельный агент.

### Алгоритм

```
loop:
  clarifier анализирует user_request + accumulated key_facts
  если open_questions пусты ИЛИ turn_count >= max_turns:
    is_ready = true, выход из цикла
  иначе:
    задать пользователю вопрос (или несколько)
    добавить ответ в key_facts, обновить summary
```

### ClarificationState — артефакт

- `summary: str` — 1–3 предложения: синтез того, что прояснено
- `key_facts: list[str]` — конкретные ограничения, требования, контекст
- `open_questions: list[str]` — что ещё неизвестно (пусто = готово к планированию)
- `is_ready: bool` — флаг: можно передавать в Planner
- `turn_count: int` — счётчик раундов; защита от бесконечного цикла
- `max_turns: int` — из конфига (default: 3); при достижении `is_ready=true` принудительно

### Что передаётся в Planner

Planner получает в системном промпте:
- исходный `user_request` (неизменный)
- `ClarificationState.summary`
- `ClarificationState.key_facts`

История диалога с пользователем **не передаётся**. Это сознательное решение против "lost in the middle".

### События в RunContext

- `clarification_started` — начало loop'а
- `clarification_turn` — один раунд (вопрос + ответ, без raw текста; только факты)
- `clarification_done` — loop завершён, `ClarificationState` готов

### Что отложено (не MVP)

- `clarifier` как отдельная роль в `models.yaml` — в MVP берёт model alias planner'а
- Сохранение полного диалога в persistence — только структурированные events
- Streaming вопросов в CLI

---

## 2.5. RunContext — Shared Execution State

`RunContext` — единый объект, который создаётся при старте run'а и сопровождает всё выполнение: planner → executor(s) → critic → final answer. Это точка консолидации для state, persistence, hooks и retry-логики.

### Структура RunContext

- `run_id` — уникальный идентификатор run'а
- `env` — среда выполнения (dev/prod/test)
- `user_request` — исходный запрос пользователя (неизменный)
- `started_at` — timestamp начала run'а
- `events` — append-only список событий (см. ниже)
- `metadata` — extensibility dict для hooks (ключи — имена hooks, значения — любые данные)
- `metadata` — extensibility dict для runtime state (ключи — любые, значения — любые данные)

**Производные данные** (вычисляются из events, не хранятся отдельно):
- `plan` — reconstructed из `plan_created` events (если есть в flow)
- `retry_counters` — count `*_retried` events по agent/step
- `current_step` — последний `step_started` event (если applicable)
- `tool_calls` — все `tool_call` events в порядке исполнения

### Модель событий (Events — append-only, flow-agnostic)

Каждое событие: `{type: str, timestamp: datetime, payload: dict}`

**Универсальные события** (работают для всех flows):
- `run_started` — инициализация run'а
- `run_completed` — финальный результат, run завершён
- `error` — необработанная ошибка
- `tool_call` — LLM запросил вызов tool'а (agent, tool_name, args)
- `tool_result` — результат выполнения tool'а (output или error)

**Workflow-специфичные события** (P-E-C flow определяет свои):
- `plan_created` — planner сгенерировал план
- `step_started` — executor начал работу над step'ом (step_id, executor_type)
- `step_completed` — executor вернул результат (step_id, result)
- `critic_verdict` — critic оценил шаг (step_id, approved: bool, feedback)
- `step_retried` — retry шага (step_id, reason, retry_count)

**Другие flows определяют свои события:**
- **ReAct**: `thought_generated`, `action_chosen`, `observation_received`
- **Hub-and-Spoke**: `agent_delegated`, `agent_response_received`, `aggregation_completed`
- **Dynamic adaptive**: `goal_decomposed`, `subgoal_updated`, `strategy_changed`

**Преимущества:**
- Новый flow добавляет свои event-типы без изменения RunContext
- Events хранятся единообразно в persistence (одна таблица/JSONL)
- Hooks видят полную историю в одном месте (events), интерпретируют по-своему
- Retry counting, plan reconstruction и т.д. — запросы к events, не отдельные поля

### Почему append-only events?

- **Flow-agnostic**: один events-based контейнер работает для Planner-Executor-Critic, ReAct, Hub-and-Spoke, динамических flows. Каждый flow определяет свои event-типы, но storage uniform
- **Extensibility**: новый flow не требует изменения RunContext или persistence — только добавляет свои event-типы
- **Derived state, не stored state**: plan, retry_counters, current_step — это queries к events (reconstruction), не отдельные поля. Уменьшает complexity, избегает дублирования
- **Persistent foundation**: основа для DB-agnostic persistence (каждый event = одна запись в БД)
- **Recovery & audit**: полная история run'а всегда восстанавливается через replay events; хороший audit trail
- **Fail-safe**: если persistence упал на событии N, события 1..N-1 уже сохранены

### Как разные flows используют события

Events — универсальный формат, flow интерпретирует их для своих нужд:

**Planner-Executor-Critic flow:**
```
plan = ctx.events |> filter(type='plan_created') |> extract(plan)
current_step = ctx.events |> filter(type='step_started') |> last()
retry_count(step_id) = ctx.events |> filter(type='step_retried' AND step_id) |> count()
critic_verdict = ctx.events |> filter(type='critic_verdict') |> last()
```

**ReAct flow:**
```
last_thought = ctx.events |> filter(type='thought_generated') |> last()
last_action = ctx.events |> filter(type='action_chosen') |> last()
observations = ctx.events |> filter(type='observation_received') |> list()
```

**Hub-and-Spoke flow:**
```
delegated_agents = ctx.events |> filter(type='agent_delegated') |> extract(agent_name) |> unique()
responses = ctx.events |> filter(type='agent_response_received') |> list()
```

Это устраняет жёсткую привязку RunContext к одному workflow'у.

### Что НЕ хранит

RunContext не содержит raw transcripts LLM (уменьшает размер БД, снижает риски хранения PII). Артефакты хранятся как структурированные события, не сырой текст.

---

## 3. Независимость от vendor SDK (Vendor / SDK Agnosticism)

### 3.1 Внутренний нейтральный интерфейс
Весь прикладной код (агенты, orchestrator, router) зависит только от наших внутренних типов и интерфейсов:
- `Message` (role/content) как формат сообщений
- `ChatRequest` / `ChatResponse` как нейтральные request/response
- `LLMClient` как минимальный интерфейс (Protocol) для чата

Важно: код агентов/оркестрации **не импортирует** SDK провайдеров (`openai`, `anthropic` и т.п.).

### 3.2 Adapter layer (провайдер-специфичный слой)
Конкретные SDK изолируются за адаптерами, которые реализуют `LLMClient`.

Концептуально:
[Agents/Orchestrator] -> (LLMClient) -> [Adapter] -> [Vendor SDK / HTTP API]

Примеры адаптеров:
- `LiteLLMProxyAdapter` (OpenAI-compatible Messages API endpoint)
- `AnthropicAdapter` (Claude SDK / Messages API)
- `LocalModelAdapter` (vLLM/Ollama/etc.)

Ответственность адаптера:
- преобразовать нейтральные `Message[]` в формат провайдера,
- применить vendor-specific настройки,
- нормализовать ответ обратно в `ChatResponse`,
- (позже) привести tools/function calling к каноничному внутреннему формату.

Такой дизайн позволяет добавлять нового провайдера “одним модулем”, не меняя orchestration.

---

## 4. “Anthropic-style discipline” без излишней сложности

### 4.1 Структурированные данные между компонентами (всегда)
Внутри системы обмен между агентами/оркестратором идет через **типизированные структуры** (Pydantic) — это наш внутренний контракт и база надежности.

Артефакты P-E-C flow (`flows/pec/models.py`):
- `ClarificationState` — итог уточняющего диалога (summary, key_facts, is_ready)
- `PlanResult` — структурированный план от Planner
- `PlanStep` — один шаг плана с success_criteria
- `StepResult` — результат Executor'а по одному шагу
- `CriticResult` — verdict от Critic (approved / issues)

Эти объекты сериализуются в JSON и сохраняются в SQLite через RunContext events.

### 4.2 Структурирование входа LLM (на уровне текста)
Чтобы бороться с “lost in the middle”, вход в LLM формируется “документом”:

Вход LLM формируется так, чтобы важное было в начале и было разделено заголовками:

Key Findings / Summary — в начале
Явные секции (Request, Constraints, Artifacts, Output format)
Это vendor-agnostic (обычный текст/Markdown).

### 4.3 Строго структурированный output — только там, где нужно
Planner: строгий JSON (валидируем Pydantic)
Critic: структурированный verdict (валидируем Pydantic)
Executor: обычно свободный текст, структура — по необходимости

Чтобы не усложнять систему:
- **Planner output**: строго JSON по схеме `Plan`, валидируем Pydantic.
- **Critic output**: структурированный verdict (`approved: bool`, `feedback: str`), валидируем Pydantic.
- **Executor output**: обычно свободный текст (опционально структурированные поля при необходимости).

Если парсинг/валидация ломается, применяется retry/repair (на следующих этапах).

---

## 5. Конфигурация

### 5.0 Иерархия источников конфигурации

Конфигурация собирается из нескольких источников с явным приоритетом (от наивысшего к низшему):

1. **CLI аргументы** — `--env`, `--model`, `--flow` и т.д.
2. **Переменные окружения** — `ADVISOR_*`
3. **Project-level config** — `.advisor/config.yaml` в директории проекта
4. **Global config** — `~/.advisor/config.yaml`
5. **Built-in defaults** — hardcoded в ConfigLoader

Каждый следующий уровень переопределяет предыдущий только для явно указанных ключей, не целиком. Это позволяет локальные переопределения (CLI) комбинировать с глобальными settings без дублирования.

### 5.1 Выбор окружения (`--env`)
Среда выбирается CLI флагом:
- `--env dev|prod|test`

Среда влияет на:
- директорию конфигов: `config/<env>/...`
- выбор LLM реализации:
  - `test` использует `MockLLMClient` (детерминированно, без сети)
  - `dev/prod` используют реальные адаптеры (позже)

### 5.2 YAML конфиги: что храним и почему
Мы **не дублируем** конфигурацию LiteLLM (api_base, api_key, model_list). Это ответственность LiteLLM.

Наши YAML хранят только то, что нужно приложению.

**`models.yaml`**
- маппинг внутренних ролей на alias моделей LiteLLM (primary/fallback)
- цель: быстро переключать модели по ролям и по окружениям без изменения кода

---

## 6. Persistence (DB-agnostic)

Хранение артефактов run'а реализуется через абстрактный интерфейс `RunStore`, не привязано к конкретной БД.

### 6.1 RunStore — абстрактный интерфейс

Весь persistence-код в ядре работает только через интерфейс `RunStore`. Минимальный набор операций:

- `save_run_metadata(run_id, metadata: dict)` — создать запись о run'е
- `append_event(run_id, event: RunEvent)` — добавить событие (append-only)
- `get_run(run_id)` → tuple[metadata, events] | None
- `list_runs(limit: int, env: str | None = None)` → list[metadata]

### 6.2 Реализации RunStore

- **SQLiteRunStore** — default для dev/prod, переиспользует инициализацию из Stage 0.2
- **InMemoryRunStore** — для тестов (нет disk I/O, детерминированно)
- Выбор backend'а через конфиг (`persistence.type: sqlite | in-memory`)
- В будущем: JSONL-файлы, PostgreSQL и т.д.

### 6.3 Модель хранения: metadata + append-only events

**Run metadata** (неизменная "шапка"):
- `run_id`, `env`, `user_request`, `started_at`, `completed_at`, `status`

**Run events** (append-only):
- Каждое событие = одна запись (см. раздел 2.5 RunContext)
- Разделение: metadata читается быстро; events растут инкрементально

**Почему append-only?**
- Работает для любого flow (система спроектирована с расчётом на future extensions)
- Основа для DB-agnostic persistence: каждый event = одна запись
- Восстановление run'а при сбое через replay событий
- Совместимо с fail-safe: если persistence упал на событии N, события 1..N-1 уже сохранены

### 6.4 Подключение к оркестратору

RunStore вызывается только через hooks (`after_step`, `on_run_complete`), не прямыми вызовами из ядра orchestrator'а. Это обеспечивает fail-safe: сбой persistence не валит основной flow.

---

## 7. Логирование
Используется стандартный `logging`:
- dev → DEBUG
- prod → INFO
- формат логов включает filename и line number для удобного дебага

Пока логирование только в консоль (по умолчанию stderr). Файл-лог можно добавить позже.
Настройки логирования тоже позже будут из файла конфигурации для env.

---

## 8. Надежность и retry (планируемая политика)

### 8.1 Error taxonomy — классификация ошибок

Retry-политика определяется типом ошибки. Иерархия ошибок:

- **TransportError** (timeout, 5xx, rate limit, connection refused) → exponential backoff, retryable
- **AuthError** (401, 403) → fail immediately, non-retryable (нет смысла retry)
- **ValidationError** (невалидный JSON от planner/critic) → repair-попытка с уточняющим промптом
- **ExecutorError** (сбой в исполнении шага) → retryable с другим executor/model через Router
- **CriticRejectError** (штатный reject от critic) → отдельный путь (Step 3.4): retry шага через Router без перепланирования

**Глобальный retry cap:**
- Максимум retry на один шаг: 2 (configurable)
- Максимум суммарных reject'ов за run: N (configurable) — защита от бесконечного цикла при хроническом reject
- При исчерпании → run завершается с `status=failed`, все артефакты сохранены

### 8.2 Применение retry-политик

Retry применяем для:
1) транспортных ошибок (timeouts, rate limits, transient)
2) ошибок качества/валидации (critic reject, невалидный JSON planner/critic)

Ключевая политика:
- critic reject → retry того же шага с альтернативным executor/model
- перепланирование — fallback, не дефолт

Для retry используется `tenacity`.

```mermaid
stateDiagram-v2
  [*] --> Plan
  Plan --> ExecuteStep
  ExecuteStep --> CriticCheck
  CriticCheck --> NextStep: approve
  CriticCheck --> RetryStep: reject
  RetryStep --> ExecuteStep
  NextStep --> [*]: done
```

---

## 8.5. Extension Hooks

Оркестратор вызывает именованные hook-точки в ключевых местах pipeline. Hooks — это user-defined callable'ы, получающие `RunContext`.

### Именованные точки расширения

- `before_plan(ctx)` — перед вызовом planner
- `after_plan(ctx, plan)` — план получен, до первого шага
- `before_step(ctx, step)` — перед вызовом executor
- `after_step(ctx, step, result)` — после получения StepResult
- `on_critic_verdict(ctx, step, verdict)` — после получения verdict от critic
- `on_step_reject(ctx, step, verdict)` — при reject, до retry
- `on_run_complete(ctx, final_answer)` — run завершён
- `on_error(ctx, error)` — необработанная ошибка в pipeline

### Контракт hooks

- Hook получает `RunContext`, может читать и дополнять `metadata`
- Hook **не может** прерывать основной flow (не middleware-style short-circuit)
- Ошибка в hook'е: логируется, flow продолжается — **fail-safe** (аналогично Design Principles)
- Hooks регистрируются при инициализации, не хардкодятся в orchestrator

### Применение (примеры)

- **Persistence**: `after_step` + `on_run_complete` → `RunStore`
- **Debug logging**: `before_step` + `after_step` → структурированный лог шагов
- **Метрики**: `on_run_complete` → агрегация usage/cost из events

Hooks позволяют добавлять persistence, метрики, валидацию без правок ядра оркестратора. Это реализация open/closed principle на практике.

---

## 9. Тестирование
- `--env test` + `MockLLMClient` + `config/test/...` дают детерминированные тесты без сети
- unit tests для конфигов/валидации/роутинга
- integration smoke tests для запуска CLI в test env

---

## 10. Future Extensions

### 10.1 Flow abstraction (post-MVP)

Planner-Executor-Critic — один flow. Когда потребуется расширение, Flow вводится как абстракция со своим контрактом (участники, логика передачи управления, критерии завершения). Оркестратор становится "flow runner". 

Примеры будущих flows:
- **Hub-and-Spoke**: центральный координатор делегирует специализированным агентам, агрегирует ответы
- **ReAct**: один агент в цикле think→act→observe с tools
- **Reflection**: agent → self-critique → revision → repeat
- **Sequential chain**: `agent_A → agent_B → agent_C` без ветвлений

**Критерий правильной реализации:** добавление нового flow не требует изменений в ядре оркестратора, RunContext, persistence, hooks. Это валидация что система действительно расширяемая.

### 10.2 Agent-as-config

Роли (Planner, Executor, Critic) — это конфигурации агента (prompt + tools + model alias), а не классы-наследники. Это позволяет добавить новую роль (например, Hub или Spoke) только конфигом, без нового класса.

### 10.3 Tools layer

- **Tool interface**: name, description, parameter schema (JSON Schema), invoke callable
- **Tool registry**: глобальный реестр, агенты объявляют subset доступных tools
- **Vendor-agnostic schema**: adapter конвертирует в OpenAI functions / Anthropic tool_use при вызове
- **Security**: validation входов по schema, audit каждого call'а в RunContext events
- **MCP (Model Context Protocol)** как потенциальный стандарт для интеграции готовых tool-серверов

---

## 11. Session Management (post-MVP)

### 11.1 Концепция

На текущем MVP фокус — отдельные runs (статeless запросы). Для post-MVP нужно управление **долгоживущими сессиями пользователя**:

- **Session** — контейнер множественных run'ов, связанных одним пользователем/контекстом
- **session_id** — глобально уникальный идентификатор сессии
- **Session history** — список run'ов в порядке их выполнения
- **Persistent session context** — опциональное хранение state между run'ами (conversation memory, user preferences)

### 11.2 Архитектурные изменения

**RunContext расширяется:**
- добавить поле `session_id: str | None` (опционально)
- все run'ы с одним `session_id` образуют логическую сессию

**RunStore интерфейс расширяется:**
- `create_session(user_id: str) → session_id` — создать новую сессию
- `get_session(session_id) → (metadata, list[run_id])` — получить info сессии и её run'ы
- `list_sessions(user_id, limit) → list[session_metadata]` — история сессий пользователя
- `append_session_context(session_id, context_update: dict)` — обновить session context

**Persistence schema:**
- таблица `sessions` (session_id, user_id, started_at, completed_at, status, context JSON)
- таблица `runs` расширяется с FK на `sessions` (session_id nullable для backward-compatibility)

**CLI расширяется:**
- `advisor chat --session <session_id>` — продолжить существующую сессию
- `advisor sessions list [--user <user_id>]` — просмотр истории сессий
- `advisor sessions show <session_id>` — детали сессии + список run'ов

### 11.3 Пример flow'а с сессиями

```
User initiates chat session:
  advisor chat
  → creates session_id (e.g., sess_abc123)
  → enters interactive mode

User query 1:
  > analyze this data
  → creates run (run_1) with session_id=sess_abc123
  → executes, returns answer
  → stores run_1 metadata + session context

User query 2 (in same session):
  > based on previous, suggest improvements
  → creates run (run_2) with session_id=sess_abc123
  → planner gets access to session history (run_1 results)
  → executes, returns answer

On exit:
  → session marked completed
  → full history persisted (all run artifacts + session metadata)
```

### 11.4 Integration with RunContext & Hooks

- `before_plan(ctx)` получит access к `ctx.session_id` и истории runs в сессии через RunStore
- planner может использовать session history как контекст для планирования (опционально)
- hooks могут интегрировать session-level metrics/logging через `on_run_complete`

### 11.5 Non-breaking design

- Для backward-compatibility: `session_id` в RunContext опционален
- Старые run'ы (без session_id) по-прежнему хранятся и доступны
- CLI команды работают как с сессиями, так и с отдельными run'ами
- Переход с MVP (stateless) на post-MVP (sessions) — постепенный

### 11.6 Future considerations

- **User identification**: сессии привязаны к `user_id` — нужен механизм auth/identification (позже)
- **Session memory injection**: как и когда прошлые run'ы попадают в prompt'ы (может быть отдельная схема)
- **Session cleanup**: политика архивирования/удаления старых сессий
- **Distributed sessions**: если advisor работает в многопроцессном/сетевом режиме, синхронизация session state