# Advisor Strategy System — Implementation Plan (Python, vendor-agnostic)

Цель: поэтапно реализовать vendor-agnostic LLM advisor strategy system (planner–executor + optional critic loop) на Python с конфигурацией в YAML, CLI, retry, логированием, кешем и SQLite persistence.  
Доступ к LLM: через **LiteLLM proxy (OpenAI-compatible Messages API)**. Streaming — позже.

---

## Этап 0 — Базовая инфраструктура

### Шаг 0.0 — Скелет проекта, запуск, README, Hello world
**Цель:** проект запускается локально, есть простейшая CLI-команда.

**Готово, если:**
- `uv run advisor` запускается и печатает `Hello world` (или другой smoke output)
- есть минимальный `README.md`

**Артефакты:**
- `cli/main.py`
- `pyproject.toml` с `[project.scripts] advisor = "..."`
- `README.md`

---

### Шаг 0.1 — Параметр среды dev/prod при старте приложения
**Цель:** CLI принимает `--env dev|prod` и приложение знает текущую среду.

**Решение:**
- Typer `@app.callback()` + `invoke_without_command=True`
- Вывод `env=...` при старте

**Готово, если:**
- `uv run advisor` → `env=dev`
- `uv run advisor --env prod` → `env=prod`

**Артефакты:**
- обновление `cli/main.py`
- обновление `README.md` (примеры запуска с `--env`)

---

### Шаг 0.2 — Логирование и подключение к SQLite
**Цель:** базовый `logging` + создание/открытие SQLite файла, чтобы дальше писать артефакты.

**Рекомендуемые решения (MVP):**
- стандартный `logging` (консоль)
- `sqlite3` из stdlib (простота), позже можно перейти на SQLAlchemy

**Готово, если:**
- при запуске инициализируется логгер (уровень INFO/DEBUG)
- создаётся файл БД (если нет) в заданном пути
- выполняется минимальная миграция (создание таблицы `runs`)

**Артефакты:**
- `advisor/logging.py` или `core/logging.py`
- `advisor/.data/sqlite.py` (init_db)

---

### Шаг 0.3 — Загрузка конфигов в зависимости от среды выполнения
**Цель:** по `--env` выбираются конфиги и/или `.env` файлы, конфигурация валидируется.

**Решение:**
- `config/` директория
- YAML + Pydantic схемы
- `.env` файлы: `dev.env`, `prod.env`, `test.env` (опционально)
- loader с кешем (`lru_cache`) — аккуратно

**Готово, если:**
- `advisor --env dev` грузит `config/...` и валидирует
- ошибки конфигов понятны (pydantic validation errors)

**Артефакты:**
- `config/models.yaml`, `config/agents.yaml`
- `advisor/config/schema.py`, `advisor/config/loader.py`
- `advisor/settings.py` (env loading)

---

## Этап 1 — LLM доступ (LiteLLM) + базовые типы сообщений

### Шаг 1.0 — Базовые типы сообщений (Messages API)
**Цель:** унифицированные типы `Message`, `ChatRequest`, `ChatResponse` (pydantic).

**Готово, если:**
- типы покрывают роль/контент
- можно сериализовать в формат OpenAI-compatible messages

**Артефакты:**
- `advisor/llm/types.py`

---

### Шаг 1.1 — LLM Client (LiteLLM proxy, без streaming)
**Цель:** минимальный клиент `LLMClient.chat()` через OpenAI-compatible endpoint.

**Решение:**
- `openai.AsyncOpenAI(base_url=..., api_key=...)`
- метод `chat(req)` возвращает `ChatResponse(text, usage?, raw?)`

**Готово, если:**
- есть рабочий “ручной” пример запроса
- ошибки сети обрабатываются и логируются (без retry на этом шаге можно)

**Артефакты:**
- `advisor/llm/protocol.py` (Protocol)
- `advisor/llm/litellm_client.py`

---

### Шаг 1.2 — Минимальные тесты для LLM слоя (без сети)
**Цель:** тестируем контракт и структуру без реальных HTTP вызовов.

**Решение:**
- `FakeLLMClient` для тестов
- smoke tests: типы, сериализация, базовый контракт

**Артефакты:**
- `tests/test_llm_contract.py`

---

## Этап 2 — Агентный слой (Planner/Executor/Critic)

### Шаг 2.0 — Prompt loader (FS)
**Цель:** каждый агент умеет загрузить prompt из файла.

**Решение:**
- `pathlib.Path.read_text(encoding="utf-8")`
- кеширование опционально (`lru_cache`)

**Готово, если:**
- prompt читается
- ошибки (нет файла) дают понятное исключение

---

### Шаг 2.1 — AgentBase (ABC) + структурированные вход/выход
**Цель:** единый интерфейс `ainvoke(...)` для агентов.

**Решение:**
- `abc.ABC` + `@abstractmethod`
- pydantic модели для input/output (особенно для Planner plan)

---

### Шаг 2.2 — PlannerAgent: JSON план (pydantic)
**Цель:** Planner генерирует план в JSON, валидируем pydantic моделью.

**Решение:**
- pydantic `Plan`, `PlanStep`
- парсинг: `json.loads(resp.text)` → `Plan.model_validate(...)`
- позже добавим repair+retry

---

### Шаг 2.3 — Executor агенты: GenericExecutor + CodeExecutor
**Цель:** выполнение шагов плана.

**Router MVP:** keywords (“code”, “python”, “implement”, “class”, “bug”, “refactor” → CodeExecutor, иначе Generic).

---

### Шаг 2.4 — CriticAgent (опционально, но желательно)
**Цель:** оценка результата шага/финала: approve/revise.

**Выход:** `Critique(approved: bool, feedback: str, severity: ...)`

---

## Этап 3 — Orchestrator (planner→steps→executors + critic loop + retry)

### Шаг 3.0 — Orchestrator MVP без retry
**Цель:** связать planner и executors последовательно, собрать final answer.

---

### Шаг 3.1 — Retry стратегия (tenacity)
**Цель:** ретраи на:
- сетевые ошибки/429
- critic reject (политика: retry step другим executor’ом)

**Правило:** если critic недоволен — **не перепланировать сразу**, а сначала retry step с другим executor.

---

### Шаг 3.2 — Fallback политики
**Цель:** определить поведение при превышении лимитов:
- fallback на другой executor/model
- (опционально) реплан после N фейлов

---

## Этап 4 — Factory + конфигурация агентов/моделей (YAML) + env

### Шаг 4.0 — YAML конфиги моделей и агентов
**Файлы:**
- `config/models.yaml`: temperature/max_tokens/model name
- `config/agents.yaml`: role → model_ref + prompt_file

---

### Шаг 4.1 — Factory: создание агентов по env и YAML
**Цель:** создать агентов из конфигов.
- dev/test: Mock/Fake агенты или FakeLLMClient
- prod: LiteLLM client

**Trade-off:** избегать глобальных singletons; лучше явный factory object.

---

## Этап 5 — Tools (sync python functions) end-to-end

### Шаг 5.0 — Canonical ToolSpec + registry
**Цель:** единый формат tools и реестр функций (allowlist).

---

### Шаг 5.1 — Tool execution
**Цель:** выполнить синхронную функцию, вернуть tool result.

---

### Шаг 5.2 — Интеграция tool-calling с LiteLLM (Messages API)
**Цель:** поддержать tool calls через OpenAI-compatible формат (через proxy).

---

## Этап 6 — Persistence (SQLite): хранение артефактов

### Шаг 6.0 — Схема БД (MVP)
Храним только артефакты:
- run (input, env, timestamps)
- plan (json)
- steps (json in/out, executor, attempts)
- critic (verdict, feedback)
- final (text/json)
- usage (если доступно)

---

### Шаг 6.1 — Repository слой
**Цель:** изолировать SQL от orchestrator’а.

---

## Этап 7 — CLI команды (ask/chat/list-models)

### Шаг 7.0 — `list-models`
Читает YAML и печатает доступные модели.

### Шаг 7.1 — `ask`
Один запуск orchestrator для одного запроса.

### Шаг 7.2 — `chat` (сессия)
Интерактивный режим (позже можно добавить persistence session).

> Streaming добавить позже отдельным шагом, без поломки API.

---

## Этап 8 — Набор тестов

### Шаг 8.0 — Unit tests
- config validation
- routing keywords
- plan parsing + failure cases
- retry policy logic (critic reject)

### Шаг 8.1 — Integration tests (offline)
- orchestrator с FakeLLMClient на сценариях approve/reject/retry

---

## Этап 9 — Документация

### Шаг 9.0 — README расширенный
- Quickstart
- структура конфигов
- как добавить модель/агента
- примеры `.env` (dev/prod)
- troubleshooting

---

## Этап 10 — Streaming (позже)

### Шаг 10.0 — Streaming в LLMClient
Добавить `chat_stream()` (async iterator) + UI в CLI (rich).

---

## Критерии “готово для MVP”
- CLI: `advisor --env dev ask "..."` (или аналог)
- Planner → Executor pipeline работает
- Есть retry (tenacity) на шаге (минимум 1 политика)
- SQLite сохраняет plan/steps/final
- Конфиги YAML валидируются pydantic
- Минимальные тесты проходят
