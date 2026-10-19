FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install uv && uv pip install --system -r pyproject.toml
COPY src ./src
RUN useradd -m app
USER app
ENTRYPOINT ["python3", "-m", "src.main"]