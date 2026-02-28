FROM python:3.12-slim

RUN pip install --no-cache-dir poetry==1.8.5

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
COPY src/ src/
COPY scripts/ scripts/

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev

EXPOSE 8100

CMD ["prompt-cli", "run_api"]
