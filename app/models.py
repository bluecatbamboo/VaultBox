"""Pydantic models for Email UI/API Service.

Defines data structures for API requests, responses, and application configuration.
"""

from typing import Optional, List
from pydantic import BaseModel


class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload data model."""
    username: Optional[str] = None


class User(BaseModel):
    """User model for API responses."""
    username: str
    totp_secret: Optional[str] = None


class Email(BaseModel):
    """Email data model."""
    id: str
    sender: str
    recipient: str
    subject: str
    body: Optional[str] = None
    body_snippet: Optional[str] = None
    is_read: bool
    arrival_time: str
    tags: List[str]
    size_bytes: int


class EmailPage(BaseModel):
    """Paginated email response model."""
    items: List[Email]
    total_items: int
    total_pages: int
    current_page: int
    page_size: int


class LoginResponse(BaseModel):
    """Login response model for UI authentication."""
    access_token: str
    token_type: str = "bearer"
    username: str


class AppSettings(BaseModel):
    """Application configuration settings."""
    PROJECT_NAME: str = "Secure Email UI/API"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_UI_USERS: str
    REDIS_URL: str = "redis://localhost"
    DATABASE_URL: str = "sqlite:///./data/emails.db"
    ENCRYPTION_KEY: str
    COOKIE_SECURE: bool = False
    LOG_LEVEL: str = "INFO"
    ENABLE_SWAGGER: bool = True
    ENABLE_UI: bool = True
