# syntax=docker/dockerfile:1.7

# Multi-stage build. Dev deps live in the builder; the runtime image is
# non-root, minimal, and runs under a HEALTHCHECK. Image builds happen in
# GitHub Actions (see .github/workflows/docker.yaml), never via local
# `docker compose build` (project policy, S-7).
#
# VERIFY: before cutting a release, replace the python tag below with a
# @sha256 digest pin. The tag form is used here to avoid fabricating a
# digest value during scaffolding.

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install uv (pinned version). COPY'd from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:0.4.20 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --------------------------------------------------------------------------
# Runtime
# --------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system --gid 10001 wageguard \
 && useradd --system --uid 10001 --gid wageguard --home-dir /app --no-create-home wageguard

WORKDIR /app

COPY --from=builder --chown=wageguard:wageguard /app/.venv /app/.venv
COPY --chown=wageguard:wageguard src/ /app/src/
COPY --chown=wageguard:wageguard pyproject.toml /app/pyproject.toml

USER wageguard

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; \
host=os.environ.get('WAGEGUARD_API_HOST','127.0.0.1'); \
port=os.environ.get('WAGEGUARD_API_PORT','8080'); \
r=urllib.request.urlopen(f'http://{host}:{port}/healthz',timeout=3); \
sys.exit(0 if r.status==200 else 1)"

ENTRYPOINT ["wageguard"]
CMD ["--help"]
