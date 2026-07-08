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
    """
    Base class for all SQLAlchemy models in the application.
    Inherits from DeclarativeBase to enable declarative mapping, providing a 
    common base for table definitions and model relationships across the system.
    """
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for FastAPI endpoints to get an asynchronous database session.
    
    Yields:
        AsyncSession: An asynchronous SQLAlchemy session connected to the PostgreSQL database.
        
    Raises:
        Exception: Re-raises any exception encountered during the session, and triggers a rollback.
        
    Note:
        This function is designed to be used with FastAPI's Depends() injection.
        It handles automatic commit if the transaction is successful, and rollback if it fails.
        The session is automatically closed in the finally block.
    """
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
    """
    Initialize the database connection and setup required extensions.
    
    This function performs the following actions:
    1. Loads all ORM models to ensure they are registered with SQLAlchemy's Base.metadata.
    2. Connects to PostgreSQL and attempts to create 'postgis' and 'pg_trgm' extensions.
       These extensions are required for geospatial queries and text search respectively.
    3. Seeds initial data if the database is empty.
    
    Returns:
        bool: True if initialization was successful.
        
    Raises:
        Exception: If database initialization fails, it raises an exception which should
                   be caught by the caller to handle degraded modes or failure states.
    """
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
    from app.models.database_models.evidence_model import Evidence

    # Enable PostGIS extension (optional if installed) in its own transaction so errors don't abort create_all
    try:
        async with engine.connect() as ext_conn:
            await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            await ext_conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            await ext_conn.commit()
    except Exception as ext_e:
        logger.warning(f"Optional PostgreSQL extensions not available: {ext_e}")

    try:
        logger.info("Database tables initialized via Alembic migrations")
        
        # Seed initial data
        await seed_initial_data()
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise


async def seed_initial_data():
    """
    Seed the database with initial mock data if the database is completely empty.
    
    This function checks if there are any existing records in the `User` table.
    If no users exist, it invokes the `seed_all_data` utility to populate the database
    with test entities (e.g. users, districts, crimes, alerts) for development or demo usage.
    """
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
