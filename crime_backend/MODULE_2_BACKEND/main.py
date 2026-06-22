"""
Karnataka State Police - Crime Intelligence & Analytical Platform
Module 2 - FastAPI Backend - Main Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.core.database import init_db
from app.core.redis_connection import init_redis, close_redis
from app.core.neo4j_connection import init_neo4j, close_neo4j
from app.scheduler.scheduled_tasks import init_scheduler, shutdown_scheduler

from app.routers import (
    auth_router,
    dashboard_router,
    crimes_router,
    hotspots_router,
    network_router,
    offenders_router,
    predictions_router,
    anomalies_router,
    alerts_router,
    reports_router,
    settings_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("🚀 Starting Karnataka State Police - Crime Intelligence Platform Backend...")
    
    # Initialize database
    await init_db()
    print("✅ PostgreSQL Database connected and tables created")
    
    # Initialize Redis
    await init_redis()
    print("✅ Redis Cache connected")
    
    # Initialize Neo4j
    init_neo4j()
    print("✅ Neo4j Graph Database connected")
    
    # Initialize Scheduler
    init_scheduler()
    print("✅ APScheduler started - Background intelligence tasks running")
    
    print("✅ All systems operational. Backend ready on port", settings.BACKEND_PORT)
    
    yield
    
    # Shutdown
    print("🔄 Shutting down Crime Intelligence Platform Backend...")
    shutdown_scheduler()
    await close_redis()
    close_neo4j()
    print("✅ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="SHASTRA - Crime Intelligence Platform",
    description="""
    ## SHASTRA Intelligence Platform API
    
    A state-of-the-art backend platform powering the Karnataka State Police (KSP)
    Crime Intelligence System. This API provides:
    
    - **Advanced Crime Analytics** - Spatial and temporal crime pattern analysis
    - **Hotspot Detection** - AI-powered crime cluster identification
    - **Criminal Network Analysis** - Graph-based relationship mapping
    - **Predictive Intelligence** - ML-driven crime forecasting
    - **Anomaly Detection** - Automated unusual pattern detection
    - **Socioeconomic Correlation** - Crime-poverty-urbanization analysis
    - **Gemini AI Integration** - Natural language intelligence reports
    
    ### Authentication
    All endpoints (except /api/auth/login) require a Bearer JWT token.
    
    ### Base URL
    `http://localhost:8000/api`
    
    ### Support
    Karnataka State Crime Records Bureau (SCRB)
    """,
    version="1.0.0",
    contact={
        "name": "SCRB Technical Team",
        "email": "scrb@ksp.gov.in",
    },
    license_info={
        "name": "Karnataka State Police - Internal Use Only",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include all routers
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard_router.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(crimes_router.router, prefix="/api/crimes", tags=["Crimes"])
app.include_router(hotspots_router.router, prefix="/api/hotspots", tags=["Hotspots"])
app.include_router(network_router.router, prefix="/api/network", tags=["Network Analysis"])
app.include_router(offenders_router.router, prefix="/api/offenders", tags=["Offenders"])
app.include_router(predictions_router.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(anomalies_router.router, prefix="/api/anomalies", tags=["Anomalies"])
app.include_router(alerts_router.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(reports_router.router, prefix="/api/reports", tags=["Reports"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])


@app.get("/", tags=["Health"])
async def root():
    """Root health check endpoint"""
    return {
        "success": True,
        "data": {
            "service": "Karnataka State Police - Crime Intelligence Platform",
            "version": "1.0.0",
            "status": "operational",
            "module": "Module 2 - Backend Intelligence Engine",
            "docs": "/docs",
            "api_base": "/api",
        },
        "message": "Crime Intelligence Platform Backend is running",
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Detailed health check for all services"""
    from app.core.database import get_db_health
    from app.core.redis_connection import get_redis_health
    from app.core.neo4j_connection import get_neo4j_health

    return {
        "success": True,
        "data": {
            "api": "healthy",
            "database": await get_db_health(),
            "redis": await get_redis_health(),
            "neo4j": get_neo4j_health(),
            "scheduler": "running",
        },
        "message": "All systems healthy",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
