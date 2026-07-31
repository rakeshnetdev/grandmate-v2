# Backend container.
#
# Stockfish is installed in the image rather than assumed on the host: the analysis core
# is useless without it, and "works on my machine" is not an acceptable property for the
# component that produces the system's ground truth.
#
# Hosting is deferred to Phase 17 (D-006). This image exists so development is consistent
# and so the deployment decision is not foreclosed.

FROM python:3.13-slim

# Stockfish from Debian, plus curl for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create a non-root user
RUN groupadd -g 10001 grandmate && \
    useradd -u 10001 -g grandmate -m -s /sbin/nologin grandmate

WORKDIR /app

# Ensure storage directory exists and is writable by non-root user
RUN mkdir -p /app/.storage && chown -R grandmate:grandmate /app

# Dependencies first so a source change does not invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and required assets
COPY app ./app
COPY data ./data
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

RUN chown -R grandmate:grandmate /app

USER grandmate

# API_HOST overrides the loopback default from .env: a container must bind all interfaces
# or the published port reaches nothing.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STOCKFISH_PATH=/usr/games/stockfish \
    API_HOST=0.0.0.0

EXPOSE 7575

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD curl -fsS http://localhost:7575/health || exit 1

# Entrypoint reads host and port from configuration rather than repeating them here.
CMD ["python", "-m", "app"]

