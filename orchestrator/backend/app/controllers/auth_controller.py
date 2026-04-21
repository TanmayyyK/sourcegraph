"""
Authentication Controller.

Handles passwordless login (OTP) and JWT issuance.
"""
import random
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Literal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_token_payload
from app.core.database import engine
from app.core.logger import get_logger
from app.models.db_models import User
from app.services.email_service import send_otp_email

logger = get_logger("sourcegraph.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
_last_otp_request_by_email: dict[str, float] = {}
_otp_verify_attempts_by_email: dict[str, int] = {}

# ─── Database Dependency ──────────────────────────────────────────────────────
async def get_db():
    """Yields a database session for the request."""
    async with AsyncSession(engine) as session:
        yield session

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────
class OTPRequest(BaseModel):
    email: EmailStr
    mode: Literal["LOGIN", "SIGNUP"] = "LOGIN"
    role: Annotated[str, StringConstraints(pattern=r"^(PRODUCER|AUDITOR)$")] = "AUDITOR"
    name: str | None = None

class OTPVerify(BaseModel):
    email: EmailStr
    code: Annotated[str, StringConstraints(pattern=r"^\d{6}$")]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class SessionResponse(BaseModel):
    sub: EmailStr
    name: str
    role: str


class GoogleAuthRequest(BaseModel):
    credential: str
    mode: Literal["LOGIN", "SIGNUP"] = "LOGIN"
    role: Annotated[str, StringConstraints(pattern=r"^(PRODUCER|AUDITOR)$")] = "AUDITOR"


def _issue_access_token(email: str, name: str, role: str) -> TokenResponse:
    to_encode = {"sub": email, "name": name, "role": role}
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return TokenResponse(access_token=encoded_jwt, role=role, name=name)

# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/request-otp")
async def request_otp(payload: OTPRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Generates a 6-digit code and saves it to the user's record."""
    email_key = payload.email.lower()
    now_monotonic = time.monotonic()
    last_request_ts = _last_otp_request_by_email.get(email_key)
    if last_request_ts is not None:
        elapsed = now_monotonic - last_request_ts
        remaining = settings.otp_request_cooldown_seconds - elapsed
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {int(remaining) + 1}s before requesting a new OTP.",
            )

    # 1. Find or create the user
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()
    
    code = f"{random.randint(0, 999999):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)

    if payload.mode == "LOGIN" and not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found for this email. Please create an account first.",
        )

    if payload.mode == "SIGNUP" and user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email. Please log in instead.",
        )

    if not user:
        # Create new user during signup flow.
        if not payload.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name is required to create a new account.",
            )
        user = User(
            email=payload.email,
            name=payload.name,
            role=payload.role.upper(),
            login_code=code,
            login_code_expires=expires
        )
        db.add(user)
    else:
        # Existing user login: rotate OTP and keep account identity intact.
        if payload.mode == "SIGNUP" and payload.name:
            user.name = payload.name
        user.role = payload.role.upper()
        user.login_code = code
        user.login_code_expires = expires
        
    # 2. Send OTP over SMTP, then commit the code.
    try:
        await send_otp_email(
            to_email=payload.email,
            name=user.name,
            code=code,
        )
        await db.commit()
        _last_otp_request_by_email[email_key] = now_monotonic
        _otp_verify_attempts_by_email[email_key] = 0
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to send OTP email to %s: %s", payload.email, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deliver OTP email. Please try again.",
        ) from exc

    return {"message": "OTP generated successfully. Please check your email inbox."}


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(payload: OTPVerify, db: AsyncSession = Depends(get_db)) -> Any:
    """Validates the 6-digit code and returns a JWT."""
    email_key = payload.email.lower()
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalars().first()
    
    # 1. Validation checks
    if not user or not user.login_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or code")

    attempts = _otp_verify_attempts_by_email.get(email_key, 0)
    if attempts >= settings.otp_max_verify_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many invalid OTP attempts. Please request a new OTP.",
        )

    if user.login_code != payload.code:
        _otp_verify_attempts_by_email[email_key] = attempts + 1
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    if user.login_code_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code has expired")

    # Snapshot fields before commit to avoid async lazy-load after expiration.
    user_email = user.email
    user_name = user.name
    user_role = user.role

    # 2. Success! Wipe the code so it can't be used twice (Replay Attack prevention)
    user.login_code = None
    user.login_code_expires = None
    await db.commit()
    _otp_verify_attempts_by_email.pop(email_key, None)
    
    logger.info(f"✅ User authenticated: {user_email} as {user_role}")
    return _issue_access_token(email=user_email, name=user_name, role=user_role)


@router.post("/google", response_model=TokenResponse)
async def google_auth(payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticates user via Google ID token, then issues local JWT."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication backend is not installed. Install `google-auth`.",
        ) from exc

    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on the server.",
        )

    try:
        google_info = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_oauth_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google authentication token.",
        ) from exc

    email = google_info.get("email")
    name = google_info.get("name")
    email_verified = google_info.get("email_verified")
    if not email or not name or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account must provide a verified email.",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if payload.mode == "LOGIN" and not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found for this email. Please create an account first.",
        )

    if payload.mode == "SIGNUP" and user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email. Please log in instead.",
        )

    if not user:
        user = User(
            email=email,
            name=name,
            role=payload.role.upper(),
        )
        db.add(user)
    user_name = user.name
    user_role = user.role
    await db.commit()

    logger.info("✅ Google authenticated user: %s as %s", email, user_role)
    return _issue_access_token(email=email, name=user_name, role=user_role)


@router.get("/me", response_model=SessionResponse)
async def get_me(payload: dict[str, Any] = Depends(get_token_payload)) -> SessionResponse:
    """Returns the authenticated session payload."""
    sub = payload.get("sub")
    name = payload.get("name")
    role = payload.get("role")
    if not sub or not name or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token payload.",
        )
    return SessionResponse(sub=sub, name=name, role=role)