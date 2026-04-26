from __future__ import annotations

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


def _get_mongo_uri() -> str:
    return os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")


def _get_database_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "price_claw")


async def init_mongo(strict: bool = False) -> AsyncIOMotorDatabase | None:
    global _mongo_client, _mongo_db

    if _mongo_db is not None:
        return _mongo_db

    try:
        _mongo_client = AsyncIOMotorClient(_get_mongo_uri())
        _mongo_db = _mongo_client[_get_database_name()]
        await _mongo_db.command("ping")
        await ensure_indexes(_mongo_db)
        return _mongo_db
    except Exception:
        _mongo_db = None
        if _mongo_client is not None:
            _mongo_client.close()
            _mongo_client = None
        if strict:
            raise
        return None


def get_mongo_database() -> AsyncIOMotorDatabase | None:
    return _mongo_db


async def close_mongo() -> None:
    global _mongo_client, _mongo_db

    if _mongo_client is not None:
        _mongo_client.close()
    _mongo_client = None
    _mongo_db = None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["schemas"].create_index([("domain", 1), ("status", 1), ("updated_at", -1)])
    await db["schemas"].create_index([("schema_name", 1), ("status", 1)])
    await db["extractions"].create_index([("task_id", 1), ("created_at", -1)])
    await db["extractions"].create_index([("file_name", 1), ("created_at", -1)])
    await db["tasks"].create_index([("task_id", 1)], unique=True)
    await db["tasks"].create_index([("status", 1), ("updated_at", -1)])
