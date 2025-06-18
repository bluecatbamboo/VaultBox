"""Authentication module for Email UI/API Service.

Provides user authentication, TOTP verification, and JWT token management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

import pyotp
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Security and authentication setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


class UserInDB(BaseModel):
    """User database model with authentication details."""
    username: str
    hashed_password: str
    otp_secret: str
    is_active: bool = True


def get_users_from_env(email_ui_users_str: str) -> Dict[str, UserInDB]:
    """Parse EMAIL_UI_USERS environment variable into user database.
    
    Args:
        email_ui_users_str: Semicolon-separated user entries in format 'user:hash:secret'
        
    Returns:
        Dict[str, UserInDB]: Dictionary mapping usernames to user objects.
    """
    users_db: Dict[str, UserInDB] = {}
    if not email_ui_users_str:
        return users_db
    
    for entry in email_ui_users_str.strip().split(';'):
        if not entry.strip():
            continue
        parts = entry.split(':')
        if len(parts) == 3:
            username, hashed_password, otp_secret = [p.strip() for p in parts]
            users_db[username] = UserInDB(
                username=username,
                hashed_password=hashed_password,
                otp_secret=otp_secret
            )
    return users_db

def get_user(username: str, email_ui_users_str: str) -> Optional[UserInDB]:
    """Retrieve user from configured users by username.
    
    Args:
        username: Username to look up.
        email_ui_users_str: Environment variable string containing user configurations.
        
    Returns:
        Optional[UserInDB]: User object if found, None otherwise.
    """
    users_db = get_users_from_env(email_ui_users_str)
    return users_db.get(username)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against hashed password.
    
    Args:
        plain_password: Plaintext password to verify.
        hashed_password: Hashed password to compare against.
        
    Returns:
        bool: True if password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for password.
    
    Args:
        password: Plaintext password to hash.
        
    Returns:
        str: Hashed password.
    """
    return pwd_context.hash(password)


def verify_totp(otp_secret: str, code: str) -> bool:
    """Verify TOTP (Time-based One-Time Password) code.
    
    Args:
        otp_secret: Base32-encoded secret key for TOTP generation.
        code: 6-digit TOTP code to verify.
        
    Returns:
        bool: True if code is valid, False otherwise.
    """
    totp = pyotp.TOTP(otp_secret)
    return totp.verify(code)


def authenticate_user(username: str, password: str, email_ui_users_str: str) -> Optional[UserInDB]:
    """Authenticate user with username and password.
    
    Args:
        username: Username for authentication.
        password: Plaintext password for authentication.
        email_ui_users_str: Environment variable string containing user configurations.
        
    Returns:
        Optional[UserInDB]: User object if authentication successful, None otherwise.
    """
    user = get_user(username, email_ui_users_str)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, secret_key: str, algorithm: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with expiration.
    
    Args:
        data: Payload data to encode in token.
        secret_key: Secret key for token signing.
        algorithm: JWT algorithm to use.
        expires_delta: Token expiration time delta (default: 15 minutes).
        
    Returns:
        str: Encoded JWT access token.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def get_current_user(token: str, email_ui_users_str: str, secret_key: str, algorithm: str) -> Optional[UserInDB]:
    """Extract and validate user from JWT token.
    
    Args:
        token: JWT access token.
        email_ui_users_str: Environment variable string containing user configurations.
        secret_key: Secret key for token verification.
        algorithm: JWT algorithm used.
        
    Returns:
        Optional[UserInDB]: User object if token is valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None
    
    return get_user(username, email_ui_users_str)
