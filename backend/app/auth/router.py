"""Auth router: register, login, logout, me (ADR-006).

Auth backends
-------------
access_backend  — cookie ``access_token``   httpOnly SameSite=Lax  TTL 1 h
refresh_backend — cookie ``refresh_token``  httpOnly SameSite=Lax  TTL 7 d

Routes registered
-----------------
POST /auth/register
POST /auth/login        (access_backend)
POST /auth/logout       (access_backend)
POST /auth/refresh/login   (refresh_backend)
POST /auth/refresh/logout  (refresh_backend)
GET  /auth/me
PATCH /auth/me
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)

from app.auth.manager import get_user_manager
from app.auth.models import User
from app.auth.schema import UserCreate, UserRead, UserUpdate
from app.config import get_settings

_s = get_settings()

# ---------------------------------------------------------------------------
# Transports (httpOnly, SameSite=Lax — ADR-006)
# ---------------------------------------------------------------------------

_access_transport = CookieTransport(
    cookie_name="access_token",
    cookie_max_age=_s.jwt_access_ttl_s,
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_secure=_s.cookie_secure,  # True in prod (HTTPS), False in dev
)

_refresh_transport = CookieTransport(
    cookie_name="refresh_token",
    cookie_max_age=_s.jwt_refresh_ttl_s,
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_secure=_s.cookie_secure,  # True in prod (HTTPS), False in dev
)

# ---------------------------------------------------------------------------
# JWT strategies
# ---------------------------------------------------------------------------


def _get_access_strategy() -> JWTStrategy:
    return JWTStrategy(secret=_s.jwt_secret, lifetime_seconds=_s.jwt_access_ttl_s)


def _get_refresh_strategy() -> JWTStrategy:
    return JWTStrategy(secret=_s.jwt_secret, lifetime_seconds=_s.jwt_refresh_ttl_s)


# ---------------------------------------------------------------------------
# Authentication backends
# ---------------------------------------------------------------------------

access_backend = AuthenticationBackend(
    name="cookie",
    transport=_access_transport,
    get_strategy=_get_access_strategy,
)

refresh_backend = AuthenticationBackend(
    name="cookie_refresh",
    transport=_refresh_transport,
    get_strategy=_get_refresh_strategy,
)

# ---------------------------------------------------------------------------
# FastAPIUsers instance
# ---------------------------------------------------------------------------

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [access_backend, refresh_backend],
)

# Dependency to inject the current active user in protected routes.
current_active_user = fastapi_users.current_user(active=True)

# ---------------------------------------------------------------------------
# Router assembly
# ---------------------------------------------------------------------------

router = APIRouter()

# POST /auth/login  +  POST /auth/logout
router.include_router(
    fastapi_users.get_auth_router(access_backend),
    prefix="/auth",
    tags=["auth"],
)

# POST /auth/refresh/login  +  POST /auth/refresh/logout
router.include_router(
    fastapi_users.get_auth_router(refresh_backend),
    prefix="/auth/refresh",
    tags=["auth"],
)

# POST /auth/register
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# GET /auth/me  +  PATCH /auth/me  (+  admin /auth/{id} routes)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/auth",
    tags=["auth"],
)
