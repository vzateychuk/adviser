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

## Tests

```bash
uv run pytest -q
```