"""
Authentication Service
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

from app.models.database_models.user_model import User
from app.core.security import verify_password, hash_password, create_access_token
from app.core.config import settings
from app.utils.district_resolver import resolve_district_id

logger = logging.getLogger(__name__)


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> Optional[Dict[str, Any]]:
    """Authenticate a user and return user data if valid"""
    
    # Find user by username
    result = await db.execute(
        select(User).where(User.username == username, User.is_active)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Login attempt for non-existent user: {username}")
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        logger.warning(f"Invalid password for user: {username}")
        return None
    
    # Update last login
    await db.execute(
        update(User)
        .where(User.user_id == user.user_id)
        .values(last_login=datetime.now(timezone.utc))
    )
    await db.commit()
    
    return user.to_dict()


async def create_user_token(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a JWT token for a user"""
    
    token_data = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "role": user_data["role"],
        "district_id": user_data.get("district_id"),
        "police_station_id": user_data.get("police_station_id"),
        "permissions": user_data.get("permissions", []),
    }
    
    token = create_access_token(token_data)
    
    expire_time = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    
    return {
        "auth_token": token,
        "token_expires_at": expire_time.isoformat(),
        "user_id": user_data["user_id"],
        "user_name": user_data["full_name"],
        "user_role": user_data["role"],
        "user_district": user_data.get("district_id"),
        "permissions_list": user_data.get("permissions", []),
        "login_time": datetime.now(timezone.utc).isoformat(),
        "expires_in": settings.JWT_EXPIRY_HOURS * 3600,
    }


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by their ID"""
    import uuid
    
    result = await db.execute(
        select(User).where(User.user_id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    return user.to_dict()


async def create_user(db: AsyncSession, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new user"""
    role = user_data.get("role")
    if role not in ["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]:
        raise ValueError(f"Invalid role '{role}'. Must be one of: SCRB_OFFICER, DISTRICT_OFFICER, INVESTIGATOR")
        
    if not user_data.get("full_name") or not str(user_data.get("full_name")).strip():
        raise ValueError("full_name is required and cannot be empty")
    
    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data["username"])
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Username '{user_data['username']}' already exists")
    
    # Hash password
    password_hash = hash_password(user_data["password"])
    
    # Determine default permissions based on role
    permissions = get_default_permissions(user_data["role"])
    
    resolved_district = None
    if user_data.get("district_id"):
        resolved_district = await resolve_district_id(db, user_data.get("district_id"))

    # Create user
    new_user = User(
        username=user_data["username"],
        password_hash=password_hash,
        full_name=user_data["full_name"],
        role=user_data["role"],
        district_id=resolved_district,
        police_station_id=user_data.get("police_station_id"),
        email=user_data.get("email"),
        phone=user_data.get("phone"),
        permissions=permissions,
        is_active=True,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user.to_dict()


async def get_all_users(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    """Get paginated list of users"""
    from sqlalchemy import func
    total_result = await db.execute(select(func.count(User.user_id)))
    total_count = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    result = await db.execute(select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size))
    users = result.scalars().all()
    return {
        "users": [u.to_dict() for u in users],
        "total_count": total_count,
        "page": page,
        "page_size": page_size
    }


def get_default_permissions(role: str) -> list:
    """Get default permissions based on user role"""
    if role == "SCRB_OFFICER":
        return [
            "view_all_districts",
            "view_all_crimes",
            "view_all_offenders",
            "view_network_analysis",
            "view_predictions",
            "view_anomalies",
            "view_alerts",
            "generate_reports",
            "manage_users",
            "view_settings",
            "modify_settings",
        ]
    elif role == "DISTRICT_OFFICER":
        return [
            "view_own_district",
            "view_own_crimes",
            "view_own_offenders",
            "view_network_analysis",
            "view_predictions",
            "view_anomalies",
            "view_alerts",
            "generate_reports",
        ]
    elif role == "INVESTIGATOR":
        return [
            "view_own_district",
            "view_assigned_crimes",
            "view_offenders",
            "view_alerts",
        ]
    return []
