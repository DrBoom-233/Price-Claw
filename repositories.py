from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_public_id(doc: dict[str, Any]) -> dict[str, Any]:
    converted = dict(doc)
    if "_id" in converted:
        converted["id"] = str(converted.pop("_id"))
    return converted


class SchemaRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["schemas"]

    async def create_schema(
        self,
        schema_name: str,
        domain: str,
        selectors_config: dict[str, Any],
        source: str,
        source_path: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        payload = {
            "schema_name": schema_name,
            "domain": domain,
            "selectors_config": selectors_config,
            "source": source,
            "source_path": source_path,
            "status": "active",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(payload)
        payload["_id"] = result.inserted_id
        return _to_public_id(payload)

    async def list_schemas(self, domain: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"status": "active"}
        if domain:
            query["domain"] = domain

        cursor = self.collection.find(query).sort("updated_at", -1)
        return [_to_public_id(doc) async for doc in cursor]

    async def get_schema_by_id(self, schema_id: str) -> dict[str, Any] | None:
        try:
            obj_id = ObjectId(schema_id)
        except Exception:
            return None

        doc = await self.collection.find_one({"_id": obj_id, "status": "active"})
        return _to_public_id(doc) if doc else None

    async def find_latest_active_by_domain(self, domain: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one(
            {"domain": domain, "status": "active"},
            sort=[("updated_at", -1)],
        )
        return _to_public_id(doc) if doc else None

    async def update_schema(
        self,
        schema_id: str,
        schema_name: str | None = None,
        domain: str | None = None,
        selectors_config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            obj_id = ObjectId(schema_id)
        except Exception:
            return None

        update_fields: dict[str, Any] = {"updated_at": _now()}
        if schema_name is not None:
            update_fields["schema_name"] = schema_name
        if domain is not None:
            update_fields["domain"] = domain
        if selectors_config is not None:
            update_fields["selectors_config"] = selectors_config

        await self.collection.update_one({"_id": obj_id, "status": "active"}, {"$set": update_fields})
        return await self.get_schema_by_id(schema_id)

    async def clone_schema(self, schema_id: str, new_name: str) -> dict[str, Any] | None:
        source = await self.get_schema_by_id(schema_id)
        if source is None:
            return None

        base_version = int(source.get("version", 1))
        now = _now()
        payload = {
            "schema_name": new_name,
            "domain": source.get("domain", "unknown"),
            "selectors_config": source.get("selectors_config", {}),
            "source": "clone",
            "source_path": source.get("source_path"),
            "status": "active",
            "version": base_version + 1,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(payload)
        payload["_id"] = result.inserted_id
        return _to_public_id(payload)

    async def archive_schema(self, schema_id: str) -> bool:
        try:
            obj_id = ObjectId(schema_id)
        except Exception:
            return False

        result = await self.collection.update_one(
            {"_id": obj_id, "status": "active"},
            {"$set": {"status": "archived", "updated_at": _now()}},
        )
        return result.modified_count > 0


class ExtractionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["extractions"]

    async def create_extraction(
        self,
        task_id: str,
        file_name: str,
        schema_id: str | None,
        extraction_request: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "task_id": task_id,
            "file_name": file_name,
            "schema_id": schema_id,
            "extraction_request": extraction_request,
            "result": result,
            "created_at": _now(),
        }
        inserted = await self.collection.insert_one(payload)
        payload["_id"] = inserted.inserted_id
        return _to_public_id(payload)

    async def list_extractions(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        cursor = self.collection.find({}).sort("created_at", -1).limit(safe_limit)
        return [_to_public_id(doc) async for doc in cursor]


class TaskRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["tasks"]

    async def create_task(self, task_id: str, filenames: list[str], mode: str) -> dict[str, Any]:
        now = _now()
        payload = {
            "task_id": task_id,
            "status": "queued",
            "filenames": filenames,
            "mode": mode,
            "created_at": now,
            "updated_at": now,
            "summary": {},
            "error": None,
        }
        await self.collection.insert_one(payload)
        return payload

    async def set_status(
        self,
        task_id: str,
        status: str,
        summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        update: dict[str, Any] = {
            "status": status,
            "updated_at": _now(),
        }
        if summary is not None:
            update["summary"] = summary
        if error is not None:
            update["error"] = error

        await self.collection.update_one({"task_id": task_id}, {"$set": update})
