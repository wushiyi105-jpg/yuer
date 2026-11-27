FROM python:3.10-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY yuer ./yuer
COPY templates ./templates
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --upgrade pip build && pip wheel --no-deps -w /wheels . && \
    pip install --prefix=/install --no-deps /wheels/*.whl && \
    pip install --prefix=/install "fastapi>=0.115" "uvicorn[standard]>=0.30" \
      "python-multipart>=0.0.9" "pydantic>=2.7" "pydantic-settings>=2.3" \
      "httpx>=0.27" "jinja2>=3.1" "typer>=0.12" "rich>=13.7" \
      "sqlalchemy>=2.0" "alembic>=1.13" "tomli>=2"

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 YER_DB_PATH=/data/yuer.db
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app/templates ./templates
COPY --from=builder /app/yuer ./yuer
COPY --from=builder /app/migrations ./migrations
COPY --from=builder /app/alembic.ini ./

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8022

CMD ["uvicorn", "yuer.iface.web:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8022"]
