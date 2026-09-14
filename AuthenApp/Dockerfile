FROM python:3.12-slim
WORKDIR /authapp
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
#RUN groupadd -r appgroup && useradd -r -g appgroup -m -d /home/appuser appuser
#
#RUN chown -R appuser:appgroup /authapp
#USER appuser
COPY ./app ./app/
EXPOSE 8000
ENV PYTHONPATH=/authapp

CMD ["uvicorn", "app.main:app","--host","0.0.0.0","--port", "8000"]