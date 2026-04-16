# advisor

## Run

Default environment is `dev`:

```bash
uv run python -m cli.main
# or
uv run advisor
# or
advisor

# Run with explicit environment:
uv run advisor --env prod
# or
advisor --env prod
```
## Ask

Send a one-shot request to the LLM selected for the given role (from `config/<env>/models.yaml`):

```bash
# test env uses mock (no network)
advisor --env test ask "hello"

# prod/dev env uses real LLM via proxy
advisor --env prod ask "Reply with exactly: pong" --role planner

## Tests

```bash
uv run pytest -q
```

## Examples

### Ask

One-shot LLM request using role prompts from `prompts/` and model aliases from `config/<env>/models.yaml`.

```bash
# Default role is generic_executor
advisor --env prod ask "Summarize why we keep LLM adapters vendor-agnostic."

# Ask code executor (returns code)
advisor --env prod ask "Write a Python function load_role_prompt(role: str) -> str that loads prompts/<role>.md using pathlib." --role code_executor
```

#### Plan

plan calls the Planner and expects a valid JSON plan (validated by Pydantic / PlanResult).
It is not a chat command. Inputs like "hello" may fail validation.

```bash
advisor --env prod plan "Create a 3-step plan to implement X. Return JSON only."
```

#### Exec step

Execute a single PlanStep (debug command) using the executor selected by step.type.

```bash
advisor --env prod exec-step "$(cat docs/steps/step_generic.json)"
advisor --env prod exec-step "$(cat docs/steps/step_code.json)"
```

#### Critic (temporary)

Temporary manual input until a dedicated review command / critic loop is implemented:

```bash
advisor --env prod ask --role critic "STEP: Implement summarize_previous_results helper. STEP_RESULT: It truncates to 200 chars and loses structure. SUCCESS_CRITERIA: Must include first 20 lines and keep readability. Return JSON verdict."
```