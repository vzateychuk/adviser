# advisor

## Run

Default environment is `dev`:

```bash
uv run advisor

# explicit environment
uv run advisor --env prod
uv run advisor --env test   # mock LLM, no network required
```

## Commands

Five focused commands, each targeting one role in the pipeline:

- `ask` — single step: send a question directly to the generic executor, no planning
- `plan` — call the Planner and print goal + step titles
- `exec-step` — execute one plan step (routes to generic or code executor by `step.type`)
- `review` — review a step result against its success criteria, print verdict
- `flow` — full pipeline: Planner -> Executor -> Reviewer loop, retries on rejection

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

Calls the Planner and prints the structured goal and step titles.
Expects LLM to return valid `PlanResult` JSON; exits with code 2 on failure.

```bash
uv run advisor --env dev plan "Create a 3-step plan to implement a REST API with JWT auth."
```

### exec-step

Executes a single `PlanStep` passed as JSON. The executor is selected by `step.type`
(`generic` or `code`). Useful for debugging a single step in isolation.

```bash
uv run advisor --env dev exec-step "$(cat docs/steps/step_generic.json)"
uv run advisor --env dev exec-step "$(cat docs/steps/step_code.json)"
```

Example inline:

```bash
uv run advisor --env prod exec-step '{
  "id": 1,
  "title": "Explain vendor-agnostic adapters",
  "type": "generic",
  "input": "Why keep LLM adapters vendor-agnostic?",
  "output": "Short explanation",
  "success_criteria": ["mentions adapter layer", "mentions portability"]
}'
```

### review

Reviews a step result against its success criteria. Prints `approved=True/False`
and the number of issues found. Both arguments are JSON strings.

```bash
uv run advisor --env dev review \
  "$(cat docs/steps/step_generic.json)" \
  '{"id": 1, "executor": "generic", "content": "...", "assumptions": []}'
```

### flow

Full pipeline: Planner produces a plan, each step is executed then reviewed by
the Reviewer. Failed steps are retried with Reviewer feedback injected into the
executor prompt. Retries up to `orchestrator.max_retries` from
`config/<env>/app.yaml`.

```bash
uv run advisor --env prod flow "Implement a Python helper that loads role prompts from the filesystem."
```

## Configuration

- `config/<env>/app.yaml` — LLM provider, DB path, prompts directory, `orchestrator.max_retries`
- `config/<env>/models.yaml` — role-to-model mapping (`planner`, `generic_executor`, `code_executor`, `reviewer`)
- `prompts/<role>/system.md` + `user.md` — role system prompts and user templates

## Environments

- `test` — mock LLM, no network, used in CI and unit tests
- `dev` — OpenAI-compatible proxy at `localhost:4000`, for local development
- `prod` — OpenAI-compatible proxy at `localhost:4000`, for production use
