"""FastAPI Users UserManager — lifecycle hooks and token secrets (ADR-006)."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from app.auth.db import get_user_db
from app.auth.models import User
from app.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = _settings.jwt_secret
    verification_token_secret = _settings.jwt_secret

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        logger.info("User %s registered.", user.id)

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response=None,
    ) -> None:
        logger.debug("User %s logged in.", user.id)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
