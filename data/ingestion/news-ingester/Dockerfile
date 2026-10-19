FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
COPY list_symbol.txt .
COPY pyproject.toml .
RUN which uv && uv --version
RUN uv pip install --system -r pyproject.toml
COPY ingestion ./ingestion
COPY main.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["python","-m","main"]