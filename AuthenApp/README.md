# AuthenApp

Ứng dụng xác thực trung tâm xây bằng FastAPI, Beanie/MongoDB, JWT và OAuth2 Google.

## Chạy test

Đồng bộ môi trường dev:

```bash
uv sync --group dev
```

Chạy toàn bộ test:

```bash
uv run pytest app/test -q
```

Chạy test kèm coverage:

```bash
uv run pytest app/test --cov=app --cov-report=term-missing -q
```

