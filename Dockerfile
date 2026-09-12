FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY kinetix ./kinetix
RUN pip install --no-cache-dir ".[postgres]"

RUN useradd --create-home --uid 1000 kinetix \
    && mkdir -p /app/data \
    && chown -R kinetix:kinetix /app
USER kinetix

VOLUME ["/app/data"]
CMD ["python", "-m", "kinetix"]
