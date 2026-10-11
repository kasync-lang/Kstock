FROM python:3.12-slim

WORKDIR /authapp

RUN pip install --no-cache-dir uv \
    && groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home --home-dir /home/appuser appuser

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=appuser:appgroup ./app ./app/

# Nếu ứng dụng cần ghi vào thư mục project (log, file tạm, v.v.)
RUN chown -R appuser:appgroup /authapp

USER appuser

EXPOSE 8000

CMD ["uv","run","--frozen","--no-dev","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]