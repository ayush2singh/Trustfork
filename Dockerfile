FROM python:3.12-slim

# Copy uv binary directly from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency specifications first for Docker layer caching
COPY app_build/pyproject.toml app_build/uv.lock app_build/README.md /app/app_build/

WORKDIR /app/app_build
RUN uv sync --frozen --no-dev

# Copy application source code and web static assets
COPY app_build/src /app/app_build/src
COPY app_build/static /app/app_build/static

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "uvicorn", "trustfork.server:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
