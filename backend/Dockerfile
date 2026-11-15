FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml ./
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      uv pip install -r pyproject.toml --extra dev; \
    else \
      uv pip install -r pyproject.toml; \
    fi

COPY . .

# Cloud Run injects PORT; APP_ROLE=api|worker selects which routers are mounted.
ENV PORT=8080 APP_ROLE=api
EXPOSE 8080
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
