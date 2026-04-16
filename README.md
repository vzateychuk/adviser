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

### Examples

#### Ask

```bash
advisor --env prod ask "Create a 3-step plan to add filesystem prompts loading to the project. Return JSON only." --role planner

#  Ask dev planner
advisor --env prod ask "Write a Python function load_role_prompt(role: str) -> str that loads prompts/<role>.md using pathlib." --role code_executor
```

#### Plan

Planner (returns JSON plan):

`plan` calls the Planner and expects a valid JSON plan (validated by Pydantic).  
It is **not** a chat command. Inputs like "hello" may fail validation.

```bash
advisor --env prod plan "Create a 3-step plan to implement X. Return JSON only."