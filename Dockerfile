FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Cache dependency layer — install deps only (no project yet)
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --no-dev --frozen --no-install-project

# Copy source and install the project itself
COPY src/ src/
RUN uv sync --no-dev --frozen

ENTRYPOINT ["uv", "run", "python", "-m", "argus.interfaces.main"]
