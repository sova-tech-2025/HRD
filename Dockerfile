FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (layer cached separately from code)
COPY pyproject.toml .
RUN mkdir -p src/bot && touch src/bot/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf src/

COPY . .

ENV PYTHONPATH=/app/src

RUN mkdir -p /app/logs && chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
