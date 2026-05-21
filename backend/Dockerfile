# Backend image — Python 3.12 + uv.
FROM python:3.12-slim

# uv: fast Python package/deps manager.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for better layer caching.
# --frozen: use the committed uv.lock as-is (reproducible builds, no resolution).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Application code.
COPY . .
RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
