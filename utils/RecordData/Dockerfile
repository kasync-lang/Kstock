FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY requirements.txt requirements.txt
RUN uv pip install --system -r requirements.txt
COPY src ./src
CMD ["python3", "-m", "src.main"]