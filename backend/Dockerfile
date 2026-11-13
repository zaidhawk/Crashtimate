FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Dependencies first, so editing the code doesn't reinstall them on every build.
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
RUN pip install --no-cache-dir .

COPY app ./app
RUN pip install --no-cache-dir --no-deps .

# Run as an ordinary user, with a folder it owns for the SQLite file. Mount a volume at
# /data to keep cached analyses and saved estimates across deploys.
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
USER appuser

ENV CRASHTIMATE_DATABASE_PATH=/data/crashtimate.db \
    PORT=8000
EXPOSE 8000

# One worker: the rate limiter keeps its counts in this process's memory.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
