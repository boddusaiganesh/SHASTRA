"""
Karnataka State Police - Crime Intelligence & Analytical Platform
Module 2 - FastAPI Backend - Main Entry Point
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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
    victims_router,
    import_router,
    search_router,
    evidence_router,
    assistant_router,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

import subprocess
import os

_db_ready = False

import platform

def start_local_postgres():
    if os.environ.get("ENVIRONMENT", "local") == "development" and platform.system() == "Windows":
        import subprocess
        logger.info("Local development environment on Windows detected. Attempting to start PostgreSQL...")
        try:
            # Check if postgres is already running
            subprocess.run(['pg_isready'], check=True, capture_output=True)
            logger.info("PostgreSQL is already running.")
        except subprocess.CalledProcessError:
            try:
                # Start postgres (adjust path as needed for local setup)
                pg_ctl_path = r"D:\PostgreSQL_17\bin\pg_ctl.exe"
                data_dir = r"D:\PostgreSQL_17\data"
                if os.path.exists(pg_ctl_path) and os.path.exists(data_dir):
                    subprocess.Popen([pg_ctl_path, "start", "-D", data_dir])
                    logger.info("Started PostgreSQL service.")
                else:
                    logger.warning("Could not find PostgreSQL installation to auto-start.")
            except Exception as e:
                logger.error(f"Failed to start PostgreSQL: {e}")
    else:
        # Silently skip on production/containerized or non-Windows environments
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global _db_ready
    print("🚀 Starting SHASTRA - Crime Intelligence Platform Backend...")
    start_local_postgres()
    
    try:
        await init_db()
        _db_ready = True
        print("✅ PostgreSQL Database connected and tables created")
    except Exception as e:
        print(f"⚠️  Database not available: {e} — continuing in degraded mode")
    
    try:
        await init_redis()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        
    try:
        from app.core.gemini_client import init_gemini_models
        await init_gemini_models()
        print("✅ Gemini AI Models initialized")
    except Exception as e:
        print(f"❌ Gemini AI init failed: {e}")


    
    try:
        init_neo4j()
        print("✅ Neo4j Graph Database connected")
    except Exception as e:
        print(f"⚠️  Neo4j unavailable: {e} — continuing in degraded mode")
    
    if _db_ready:
        init_scheduler()
        print("✅ APScheduler started - Background intelligence tasks running")
    else:
        print("⚠️  Scheduler NOT started — database unavailable")
    
    print("✅ All systems operational. Backend ready on port", settings.BACKEND_PORT)
    
    yield
    
    print("🔄 Shutting down SHASTRA Intelligence Platform Backend...")
    if _db_ready:
        shutdown_scheduler()
    await close_redis()
    close_neo4j()


app = FastAPI(
    title="SHASTRA - Crime Intelligence Platform",
    description="""
    ## SHASTRA Intelligence Platform API
    
    A state-of-the-art backend platform powering the Karnataka State Police (KSP)
    Crime Intelligence System.
    """,
    version="1.0.0",
    contact={"name": "SCRB Technical Team", "email": "scrb@ksp.gov.in"},
    license_info={"name": "Karnataka State Police - Internal Use Only"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    headers = {}
    # Apply CORS headers for 500 responses
    headers["Access-Control-Allow-Origin"] = origin if origin else "*"
    headers["Access-Control-Allow-Credentials"] = "true"
    
    logger.error(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "message": str(exc)},
        headers=headers
    )

# Security and Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
allowed_origins = []
if settings.ENVIRONMENT == "production":
    allowed_origins = [settings.FRONTEND_URL]
else:
    allowed_origins = [
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Static files for evidence uploads
import os
os.makedirs("app/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

# Include routers
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
app.include_router(victims_router.router, prefix="/api/victims", tags=["Victims"])
app.include_router(import_router.router, prefix="/api/import", tags=["Import"])
app.include_router(search_router.router, prefix="/api/search", tags=["Search"])
app.include_router(evidence_router.router, prefix="/api/evidence", tags=["Evidence"])
app.include_router(assistant_router.router, prefix="/api/assistant", tags=["Assistant"])


@app.get("/", tags=["Health"])
async def root():
    return {"success": True, "message": "SHASTRA API is running"}

@app.get("/api/health", tags=["Health"])
async def health_check():
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
            "scheduler": "running" if _db_ready else "stopped",
        }
    }

if __name__ == "__main__":
    workers = 1 if settings.ENVIRONMENT == "development" else 4
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=settings.ENVIRONMENT == "development",
        workers=workers,
        log_level="info",
    )
