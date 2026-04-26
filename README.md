# advisor

## Run
Default environment is `dev`:
```bash
uv run advisor # explicit environment
uv run advisor --env prod
uv run advisor --env test # mock LLM, no network required
```

## Commands
Five focused commands, each targeting one role in the pipeline:
- `ask` — single step: send a question directly to the generic executor, no planning
- `plan` — call the Planner and print goal + step titles
- `exec` — execute all plan steps **only through the OCR Executor** (no critic validation)
- `critic` — review all executed steps sequentially, stopping at the first failure
- `run` — full pipeline: `plan` → `exec` → `critic` (internal method)

## Tests
```bash
uv run pytest -q
```

## Usage
### ask
Calls the generic executor directly with the user request. No planning, no review loop.
```bash
uv run advisor --env dev ask "Summarize why we keep LLM adapters vendor-agnostic."
```

### plan
Calls the Planner and prints the structured goal and step titles. Expects LLM to return valid `PlanResult` JSON; exits with code 2 on failure.
```bash
uv run advisor --env dev plan "Create a 3-step plan to implement a REST API with JWT auth."
```

### exec
Execute all plan steps through the OCR Executor **without critic validation**. Useful for debugging the executor in isolation or running extraction without validation.
```bash
uv run advisor --env dev exec @docs/fixtures/ctx_plan.yaml
```

### critic
Review all executed steps sequentially. Stops at the first rejected step.
```bash
uv run advisor --env dev critic @docs/fixtures/ctx_exec.yaml
```

### run
Full pipeline: `plan` → `exec` → `critic`.
```bash
uv run advisor --env dev plan "мой документ"
uv run advisor --env dev exec @ctx_plan.yaml
uv run advisor --env dev critic @ctx_exec.yaml
```

## Configuration
- `config/<env>/app.yaml` — LLM provider, DB path, prompts directory
- `config/<env>/models.yaml` — role-to-model mapping (`planner`, `ocr_executor`, `critic`)
- `prompts/<role>/system.md` + `user.md` — role system prompts and user templates

## Environments
- `test` — mock LLM, no network, used in CI and unit tests
- `dev` — OpenAI-compatible proxy at `localhost:4000`, for local development
- `prod` — OpenAI-compatible proxy at `localhost:4000`, for production use
