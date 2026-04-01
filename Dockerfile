FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY scripts/ scripts/

RUN uv lock && uv sync --frozen --no-dev

EXPOSE 8100

CMD ["uv", "run", "--no-sync", "prompt-cli", "run_api"]
