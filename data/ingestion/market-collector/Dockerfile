FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install uv && uv pip install --system -r pyproject.toml
COPY src ./src
COPY list_symbol.txt list_symbol.txt
RUN useradd -m app
USER app
CMD ["python3","-m","src.main"]