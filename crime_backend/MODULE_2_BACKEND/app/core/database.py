"""
PostgreSQL Database Connection using SQLAlchemy Async
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from typing import AsyncGenerator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database and create tables"""
    # Import all models here to ensure they are registered with Base.metadata before create_all
    # Import in order of dependency (parent tables before child tables)
    from app.models.database_models.user_model import User
    from app.models.database_models.crime_model import District, PoliceStation, Crime, CrimeOffenderLink, CrimeVictimLink
    from app.models.database_models.offender_model import Offender
    from app.models.database_models.victim_model import Victim
    from app.models.database_models.location_model import Hotspot, Location, SocioeconomicData
    from app.models.database_models.prediction_model import Prediction
    from app.models.database_models.alert_model import Alert
    from app.models.database_models.anomaly_model import Anomaly
    from app.models.database_models.report_model import Report
    from app.models.database_models.system_settings_model import SystemSettings

    # Enable PostGIS extension (optional if installed) in its own transaction so errors don't abort create_all
    try:
        async with engine.connect() as ext_conn:
            await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            await ext_conn.commit()
    except Exception as ext_e:
        logger.warning(f"Optional PostgreSQL extensions not available: {ext_e}")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
        # Seed initial data
        await seed_initial_data()
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        # Don't raise - allow app to start even if DB is not ready in dev mode


async def seed_initial_data():
    """Seed the database with initial data if empty"""
    try:
        async with AsyncSessionLocal() as session:
            from app.models.database_models.user_model import User
            from sqlalchemy import select
            
            # Check if data already exists
            result = await session.execute(select(User).limit(1))
            if result.scalar_one_or_none():
                return  # Data already seeded
            
            # Import and run seeder
            from app.utils.data_seeder import seed_all_data
            await seed_all_data(session)
            logger.info("Initial data seeded successfully")
            
    except Exception as e:
        logger.warning(f"Data seeding skipped: {e}")


async def get_db_health() -> str:
    """Check database health"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return "healthy"
    except Exception as e:
        return f"unhealthy: {str(e)}"
