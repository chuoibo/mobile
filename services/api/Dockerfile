# Multi-stage so the runtime image carries no build tooling and no test suite.
FROM python:3.12-slim AS build

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements-dev.txt ./
# The dev file is the only pinned set right now. Splitting runtime from dev
# pins is worth doing once there is a second deployment target; pinning both to
# the same resolved tree is better than an unpinned runtime.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements-dev.txt

FROM python:3.12-slim AS runtime

# Non-root. The process handles other people's bank account numbers; there is
# no reason for it to be able to write to its own image.
RUN useradd --create-home --uid 10001 app
WORKDIR /srv

COPY --from=build /venv /venv
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./alembic.ini

USER app
EXPOSE 8000

# No default database URL baked in. A container that silently starts against
# the wrong database is worse than one that refuses to start.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
