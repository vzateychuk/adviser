# Session Summary — Advisor Strategy System (MVP)

Дата: 2026-04-16  
Назначение: краткая фиксация текущего состояния проекта и принятых решений, чтобы продолжить работу в новой сессии.  
Файлы-источники: `impl-plan.md`, `planner.md`, `generic_executor.md`, `code_executor.md`, `critic.md`

---

## 1) Цель проекта (MVP)
Построить vendor-agnostic LLM advisor strategy system на Python:
- planner–executor архитектура + опциональный critic loop
- единый интерфейс для LLM клиентов (через adapters)
- конфигурация через YAML (env-specific)
- CLI интерфейс
- надежность: обработка ошибок, retry/fallback (частично)
- persistence: SQLite (храним артефакты, не полный transcript)
- prompts из файловой системы

---

## 2) Ключевые архитектурные решения
- **Orchestrator**: это **код**, не LLM. Управляет процессом, политиками, persistence.
- **LLM** используется в ролях: planner / generic_executor / code_executor / critic.
- Vendor neutrality: SDK провайдера импортируется только в `llm/` adapters; остальной код зависит только от внутренних типов/Protocol.
- Контекст: избегаем накопления длинной истории; передаем структурированный ввод секциями + summary/key facts (для будущего clarification loop).
- Prompts загружаются из FS и подставляются как system message.

---

## 3) Среды выполнения (env)
Поддерживаются: `dev`, `prod`, `test` через `--env`.
- `test`: `MockLLMClient` (без сети, детерминированно).
- `dev/prod`: OpenAI-compatible client через LiteLLM proxy.

---

## 4) Конфиги (YAML)
Env-specific: `config/<env>/...`

### `models.yaml`
Назначение: маппинг **роль → model alias** (primary/fallback).
- роли: `planner`, `generic_executor`, `code_executor`, `critic`

### `app.yaml`
Назначение: runtime-настройки окружения.
- `llm.provider`: `openai | anthropic | mock` (anthropic пока не реализован)
- `llm.base_url`: base_url для OpenAI-compatible proxy
- `db.path`: путь к SQLite
- `prompts_dir`: путь к директории prompt-файлов

---

## 5) LLM слой
### Внутренний контракт
- `LLMClient` (Protocol): `async chat(ChatRequest) -> ChatResponse`
- `ChatRequest`: включает `model`, `messages`, и `meta: dict[str,str] | None`
- `meta` используется для test/mock и будущих хуков/контекста (например `meta.role`).

### Реальные реализации
- `OpenAICompatibleClient`: AsyncOpenAI, base_url берется из `app.yaml`.
- `MockLLMClient`: детерминированный клиент; для `meta.role=="planner"` возвращает валидный JSON план.

---

## 6) Prompts
Prompts хранятся в `prompts/`:
- `planner.md`
- `generic_executor.md`
- `code_executor.md`
- `critic.md`

Загрузка:
- `tools/prompts.py`: `load_role_prompt(role, prompts_dir)` + `render_template(template, values)`
- `render_template` подставляет `{{PLACEHOLDER}}`; если что-то не подставилось — логирует warning, не падает.

`prompts_dir` берется из `app.yaml`, а не из CWD.

---

## 7) PEC артефакты (структурированные модели)
Модели перенесены в:
- `flows/pec/models.py` (ранее `artifacts/` удалён)

Модели (Pydantic):
- `PlanStep` (id, title, type, input, output, success_criteria)
- `PlanResult` (goal, assumptions, steps)
- `StepResult` (step_id, executor, content, assumptions)
- `CriticIssue` (severity, description, suggestion)
- `CriticResult` (approved, issues, summary)

---

## 8) CLI команды (Typer)
Bootstrap (`cli/main.py`) делает:
- setup_logging(env)
- load_models(cfg_dir), load_app(cfg_dir)
- create_llm(env, app_cfg)
- кладёт в `ctx.obj`: env, models_registry, app_cfg, llm, prompts_dir
- инициализирует SQLite и пишет run metadata

Команды:
- `ask`: one-shot вызов по роли (default `generic_executor`)
- `plan`: planner вызов → извлечение JSON (учёт ```json fences) → валидация в `PlanResult` → печатает `Plan OK, steps=N`
- `exec-step`: выполнить один `PlanStep` (передаётся как JSON строка), роутинг по `step.type` → GenericExecutor/CodeExecutor

Имена команд:
- используется дефисное имя для `exec-step` через `app.command("exec-step")(exec_step)`.

---

## 9) Executors (Этап 2.3)
- `flows/pec/executors/generic_exec.py`: `GenericExecutor(llm, model_alias, prompts_dir)`
- `flows/pec/executors/code_exec.py`: `CodeExecutor(llm, model_alias, prompts_dir)`
- Формируют system prompt через placeholders:
  - `STEP_TITLE`, `STEP_INPUT`, `STEP_OUTPUT`, `STEP_SUCCESS_CRITERIA`, `PREVIOUS_RESULTS`
- `PREVIOUS_RESULTS` готовится через helper:
  - `flows/pec/executors/utils.py::summarize_previous_results(previous_results, max_lines=20)`
  - берёт первые 20 строк каждого результата
  - содержит TODO на более умную суммаризацию

Важно:
- `flows/pec/executors/__init__.py` не должен импортировать пакет сам в себя (избегаем circular imports).

---

## 10) Error handling
- CLI ловит внутреннее исключение `LLMError` (vendor-neutral), не `openai.APIStatusError`.
- При `LLMError` команды завершаются через `typer.Exit(code=2)` и пишут понятный лог.

---

## 11) Logging
- `tools/logging.py` настраивает logging:
  - dev: DEBUG
  - prod: INFO
- формат включает `filename:lineno`

---

## 12) Persistence (SQLite)
- SQLite используется для артефактов (MVP пока: запись run metadata при старте).
- Хранение plan/steps/final/critic — запланировано далее.

---

## 13) Тестирование (соглашения)
Рекомендованная структура:
- `tests/cli/` — только интеграционные smoke тесты CLI (`ask/plan/exec-step`, bootstrap)
- `tests/tools/` — unit tests для prompt loader/renderer
- `tests/cfg/` — unit tests для config loaders (включая `load_app` и `prompts_dir`)
- `tests/pec/` — unit tests для Pydantic моделей PEC и executor utils

Важно:
- не держать два test файла с одинаковым basename (иначе pytest import mismatch).

Добавлены тесты/ожидаемые:
- `load_app` парсит `prompts_dir` (unit)
- `summarize_previous_results` ограничивает строки (unit)
- `plan` в `--env test` должен проходить (интеграционный, зависит от `meta.role="planner"`)

---

## 14) README (примеры)
Добавлены секции Examples:
- `ask` (default generic_executor) + `--role code_executor`
- `plan` (ожидает JSON plan, не чат)
- `exec-step` через чтение JSON из `docs/steps/*.json` (Git Bash и PowerShell варианты)
- `critic` временно через `ask --role critic ...`

---

## 15) Текущее состояние по плану (impl-plan.md)
Выполнено:
- Этап 0 (0.0–0.3)
- Этап 1 (1.0–1.2)
- Этап 2:
  - 2.0 Prompts FS
  - 2.1 PEC модели
  - 2.2 Planner JSON validation (через CLI `plan`)
  - 2.3 Executors + `exec-step` (в процессе стабилизации тестов)

Дальше по плану:
- 2.4 Critic агент/команда review-step + critic loop
- 3.0 Orchestrator MVP (plan → execute steps) + persistence артефактов
- Clarification Loop (MVP: только до plan) — запланировано как отдельное расширение
- Smart routing (RouterAgent + RouteDecision + policy enforcement) — после 2.4/3.0

---
