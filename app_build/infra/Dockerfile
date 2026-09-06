FROM python:3.12-slim

# Install system utilities & copy official uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create unprivileged non-root user (Principle of Least Privilege - PoLP)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Cache dependency layer
COPY app_build/pyproject.toml app_build/uv.lock app_build/README.md /app/app_build/

WORKDIR /app/app_build
RUN uv sync --frozen --no-dev

# Copy application source and web UI assets
COPY app_build/src /app/app_build/src
COPY app_build/static /app/app_build/static

# Grant ownership to non-root appuser
RUN chown -R appuser:appgroup /app

USER appuser

ENV PORT=8000
EXPOSE 8000

# PID 1 POSIX signal forwarding with dynamic cloud port injection
CMD ["sh", "-c", "exec uv run python -m uvicorn trustfork.server:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
