from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config.settings import settings
from app.models.alert import Base
import asyncio
from loguru import logger

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    future=True
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Sync engine for setup and migrations
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG
)


async def init_db():
    """Initialize database tables"""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def get_db_session():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


def create_sync_session():
    """Create synchronous session for scripts"""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sync_engine)
    return SessionLocal()
