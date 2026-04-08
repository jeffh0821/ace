"""User model with role-based access."""

import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean
from app.db.database import Base


class UserRole(str, enum.Enum):
    sales = "sales"
    engineer = "engineer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.sales)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
