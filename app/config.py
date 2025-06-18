"""Application configuration module.

Manages environment variables and application settings.
"""

import os
from functools import lru_cache

from cryptography.fernet import Fernet
from dotenv import load_dotenv

from .models import AppSettings

# Load environment variables (don't override existing env vars)
load_dotenv(override=False)


@lru_cache()
def get_settings() -> AppSettings:
    """Get application settings from environment variables.
    
    Uses LRU cache to ensure settings are loaded only once during application lifetime.
    
    Returns:
        AppSettings: Application configuration object.
        
    Raises:
        ValueError: If required sensitive environment variables are missing.
    """
    # Check for required sensitive environment variables
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ValueError(
            "SECRET_KEY environment variable is required. "
            "Generate one with: openssl rand -hex 32"
        )
    
    email_ui_users = os.getenv("EMAIL_UI_USERS")
    if not email_ui_users:
        # Provide a default admin user for development only
        import warnings
        warnings.warn(
            "EMAIL_UI_USERS not set. Using default admin user. "
            "Set EMAIL_UI_USERS for production deployment.",
            UserWarning
        )
        email_ui_users = "admin:$2b$12$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH"
    
    # Generate encryption key if not provided
    encryption_key = os.getenv("EMAIL_ENCRYPTION_KEY")
    if not encryption_key:
        encryption_key = Fernet.generate_key().decode()
        import warnings
        warnings.warn(
            "EMAIL_ENCRYPTION_KEY not set. Generated a random key. "
            "This key will change on restart - set EMAIL_ENCRYPTION_KEY for persistence.",
            UserWarning
        )
    
    return AppSettings(
        SECRET_KEY=secret_key,
        EMAIL_UI_USERS=email_ui_users,
        ENCRYPTION_KEY=encryption_key,
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379"),
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./data/emails.db"),
        COOKIE_SECURE=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        ACCESS_TOKEN_EXPIRE_MINUTES=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        ALGORITHM=os.getenv("ALGORITHM", "HS256"),
        ENABLE_SWAGGER=os.getenv("ENABLE_SWAGGER", "True").lower() == "true",
        ENABLE_UI=os.getenv("ENABLE_UI", "True").lower() == "true",
    )
