# =============================================================================
# Stage 1: Builder — cài dependencies
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Stage 2: Runtime — production image
# =============================================================================
FROM python:3.12-slim

# WHY non-root user: limit blast radius if app gets compromised
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
# .dockerignore ensures .env, tests/, __pycache__ are excluded
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# WHY entrypoint thay vì CMD trực tiếp:
# entrypoint.sh chạy migration TRƯỚC Uvicorn → no race condition
ENTRYPOINT ["./entrypoint.sh"]
