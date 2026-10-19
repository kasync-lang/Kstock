FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install uv && uv pip install --system -r pyproject.toml
COPY *.py ./
RUN rm -f test_*.py && useradd -m app
USER app
# One-shot job, e.g.: docker compose run --rm news-processing --symbol AAPL --date 2026-10-14
ENTRYPOINT ["python3", "pipeline.py"]
CMD ["--help"]
