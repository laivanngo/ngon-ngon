#!/bin/bash
# =============================================================================
# Entrypoint — Chạy migration TRƯỚC KHI app start
# =============================================================================
# WHY entrypoint thay vì migration trong app code:
# 1. Race condition: 2 Uvicorn workers cùng chạy migration = corrupt DB
# 2. Separation of concerns: migration là deploy step, không phải runtime step
# 3. Fail fast: migration lỗi → container không start → dễ phát hiện
# 4. Idempotent: Alembic track đã chạy migration nào, không chạy lại
# =============================================================================

set -e  # Dừng ngay nếu bất kỳ lệnh nào fail

echo "🔄 Running database migrations..."

# Retry loop: chờ DB sẵn sàng (có thể start chậm hơn API container)
# WHY retry: depends_on healthcheck chỉ đảm bảo DB container running,
# nhưng PostgreSQL cần thêm vài giây để accept connections sau restart
MAX_RETRIES=15
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    # Thử chạy migration
    if alembic upgrade head 2>&1; then
        echo "✅ Migrations applied successfully"
        break
    fi

    if [ $i -eq $MAX_RETRIES ]; then
        echo "❌ Failed to apply migrations after $MAX_RETRIES attempts"
        exit 1
    fi

    echo "⏳ Database not ready, retrying in ${RETRY_INTERVAL}s... ($i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

# Chạy seed nếu DB trống (lần đầu deploy)
python -c "
import asyncio
from app.database import async_session
from app.catalog.infrastructure.orm_models import Category
from sqlalchemy import select

async def check():
    async with async_session() as db:
        result = await db.execute(select(Category).limit(1))
        if not result.scalar_one_or_none():
            print('📦 Empty database detected, running seed...')
            from scripts.seed import seed_all
            await seed_all()
        else:
            print('✅ Database already has data, skipping seed')

asyncio.run(check())
" 2>&1 || echo "⚠️ Auto-seed skipped (run 'make seed' manually if needed)"

echo "🚀 Starting Uvicorn..."

# Exec replaces shell process with uvicorn (proper signal handling)
# WHY exec: SIGTERM từ Docker đến trực tiếp Uvicorn, không qua shell
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-1}" \
    --limit-concurrency 100 \
    --timeout-graceful-shutdown 30 \
    --access-log
