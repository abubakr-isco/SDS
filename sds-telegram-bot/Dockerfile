FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY config ./config
COPY app ./app

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home sds && chown -R sds /app
USER sds

# Apply migrations, then start long polling.
CMD ["sh", "-c", "alembic upgrade head && exec python -m app"]
