"""Security utilities: rate limiting, login lockout, input sanitization, JWT auth."""

import time
import re
import html
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.models import Agent, User

# ── Rate Limiting (in-memory, production use Redis) ──
_rate_limit_store: dict = {}  # ip -> [(timestamp, count)]

async def rate_limit(request: Request, limit: int = None, window: int = None):
    """Simple sliding-window rate limiter."""
    limit = limit or settings.RATE_LIMIT_REQUESTS
    window = window or settings.RATE_LIMIT_WINDOW
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries
    if client_ip in _rate_limit_store:
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store[client_ip] if now - ts < window
        ]
    else:
        _rate_limit_store[client_ip] = []

    if len(_rate_limit_store[client_ip]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )

    _rate_limit_store[client_ip].append(now)


# ── Login Lockout ──
_login_attempts: dict = {}  # username -> {"count": int, "locked_until": float}

def check_login_lockout(username: str) -> Optional[float]:
    """Return remaining lockout seconds if locked, else None."""
    record = _login_attempts.get(username)
    if not record:
        return None
    locked_until = record.get("locked_until", 0)
    if locked_until and time.time() < locked_until:
        return locked_until - time.time()
    # Reset if lockout expired
    if locked_until and time.time() >= locked_until:
        _login_attempts[username] = {"count": 0, "locked_until": 0}
    return None

def record_login_failure(username: str):
    """Record a failed login attempt."""
    if username not in _login_attempts:
        _login_attempts[username] = {"count": 0, "locked_until": 0}
    _login_attempts[username]["count"] += 1
    if _login_attempts[username]["count"] >= settings.MAX_LOGIN_ATTEMPTS:
        _login_attempts[username]["locked_until"] = time.time() + settings.LOGIN_LOCKOUT_MINUTES * 60

def record_login_success(username: str):
    """Clear failed attempts on successful login."""
    _login_attempts.pop(username, None)


# ── Input Validation ──
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{3,50}$")

def validate_username(username: str) -> bool:
    return bool(_USERNAME_PATTERN.match(username))

def validate_password(password: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
    # Require at least one letter and one number
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Password must contain at least one letter and one number"
    return True, ""

def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize user input: strip, escape HTML, limit length."""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    text = html.escape(text)
    if len(text) > max_length:
        text = text[:max_length]
    return text

def sanitize_command_arg(arg: str) -> str:
    """Escape shell command arguments to prevent injection."""
    # Remove dangerous characters
    arg = re.sub(r'[;&|`$(){}[\]\\\n\r<>]', '', arg)
    return arg.strip()


# ── JWT Auth Dependency ──
security_bearer = HTTPBearer(auto_error=False)

async def get_current_user_token(credentials: HTTPAuthorizationCredentials = None):
    """Extract and return token from Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> str:
    """解码 JWT 并返回 user_id。无效 token 抛出 401。"""
    token = await get_current_user_token(credentials)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no sub")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, str]:
    """双认证：JWT (user) 或 API Key (agent)。返回 (actor_id, actor_type)。"""
    token = await get_current_user_token(credentials)

    # 1. 尝试 JWT 解码（用户）
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id:
            return (user_id, "user")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        pass

    # 2. 尝试 Agent API Key (abk_xxx)
    if token.startswith("abk_"):
        result = await db.execute(
            select(Agent).where(Agent.api_key == token, Agent.is_active == True)
        )
        agent = result.scalar_one_or_none()
        if agent:
            return (agent.id, "agent")

    raise HTTPException(status_code=401, detail="Invalid authentication token")


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> str:
    """要求管理员权限。返回 user_id，非管理员抛出 403。"""
    uid = await get_current_user_id(credentials)
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return uid


async def verify_agent_owner(db: AsyncSession, agent_id: str, uid: str) -> bool:
    """验证 Agent 归属当前用户。"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == uid)
    )
    return result.scalar_one_or_none() is not None


# ── JWT Refresh Token ──
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_refresh_token(user_id: str) -> str:
    """生成有效期 7 天的 refresh token。"""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    refresh_secret = settings.SECRET_KEY + "_refresh"
    return jwt.encode(payload, refresh_secret, algorithm="HS256")


def verify_refresh_token(token: str) -> Optional[str]:
    """验证 refresh token 并返回 user_id。无效或过期返回 None。"""
    try:
        refresh_secret = settings.SECRET_KEY + "_refresh"
        payload = jwt.decode(token, refresh_secret, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        return user_id
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
