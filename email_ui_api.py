"""FastAPI Email UI/API Service - Main Application

This module provides a FastAPI-based web application that serves both a web UI
and REST API for email management with SMTP integration.
"""

import asyncio
import json
import os
import pathlib
from datetime import timedelta
from typing import Optional

import redis
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt

# Load environment variables (don't override existing env vars)
load_dotenv(override=False)

# Application imports
from app.config import get_settings
from app.models import Token, User, Email, EmailPage, LoginResponse
from app.auth import authenticate_user, verify_totp, create_access_token, get_current_user
from app.forms import OAuth2PasswordRequestFormNoExtras
from app.openapi import custom_openapi
from email_db import EmailDB

# Application configuration
settings = get_settings()
bearer_scheme = HTTPBearer()

# Template and static file directories
TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
STATIC_DIR = pathlib.Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def validate_user_config() -> None:
    """Validate user configuration at application startup.
    
    Validates the EMAIL_UI_USERS environment variable format and ensures
    all required user configuration fields are present.
    
    Raises:
        RuntimeError: If user configuration is invalid or missing.
    """
    email_ui_users_str = settings.EMAIL_UI_USERS
    if not email_ui_users_str:
        raise RuntimeError("EMAIL_UI_USERS environment variable is not set or is empty.")

    parsed_users = []
    user_entries = email_ui_users_str.strip().split(';')
    for entry in user_entries:
        if not entry.strip():
            continue
        parts = entry.split(':')
        if len(parts) == 3:
            username, hashed_password, otp_secret = parts
            parsed_users.append({
                "username": username,
                "password_hash": hashed_password,
                "totp_secret": otp_secret
            })
        else:
            print(f"[WARNING] Malformed user entry in EMAIL_UI_USERS (skipping): '{entry}'")

    if not parsed_users:
        raise RuntimeError("No valid users configured in EMAIL_UI_USERS. Expected format: 'user:pass_hash:otp_secret;...'")

    for user_dict in parsed_users:
        if not user_dict.get("username") or not user_dict.get("password_hash") or not user_dict.get("totp_secret"):
            raise RuntimeError(f"User entry missing required fields: {user_dict}")
    
    print(f"[INFO] User configuration validated successfully. {len(parsed_users)} user(s) configured.")


async def lifespan(app: FastAPI):
    """Application lifespan event handler.
    
    Performs startup validation and cleanup tasks.
    """
    validate_user_config()
    yield


def get_db():
    """Database dependency provider.
    
    Creates and yields a database connection with proper cleanup.
    """
    db = EmailDB(db_path="data/emails.db", encryption_key=settings.ENCRYPTION_KEY)
    try:
        yield db
    finally:
        db.close()


def get_current_authenticated_user_api_only(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> User:
    """Authentication dependency for API-only endpoints.
    
    Validates Bearer token authentication for API access only.
    
    Args:
        credentials: HTTP Bearer token credentials.
        
    Returns:
        User: Authenticated user object.
        
    Raises:
        HTTPException: If authentication fails.
    """
    user = get_current_user(
        credentials.credentials, 
        settings.EMAIL_UI_USERS, 
        settings.SECRET_KEY, 
        settings.ALGORITHM
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_authenticated_user(request: Request) -> User:
    """Authentication dependency supporting both cookie and Bearer token.
    
    Attempts to authenticate user using either Bearer token (for API access)
    or HttpOnly cookie (for web UI access).
    
    Args:
        request: FastAPI request object.
        
    Returns:
        User: Authenticated user object.
        
    Raises:
        HTTPException: If authentication fails.
    """
    token = None
    
    # Try Bearer token first (for API access)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
    # Fallback to HttpOnly cookie (for web UI access)
    else:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            token = cookie_token.replace("Bearer ", "") if cookie_token.startswith("Bearer ") else cookie_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_current_user(token, settings.EMAIL_UI_USERS, settings.SECRET_KEY, settings.ALGORITHM)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_valid_username_from_cookie(request: Request) -> Optional[str]:
    """Extract and validate username from cookie token.
    
    Args:
        request: FastAPI request object.
        
    Returns:
        Optional[str]: Username if valid token found, None otherwise.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# FastAPI application initialization
if settings.ENABLE_SWAGGER:
    app = FastAPI(title="Email UI/API Service", lifespan=lifespan)
    app.openapi = lambda: custom_openapi(app)
else:
    app = FastAPI(
        title="Email UI/API Service", 
        lifespan=lifespan,
        docs_url=None,    # Disable /docs
        redoc_url=None,   # Disable /redoc
        openapi_url=None  # Disable /openapi.json
    )

# Mount static files if UI is enabled
if settings.ENABLE_UI:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/token", response_model=Token)
async def login_api(form_data: OAuth2PasswordRequestFormNoExtras = Depends()):
    """API token login endpoint.
    
    Authenticates user credentials and TOTP code, returns JWT access token.
    """
    user = authenticate_user(form_data.username, form_data.password, settings.EMAIL_UI_USERS)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    if not verify_totp(user.otp_secret, form_data.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    
    access_token = create_access_token(
        data={"sub": user.username},
        secret_key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/logout", include_in_schema=False)
async def logout(response: Response):
    """User logout endpoint.
    
    Clears the access token cookie to log out the user.
    """
    response.delete_cookie(
        "access_token", 
        httponly=True, 
        secure=settings.COOKIE_SECURE, 
        samesite="lax", 
        path="/"
    )
    return {"message": "Logged out successfully"}


@app.get("/api/me", response_model=User)
async def read_users_me(
    request: Request,
    current_user: User = Depends(get_current_authenticated_user)
):
    """Get current authenticated user information.
    
    Supports both cookie and Bearer token authentication.
    """
    return current_user


@app.get("/api/me/bearer-only", response_model=User)
async def read_users_me_bearer_only(current_user: User = Depends(get_current_authenticated_user_api_only)):
    """Get current authenticated user information (Bearer token only).
    
    Restricted to API clients using Bearer token authentication.
    """
    return current_user


@app.get("/api/emails", response_model=EmailPage)
async def get_emails(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "arrival_time",
    sort_order: str = "DESC",
    search: str = None,
    advanced: str = None,
    current_user: User = Depends(get_current_authenticated_user),
    db: EmailDB = Depends(get_db)
):
    """Retrieve paginated list of emails.
    
    Supports sorting, searching, and advanced query filtering.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1

    emails_data = db.get_emails_for_recipient(
        recipient_username=None,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search_query=search,
        advanced_query=advanced
    )
    return emails_data


@app.get("/api/emails/{email_id}", response_model=Email)
async def get_email_detail(
    email_id: str,
    request: Request,
    current_user: User = Depends(get_current_authenticated_user),
    db: EmailDB = Depends(get_db)
):
    """Retrieve detailed information for a specific email by ID."""
    email = db.get_email_by_id(email_id, None)
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    
    return Email(**email)


@app.patch("/api/emails/{email_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_email_read_status(
    email_id: str,
    read: bool,
    request: Request,
    current_user: User = Depends(get_current_authenticated_user),
    db: EmailDB = Depends(get_db)
):
    """Update email read status (mark as read or unread)."""
    success = db.mark_email_as_read(email_id, None, read_status=read)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found or update failed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/api/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_api(
    email_id: str,
    request: Request,
    current_user: User = Depends(get_current_authenticated_user),
    db: EmailDB = Depends(get_db)
):
    """Delete a specific email by ID."""
    success = db.delete_email(email_id, None)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found or deletion failed")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/events/{recipient}")
async def email_notifications_sse(
    recipient: str,
    request: Request,
    current_user: User = Depends(get_current_authenticated_user)
):
    """Server-Sent Events endpoint for real-time email notifications.
    
    Provides real-time email notifications via SSE using Redis pub/sub.
    """
    
    async def event_stream():
        redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
        
        pubsub = redis_client.pubsub()
        pubsub_channel = f"{os.environ.get('REDIS_PUBSUB_PREFIX', 'email_notify:')}{recipient}"
        pubsub.subscribe(pubsub_channel)
        
        try:
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE connection established'})}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                
                message = pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        email_data = json.loads(message['data'])
                        
                        event_data = {
                            'type': 'new_email',
                            'email': {
                                'id': email_data['id'],
                                'sender': email_data['sender'],
                                'recipient': email_data['recipient'],
                                'subject': email_data['subject'],
                                'status': email_data['status'],
                                'arrival_time': email_data['arrival_time']
                            }
                        }
                        
                        yield f"data: {json.dumps(event_data)}\n\n"
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Error parsing email notification: {e}")
                        continue
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"SSE connection error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Connection error'})}\n\n"
        finally:
            try:
                pubsub.unsubscribe(pubsub_channel)
                pubsub.close()
                redis_client.close()
            except:
                pass
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


# ============================================================================
# WEB UI ENDPOINTS (conditionally enabled)
# ============================================================================

if settings.ENABLE_UI:
    @app.post("/login", response_model=LoginResponse, include_in_schema=False)
    async def login_ui(
        request: Request,
        response: Response,
        username: str = Form(...),
        password: str = Form(...),
        totp_code: str = Form(...),
    ):
        """UI login endpoint for web interface."""
        user = authenticate_user(username, password, settings.EMAIL_UI_USERS)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )

        if not verify_totp(user.otp_secret, totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code."
            )

        access_token = create_access_token(
            data={"sub": user.username},
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        response.set_cookie(
            key="access_token", 
            value=access_token, 
            httponly=True, 
            secure=settings.COOKIE_SECURE, 
            samesite="lax",
            path="/"
        )
        return LoginResponse(access_token=access_token, username=user.username)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root(request: Request):
        """Root endpoint - redirects to appropriate page based on authentication."""
        username = get_valid_username_from_cookie(request)
        if not username:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/mailbox", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(request: Request):
        """Login page for web interface."""
        username = get_valid_username_from_cookie(request)
        if username:
            return RedirectResponse(url="/mailbox", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse("login.html", {"request": request})

    @app.get("/mailbox", response_class=HTMLResponse, include_in_schema=False)
    async def mailbox_page(request: Request):
        """Main mailbox page for web interface."""
        username = get_valid_username_from_cookie(request)
        if not username:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse("mailbox.html", {"request": request, "username": username})

    @app.get("/email/{email_id}", response_class=HTMLResponse, include_in_schema=False)
    async def email_detail_page(request: Request, email_id: str):
        """Email detail page for web interface."""
        username = get_valid_username_from_cookie(request)
        if not username:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse("email_detail.html", {
            "request": request, 
            "email_id": email_id, 
            "username": username
        })

else:
    # UI is disabled - provide 404 responses for UI routes
    async def ui_disabled():
        """Handler for when UI is disabled."""
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Web UI is disabled. Only API access is available."
        )
    
    app.get("/", include_in_schema=False)(ui_disabled)
    app.get("/login", include_in_schema=False)(ui_disabled)
    app.post("/login", include_in_schema=False)(ui_disabled)
    app.get("/mailbox", include_in_schema=False)(ui_disabled)
    app.get("/email/{email_id}", include_in_schema=False)(ui_disabled)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
