## PROJECT
| FIELD | VALUE |
|--------------|------------------------------------|
| name | adviser |
| type | application |
| architecture | layered-cli |
| languages | Python |
| frameworks | Typer, aiohttp, OpenAI SDK, Instructor |
| build | uv, hatchling |

---
## COMMANDS
| TASK | COMMAND | NOTES |
|--------|-------------------|-------|
| build | uv build | |
| dev | uv run advisor | Local development |
| test | uv run pytest | |
| lint | uv run ruff check | |
| *(Only explicitly declared commands from build manifest.)*

---
## RUNTIME
| REQUIREMENT | VERSION | NOTES |
|-------------|---------|--------------------------|
| Python | 3.13+ | from .python-version |
| typer | ^0.24.1 | Typer CLI framework |
| instructor | ^1.7.0 | Structured LLM output handling |
| openai | ^2.31.0 | OpenAI API client |
| pydantic | ^2.13.0 | Data validation |
| pyyaml | ^6.0.3 | YAML configuration |
| aiohttp | ^3.13.5 | HTTP/WebSocket client |
| uv | - | Dependency manager |
| hatchling | - | Python build system |
*(Hard runtime deps only. Write `(skip - no runtime descriptor)` if none.)*

---
## DEPENDENCIES
| PACKAGE | VERSION | PURPOSE |
|-------------|---------|--------------------------|
| instructor | ^1.7.0 | Structured LLM output handling |
| openai | ^2.31.0 | OpenAI API client |
| pydantic | ^2.13.0 | Data validation and settings |
| pyyaml | ^6.0.3 | YAML config parsing |
| typer | ^0.24.1 | CLI framework |
| aiohttp | ^3.13.5 | Async HTTP client |
| uv | - | Dependency management |
| hatchling | - | Python build backend |
*(Top 8 production deps only. Skip if library/simple script.)*

---
## ENV_CONFIG
| KEY | REQUIRED | PURPOSE |
|-----------------|----------|----------------------------|
| `LLM__PROVIDER` | no | LLM provider type (openai/anthropic/mock) |
| `LLM__BASE_URL` | no | Base URL for LLM API gateway |
| `LLM__API_KEY` | yes | API key for external LLM provider (OpenAI) |
*(Key names only — never values. Adaptive max: 12-20. Write `(skip - fully static config)` if none.)*

---
## ENTRYPOINTS
| TYPE | PATH | PURPOSE |
|----------------|---------------|--------------------------------|
| cli | cli/main.py | Main Typer CLI entrypoint (advisor command) |
| package | pyproject.toml:advisor | Entry script registered in project config |

---
## STRUCTURE (depth=2)
```
├── .data/
├── cfg/
│   ├── __init__.py
│   └── loader.py
├── cli/
│   ├── __init__.py
│   ├── commands/
│   │   ├── ask.py
│   │   ├── critic.py
│   │   ├── exec.py
│   │   ├── ocr_flow.py
│   │   ├── plan.py
│   │   └── utils.py
│   └── main.py
├── common/
│   ├── __init__.py
│   └── types.py
└── config/
    ├── __init__.py
    ├── dev/
    │   ├── agents.yaml
    │   ├── app.yaml
    │   └── models.yaml
    ├── prod/
    │   ├── agents.yaml
    │   ├── app.yaml
    │   └── models.yaml
    └── test/
        ├── agents.yaml
        ├── app.yaml
        └── models.yaml
```

---
## MODULES

| MODULE | PATH | PURPOSE | AI_TASK |
|-----------------|---------------------|------------------------------|----------------|
| cli-core | cli/ | Main CLI framework and command registration | CLI_AUTOMATION |
| cli-commands | cli/commands/ | Individual CLI commands (ask, plan, exec, etc.) | CLI_AUTOMATION |
| configuration | config/ | Environment-specific configuration files (dev/prod/test) | CONFIG |
| configuration-core | cfg/ | Core configuration loader utilities | CONFIG |
| common | common/ | Shared types, models, and utilities | BUSINESS_LOGIC |
| llm-factory | llm/factory.py | LLM client creation and provider selection | SECURITY |
| db-infra | db/ | Database connection, runtime, and persistence | INFRA |
| llm-openai-client | llm/openai_client.py | OpenAI-compatible HTTP client | INFRA |
| llm-mock | llm/mock.py | Mock LLM client for testing | INFRA |
| db-infra-core | db/db.py, db/bootstrap.py | Database schema, migrations, and bootstrap utilities | INFRA |
| prompts-core | prompts/{user,system}.md | LLM prompts for planner, executor, critic, and OCR flow | CONFIG |
| flows-pec | flows/pec/ | PEC (Planner-Executor-Critic) workflow orchestration | PEC_AUTOMATION |
| tools | tools/ | Shared utilities (logging, etc.) | DEV_TOOLING |
| tests | tests/ | Test suites (unit, integration) | TESTS |
*(List in priority order: core → infra → API → tests → tooling.)

---
## FLOWS
| FLOW NAME | STEP | FROM | TO | PURPOSE | NOTES |
|----------------------------|------|-------------------------------|-----------------------------------|-----------------------------------------------------|-------------------------------|
| CLI command execution | 1 | CLI main (cli/main.py) | Configuration loader | Load app config and dependencies | <cfg/loader.py> |
|  | 2 | Configuration loader | Database connection | Establish DB session for current run | <db/runtime.py> |
|  | 3 | Database connection | LLM factory initialization | Create or reuse LLM client | <llm/factory.py> |
|  | 4 | LLM factory | Command execution | Execute CLI command with dependencies | <cli/commands/*.py> |
|  | 5 | Command execution | LLM API call | Call external LLM provider | <llm/openai_client.py> |
|  | 6 | LLM API call | Response handling | Return structured response to user | <cli/commands/ask.py> |
*(Max 3 flows, 6 steps each. Write `(skip - not applicable)` if no pipeline.)

---
## API_SURFACE

| ROUTE_GROUP | PATH_PREFIX | PURPOSE |
|-------------|---------------|------------------------|
| advisor-cli | /cli | Typer CLI with subcommands (ask, plan, exec, critic, ocr_flow) |
| pec-api | /plan, /execute, /critic | RESTful API endpoints for PEC (Planner-Executor-Critic) workflow within CLI |
*(Write `(skip - not applicable)` if no service API.)*

---
## API_CONSUMED

| SERVICE | BASE_URL_CONFIG_KEY | OPERATIONS | MODULE |
|---------|---------------------|------------|--------|
| OpenAI API (via LiteLLM) | `LLM__BASE_URL` `LLM__PROVIDER` | chat, completions | llm-openai-client |
| PEC workflow engine | - | plan execution, critic review, OCR flow orchestration | flows/pec/ |
| (Mock LLM for testing) | - | mock chat streams | llm-mock |
*(Max 10. Prioritize: auth > data stores > messaging > notifications. Write `(skip - not applicable)` if none.)

---
## FEATURE_MAP
| FEATURE | ROUTE | HANDLER | SERVICE | MODEL |
|---------|-------|---------|---------|------|
| ask | - | ask command | llm-openai-client | ChatRequest |
| plan | - | plan command | Planner service | PlanRequest |
| exec | - | exec command | Executor service | ExecRequest |
| critic | - | critic command | Critic service | CriticRequest |
| ocr_flow | - | ocr_flow command | OCRFlow service | OCRRequest |
*(Use `-` for N/A columns. Write `(skip - not applicable)` if <3 features.)

---
## DATA_ENTITIES
| CONTRACT | PURPOSE |
|-------------|----------------------------------|
| ChatRequest | Input message format for LLM chat |
| Message | Single chat message (role/content) |
| LLMConfig | Runtime LLM provider configuration |
| LLMProvider | Literal type for supported providers |
*(Max 16. Write `(skip - not applicable)` if no domain model.)

---
## KEY_FILES

| FILE | PURPOSE | RELATED_MODULES |
|-----------------------|--------------------------------|----------------------|
| pyproject.toml | Project metadata, dependencies, scripts | DEV_TOOLING |
| cli/main.py | Main CLI entrypoint and context initialization | cli-core |
| cfg/loader.py | Configuration loader utilities | configuration-core |
| llm/factory.py | LLM client creation and management | llm-factory |
| db/runtime.py | Database connection and session management | db-infra |
| llm/openai_client.py | OpenAI-compatible HTTP client | llm-openai-client |
| llm/mock.py | Mock LLM client for testing | llm-mock |
| db/db.py | Database schema models and SQLAlchemy core definitions | db-infra-core |
| db/bootstrap.py | Database schema initialization and pre/post-migration hooks | db-infra-core |
| prompts/user.md | User-facing prompts for planner, executor, critic | prompts-core |
| prompts/system.md | System prompts for planner, executor, critic | prompts-core |
| common/types.py | Shared types and DTOs | common |
| config/dev/app.yaml | Development environment configuration | configuration |
| config/prod/app.yaml | Production environment configuration | configuration |
| config/test/app.yaml | Test environment configuration | configuration |
*(Max 15. Must include: entrypoint, deps, config, schema if exists.)

---
## CONVENTIONS
| RULE | SOURCE |
|-------------------------------------------|------------------|
| CLI commands use Typer with `ctx: typer.Context` | `cli/main.py` (pattern confirmed) |
| Each command module imports from cli.handler and registers via decorator | `cli/commands/ask.py` (pattern confirmed) |
| Environment-specific configs isolated under config/{dev,prod,test}/ | Directory structure confirmed |
| Configuration subdirs use structured profile discovery | `cfg/loader.py` (pattern confirmed) |
| Async functions use `asyncio.run()` for CLI entrypoints | `cli/commands/ask.py` (pattern confirmed) |
*(Max 5 non-obvious rules. Write `(skip - no explicit conventions)` if none.)

---
<!-- Generated: 2026-04-28 -->