from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.models import Base
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Добавляем новые колонки если таблица уже существовала (idempotent)
        await _migrate_biweekly_anomaly(conn)


async def _migrate_biweekly_anomaly(conn):
    """Добавляет anomaly-колонки в biweekly_scores если их ещё нет."""
    from sqlalchemy import text
    migrations = [
        # biweekly_scores
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS anomaly_score FLOAT",
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS is_anomaly BOOLEAN DEFAULT FALSE",
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS anomaly_features JSON",
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS intra_overall_delta FLOAT",
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS intra_burnout_delta FLOAT",
        "ALTER TABLE biweekly_scores ADD COLUMN IF NOT EXISTS intra_delivery_delta FLOAT",
        # performance_scores — weekly anomaly detection
        "ALTER TABLE performance_scores ADD COLUMN IF NOT EXISTS week_anomaly_score FLOAT",
        "ALTER TABLE performance_scores ADD COLUMN IF NOT EXISTS week_is_anomaly BOOLEAN DEFAULT FALSE",
        "ALTER TABLE performance_scores ADD COLUMN IF NOT EXISTS week_anomaly_features JSON",
    ]
    for stmt in migrations:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass  # колонка уже существует или таблица не создана ещё


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
