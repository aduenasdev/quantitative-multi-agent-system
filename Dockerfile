# syntax=docker/dockerfile:1.7
# Multi-stage image.
#   base:    Python + uv, no project code.
#   dev:     every dependency including dev tools; used by compose.yml with the source bind-mounted.
#   build:   installs the package and its runtime dependencies into /opt/venv (no dev tools).
#   runtime: slim production image: the virtual environment, the examples, a non-root user.
# The virtual environment lives in /opt/venv so that a bind mount of the source never hides it.

ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# --------------------------------------------------------------------------------------------- dev
FROM base AS dev
# git is needed by the repository check (git ls-files).
RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
ENV QMAS_DATA_DIR=/app/data
CMD ["poe", "check"]

# ------------------------------------------------------------------------------------------- build
FROM base AS build
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ----------------------------------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QMAS_DATA_DIR=/data
RUN useradd --create-home --uid 10001 qmas \
    && mkdir /data \
    && chown qmas:qmas /data
COPY --from=build /opt/venv /opt/venv
COPY examples /app/examples
WORKDIR /app
USER qmas
VOLUME ["/data"]
ENTRYPOINT ["qmas"]
CMD ["--help"]
