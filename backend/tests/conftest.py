import re

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401

_test_db_initialized = False


async def ensure_test_database() -> None:
    global _test_db_initialized
    if _test_db_initialized:
        return

    test_url = settings.resolved_test_database_url
    app_url = settings.database_url
    if test_url == app_url:
        raise RuntimeError("TEST_DATABASE_URL tidak boleh sama dengan DATABASE_URL aplikasi.")

    _, _, test_db_name = test_url.rpartition("/")
    if not re.fullmatch(r"[A-Za-z0-9_]+", test_db_name):
        raise ValueError(f"Nama database tes tidak valid: {test_db_name}")

    admin_engine = create_async_engine(app_url, isolation_level="AUTOCOMMIT", future=True)
    async with admin_engine.connect() as conn:
        exists = (
            await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": test_db_name},
            )
        ).scalar_one_or_none()
        if exists is None:
            await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    await admin_engine.dispose()

    test_engine = create_async_engine(test_url, future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await test_engine.dispose()

    _test_db_initialized = True


@pytest.fixture(autouse=True)
async def _setup_isolated_test_db() -> None:
    await ensure_test_database()

