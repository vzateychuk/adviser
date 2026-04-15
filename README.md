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