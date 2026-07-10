"""
Security - JWT Authentication and Password Hashing
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

import bcrypt

def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": "ksp_crime_intelligence_platform",
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT access token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """Get the expiry datetime of a JWT token"""
    payload = decode_access_token(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return None


# FastAPI dependency for JWT authentication
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.redis_connection import is_token_blacklisted

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency to get the current authenticated user"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Try cookie first, then fallback to Bearer token for backward compatibility
    token = request.cookies.get("auth_token")
    if not token and credentials:
        token = credentials.credentials
        
    if not token:
        raise credentials_exception
    
    # Check if token is blacklisted
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please login again.",
        )
    
    # Decode the token
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
    
    user_id = payload.get("user_id")
    if not user_id:
        raise credentials_exception
    
    return {
        "user_id": payload.get("user_id"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "district_id": payload.get("district_id"),
        "police_station_id": payload.get("police_station_id"),
        "permissions": payload.get("permissions", []),
        "token": token,
    }


def require_role(required_roles: list):
    """Create a dependency that requires specific roles"""
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if current_user["role"] not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}",
            )
        return current_user
    return role_checker


async def require_scrb_officer(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dependency that requires SCRB_OFFICER role"""
    if current_user["role"] != "SCRB_OFFICER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. SCRB Officer role required.",
        )
    return current_user

def scope_district_filter(query, user, model_district_col):
    """Filter database query based on user's district role."""
    if user["role"] == "DISTRICT_OFFICER" and user.get("district_id"):
        return query.where(model_district_col == user["district_id"])
    return query

def scope_district_param(requested_district: Optional[str], user: Dict[str, Any]) -> Optional[str]:
    """Ensure DISTRICT_OFFICER can only request their own district."""
    if user["role"] == "DISTRICT_OFFICER":
        user_district = user.get("district_id")
        if requested_district and requested_district != user_district:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. District officers can only access their own district data."
            )
        return user_district
    return requested_district


