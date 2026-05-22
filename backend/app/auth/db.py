"""Async SQLAlchemy engine and session factory for FastAPI Users.

FastAPI Users requires an async session. We keep a separate async engine
alongside the sync engine used by the rest of the app (chat, retrieval).
Both point to the same Postgres database.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.config import Settings, get_settings


@lru_cache(maxsize=1)
def _get_async_engine(database_url: str):
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _get_async_session_maker(database_url: str):
    engine = _get_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    maker = _get_async_session_maker(settings.database_url)
    async with maker() as session:
        yield session


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
):
    yield SQLAlchemyUserDatabase(session, User)
