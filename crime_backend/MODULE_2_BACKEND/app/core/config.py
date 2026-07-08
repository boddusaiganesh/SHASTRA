"""
Core Configuration - Loads all environment variables using Pydantic Settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
import logging
from dotenv import load_dotenv
from pydantic import field_validator

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://admin:securepassword@localhost:5432/crime_intelligence_db"
    DATABASE_URL_SYNC: str = "postgresql://admin:securepassword@localhost:5432/crime_intelligence_db"
    DATABASE_NAME: str = "crime_intelligence_db"
    DATABASE_USER: str = "admin"
    DATABASE_PASSWORD: str = "securepassword"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432

    # Neo4j
    NEO4J_URL: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4jsecurepassword"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: str = ""
    CACHE_EXPIRY_SECONDS: int = 900

    # Gemini AI
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.3

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 8

    # Server
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ENVIRONMENT: str = "development"
    
    # SMTP Notifications
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_FROM: str = "noreply@shastra.gov.in"
    
    # Initial Seeding
    SEED_ADMIN_PASSWORD: Optional[str] = None

    # Scheduling
    HOTSPOT_UPDATE_HOUR: int = 2
    FORECAST_UPDATE_DAY: str = "sunday"
    ANOMALY_SCAN_INTERVAL_HOURS: int = 6

    # Thresholds
    CRIME_SPIKE_THRESHOLD: int = 50
    HOTSPOT_MIN_CRIMES: int = 5
    RISK_HIGH_THRESHOLD: int = 75
    RISK_MEDIUM_THRESHOLD: int = 40
    ANOMALY_SENSITIVITY: str = "MEDIUM"
    PREDICTION_CONFIDENCE_MIN: int = 60

    def get_gemini_api_keys(self) -> list[str]:
        keys = []
        if self.GEMINI_API_KEYS:
            keys.extend([k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()])
        elif self.GEMINI_API_KEY:
            keys.append(self.GEMINI_API_KEY)
        return keys

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt(cls, v):
        if v == "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN":
            env = os.environ.get("ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a unique secret before running in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
                )
            logging.getLogger(__name__).warning("⚠️ JWT_SECRET_KEY is using the default dev value.")
        return v


settings = Settings()

# ============================================================
# Shared Constants - Both Module 1 and Module 2 must use these
# ============================================================

CRIME_TYPES = [
    "Theft",
    "Murder",
    "Robbery",
    "Assault",
    "Kidnapping",
    "Fraud",
    "Drug Offense",
    "Sexual Offense",
    "Vehicle Theft",
    "Burglary",
    "Cybercrime",
    "Domestic Violence",
]

RISK_LEVELS = ["HIGH", "MEDIUM", "LOW"]

SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

CRIME_STATUS_VALUES = ["REPORTED", "UNDER_INVESTIGATION", "SOLVED", "CLOSED", "ARCHIVED"]

OFFENDER_STATUS_VALUES = ["ACTIVE", "IMPRISONED", "ABSCONDING", "DECEASED"]

ANOMALY_STATUS_VALUES = ["NEW", "UNDER_REVIEW", "RESOLVED", "FALSE_POSITIVE"]

ALERT_TYPES = [
    "CRIME_SPIKE",
    "HOTSPOT_EMERGING",
    "KNOWN_CRIMINAL",
    "ANOMALY_DETECTED",
    "NETWORK_DISCOVERED",
    "PREDICTION_BREACH",
    "CROSS_DISTRICT_MATCH",
]

NODE_TYPES = ["criminal", "victim", "location", "organization"]

RELATIONSHIP_TYPES = [
    "KNOWS",
    "WORKED_WITH",
    "TARGETS",
    "OPERATES_IN",
    "MEMBER_OF",
    "VICTIMIZED_AT",
    "LINKED_TO",
    "FREQUENTED",
]

USER_ROLES = ["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]

TRENDS = ["INCREASING", "STABLE", "DECREASING"]

TIME_OF_DAY = {
    "MORNING": {"start": 6, "end": 12},
    "AFTERNOON": {"start": 12, "end": 18},
    "EVENING": {"start": 18, "end": 22},
    "NIGHT": {"start": 22, "end": 6},
}

# Karnataka Districts
KARNATAKA_DISTRICTS = [
    {"district_id": "KA-01", "district_name": "Bengaluru Urban", "district_code": "BLR", "headquarters": "Bengaluru"},
    {"district_id": "KA-02", "district_name": "Bengaluru Rural", "district_code": "BLR-R", "headquarters": "Bengaluru"},
    {"district_id": "KA-03", "district_name": "Mysuru", "district_code": "MYS", "headquarters": "Mysuru"},
    {"district_id": "KA-04", "district_name": "Tumakuru", "district_code": "TMK", "headquarters": "Tumakuru"},
    {"district_id": "KA-05", "district_name": "Kolar", "district_code": "KLR", "headquarters": "Kolar"},
    {"district_id": "KA-06", "district_name": "Mandya", "district_code": "MND", "headquarters": "Mandya"},
    {"district_id": "KA-07", "district_name": "Hassan", "district_code": "HSN", "headquarters": "Hassan"},
    {"district_id": "KA-08", "district_name": "Dakshina Kannada", "district_code": "DK", "headquarters": "Mangaluru"},
    {"district_id": "KA-09", "district_name": "Udupi", "district_code": "UDU", "headquarters": "Udupi"},
    {"district_id": "KA-10", "district_name": "Shivamogga", "district_code": "SMG", "headquarters": "Shivamogga"},
    {"district_id": "KA-11", "district_name": "Chikkamagaluru", "district_code": "CKM", "headquarters": "Chikkamagaluru"},
    {"district_id": "KA-12", "district_name": "Kodagu", "district_code": "KDG", "headquarters": "Madikeri"},
    {"district_id": "KA-13", "district_name": "Belagavi", "district_code": "BLG", "headquarters": "Belagavi"},
    {"district_id": "KA-14", "district_name": "Dharwad", "district_code": "DHW", "headquarters": "Dharwad"},
    {"district_id": "KA-15", "district_name": "Gadag", "district_code": "GDG", "headquarters": "Gadag"},
    {"district_id": "KA-16", "district_name": "Haveri", "district_code": "HVR", "headquarters": "Haveri"},
    {"district_id": "KA-17", "district_name": "Uttara Kannada", "district_code": "UK", "headquarters": "Karwar"},
    {"district_id": "KA-18", "district_name": "Vijayapura", "district_code": "VJP", "headquarters": "Vijayapura"},
    {"district_id": "KA-19", "district_name": "Bagalkote", "district_code": "BGL", "headquarters": "Bagalkote"},
    {"district_id": "KA-20", "district_name": "Bidar", "district_code": "BDR", "headquarters": "Bidar"},
    {"district_id": "KA-21", "district_name": "Kalaburagi", "district_code": "KLB", "headquarters": "Kalaburagi"},
    {"district_id": "KA-22", "district_name": "Yadgir", "district_code": "YDG", "headquarters": "Yadgir"},
    {"district_id": "KA-23", "district_name": "Raichur", "district_code": "RCH", "headquarters": "Raichur"},
    {"district_id": "KA-24", "district_name": "Koppal", "district_code": "KPL", "headquarters": "Koppal"},
    {"district_id": "KA-25", "district_name": "Ballari", "district_code": "BLR-B", "headquarters": "Ballari"},
    {"district_id": "KA-26", "district_name": "Vijayanagara", "district_code": "VJN", "headquarters": "Hosapete"},
    {"district_id": "KA-27", "district_name": "Davangere", "district_code": "DVG", "headquarters": "Davangere"},
    {"district_id": "KA-28", "district_name": "Chitradurga", "district_code": "CTD", "headquarters": "Chitradurga"},
    {"district_id": "KA-29", "district_name": "Ramanagara", "district_code": "RMN", "headquarters": "Ramanagara"},
    {"district_id": "KA-30", "district_name": "Chamarajanagar", "district_code": "CMJ", "headquarters": "Chamarajanagar"},
    {"district_id": "KA-31", "district_name": "Chikkaballapur", "district_code": "CKB", "headquarters": "Chikkaballapur"},
]
