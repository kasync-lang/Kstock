# AuthenApp

Central authentication application built with FastAPI, Beanie/MongoDB, JWT, and Google OAuth2.

## Running tests

Sync the dev environment:

```bash
uv sync --group dev
```

Run all tests:

```bash
uv run pytest app/test -q
```

Run tests with coverage:

```bash
uv run pytest app/test --cov=app --cov-report=term-missing -q
```
