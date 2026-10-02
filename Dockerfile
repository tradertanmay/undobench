# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

LABEL maintainer="Tanmay Sah <tradertanmay@gmail.com>"
LABEL description="Official containerized evaluation environment for RecoverBench v1.0.1"

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Install runtime dependencies (git for git sandbox tasks, sqlite3 for db sandbox tasks, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    sqlite3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install the exact distribution wheel
COPY dist/recoverbench-1.0.0-py3-none-any.whl /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip install "/app/recoverbench-1.0.0-py3-none-any.whl[all]" && \
    rm /app/recoverbench-1.0.0-py3-none-any.whl

# Preflight checks inside container
RUN recoverbench doctor && recoverbench smoke

ENTRYPOINT ["recoverbench"]
CMD ["smoke"]
