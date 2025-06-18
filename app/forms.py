"""Custom form classes for authentication.

Provides form handlers for login with TOTP authentication.
"""

from fastapi import Form


class OAuth2PasswordRequestFormNoExtras:
    """Custom OAuth2 password request form with TOTP support.
    
    Extends the standard OAuth2 password flow to include TOTP code validation.
    """
    
    def __init__(
        self,
        username: str = Form(...),
        password: str = Form(...),
        totp_code: str = Form(...),
    ):
        """Initialize form with username, password, and TOTP code.
        
        Args:
            username: User's username.
            password: User's password.
            totp_code: Time-based one-time password code.
        """
        self.username = username
        self.password = password
        self.totp_code = totp_code
