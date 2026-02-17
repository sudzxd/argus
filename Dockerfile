FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Cache dependency layer
COPY pyproject.toml uv.lock .python-version README.md ./

RUN uv sync --no-dev --frozen

# Copy source last for best layer caching
COPY src/ src/

ENTRYPOINT ["uv", "run", "python", "-m", "argus.interfaces.action"]
