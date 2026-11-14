FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project

COPY --chown=10001:10001 backend/app ./app
COPY --chown=10001:10001 backend/tests ./tests
COPY --chown=10001:10001 scripts/test_scaffold.py /opt/archpath/scripts/test_scaffold.py

RUN addgroup --system --gid 10001 archpath \
    && adduser --system --uid 10001 --ingroup archpath --home /home/archpath archpath \
    && chown -R archpath:archpath /app /opt/archpath

USER archpath

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
