"""
User Database Model - PostgreSQL Table: users
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(String(50), nullable=False)  # SCRB_OFFICER / DISTRICT_OFFICER / INVESTIGATOR
    district_id = Column(String(50), nullable=True)
    police_station_id = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(JSON, default=list)

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "district_id": self.district_id,
            "police_station_id": self.police_station_id,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "permissions": self.permissions or [],
        }
