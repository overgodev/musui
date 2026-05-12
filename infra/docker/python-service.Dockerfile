FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY docs ./docs
COPY infra ./infra
COPY scripts ./scripts
COPY services ./services
COPY shared ./shared
COPY tests ./tests

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "uvicorn", "services.gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
