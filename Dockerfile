# Setu app image. Build: docker compose build   Run: docker compose up
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY setu ./setu
COPY pipeline ./pipeline
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "setu.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
