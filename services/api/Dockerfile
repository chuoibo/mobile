# syntax=docker/dockerfile:1

# Base pinned by digest, not by tag. `python:3.12-slim` is mutable: the tag gets
# re-pushed on every upstream patch, so two builds of the same commit can differ
# without anyone changing a line. The digest below is an OCI image *index*, so it
# still resolves to the right per-architecture image on amd64 and arm64.
#
# To bump: docker buildx imagetools inspect python:3.12-slim  -> copy the Digest,
# then rebuild and re-record the size/time numbers in docs.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

# ---------------------------------------------------------------------------
# build: resolves dependencies into a venv that the runtime stage copies whole.
# Nothing from this stage other than /venv reaches the final image.
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS build

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY pyproject.toml requirements-dev.txt ./

# Two files, two different jobs, no third copy of the pins to drift:
#   - pyproject.toml     declares WHICH packages the app needs at runtime
#   - requirements-dev.txt pins WHICH VERSION the whole tree resolves to
# Feeding the second in as a constraints file means the runtime image gets the
# same resolved versions CI tests against, without dragging pytest/ruff/httpx in.
# Extras are stripped because pip rejects them in a constraints file.
RUN sed -E 's/\[[^]]*\]//' requirements-dev.txt > /tmp/constraints.txt \
 && python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/runtime.txt \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --constraint /tmp/constraints.txt -r /tmp/runtime.txt

# Fail the build if test tooling reached the venv. This is the guard for the
# thing this stage exists to do; without it the split silently rots back.
RUN for tool in pytest ruff; do \
      if [ -e "/venv/bin/$tool" ]; then echo "FATAL: dev tool '$tool' leaked into the runtime venv" >&2; exit 1; fi; \
    done

# ---------------------------------------------------------------------------
# runtime: no compiler, no pip cache, no test suite, no dev tooling.
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# Non-root. The process handles other people's bank account numbers; there is
# no reason for it to be able to write to its own image.
RUN useradd --create-home --uid 10001 app
WORKDIR /srv

# The mount point for uploaded photos, created here so that it is owned by the
# runtime user. This is not decoration: Docker copies ownership from the image
# when it first populates an empty named volume, and when the path is ABSENT
# from the image it creates the mount point as root:root 0755 instead. Measured
# on this image, uid 10001 writing into a fresh volume at a path the image does
# not contain:
#
#   drwxr-xr-x 2 0 0 /var/lib/rudi/media
#   touch: cannot touch '/var/lib/rudi/media/x': Permission denied
#
# So a compose file that mounts a volume here without this line does not lose
# photos on rebuild -- it refuses to store them at all, which is worse, because
# the failure arrives on the first upload rather than on the first rebuild.
# `/var/lib` and not `/srv`: /srv holds the application code, and a writable
# directory inside the code tree is how an upload path turns into a code path.
RUN mkdir -p /var/lib/rudi/media && chown app:app /var/lib/rudi/media

# /venv stays root-owned on purpose: the app may read its dependencies, not
# rewrite them.
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
#
# /healthz deliberately does not touch the database (see CLAUDE.md): this probe
# answers "is the API process serving?", not "is Postgres up?". Restarting the
# container cannot fix Postgres, so tying the two together would only cause
# pointless restart loops.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
