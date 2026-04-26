from __future__ import annotations

import json
import shutil
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Iterable

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from playwright.async_api import Browser, async_playwright

from app_settings import (
    apply_runtime_settings,
    get_runtime_settings,
    get_settings_public_view,
    save_runtime_settings,
)
from db import close_mongo, init_mongo
from domain_utils import domain_from_filename, extract_domain_from_mhtml
from pipeline_service import (
    build_extraction_schema,
    capture_mhtml_screenshots,
    process_product_names,
    process_product_prices,
    run_extraction_with_schema,
)
from repositories import ExtractionRepository, SchemaRepository, TaskRepository


MHTML_DIR = Path("mhtml_output")
PRICE_INFO_DIR = Path("price_info_output")
PUBLIC_DIR = Path("public")
TEMP_SCHEMA_DIR = Path(".tmp_schemas")


def _consume_playwright_driver_errors(playwright: Any) -> None:
    transport = getattr(
        getattr(getattr(playwright, "_impl_obj", None), "_connection", None),
        "_transport",
        None,
    )
    on_error_future = getattr(transport, "on_error_future", None)
    if not on_error_future:
        return

    def _mark_exception_retrieved(future: Any) -> None:
        if future.cancelled():
            return
        with suppress(Exception):
            future.exception()

    on_error_future.add_done_callback(_mark_exception_retrieved)


class SettingsPayload(BaseModel):
    apiKey: str
    model: str | None = None
    reasoningModel: str | None = None


class ModelsPayload(BaseModel):
    apiKey: str | None = None


class SchemaUpdatePayload(BaseModel):
    schemaName: str | None = None
    domain: str | None = None
    selectorsConfig: dict[str, Any] | None = None


class SchemaClonePayload(BaseModel):
    newName: str


class WsContext:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def _send(self, level: str, msg: str) -> None:
        await self.websocket.send_json(
            {"type": "log", "level": level, "message": str(msg)}
        )

    async def info(self, msg: str) -> None:
        await self._send("info", msg)

    async def warning(self, msg: str) -> None:
        await self._send("warning", msg)

    async def error(self, msg: str) -> None:
        await self._send("error", msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for directory in (MHTML_DIR, PRICE_INFO_DIR, PUBLIC_DIR, TEMP_SCHEMA_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    settings = get_runtime_settings()
    if settings:
        apply_runtime_settings(settings)

    playwright = await async_playwright().start()
    _consume_playwright_driver_errors(playwright)
    browser = await playwright.chromium.launch(headless=True)
    app.state.playwright = playwright
    app.state.browser = browser

    mongo_db = await init_mongo(strict=False)
    app.state.mongo_db = mongo_db
    app.state.schema_repo = SchemaRepository(mongo_db) if mongo_db is not None else None
    app.state.extraction_repo = (
        ExtractionRepository(mongo_db) if mongo_db is not None else None
    )
    app.state.task_repo = TaskRepository(mongo_db) if mongo_db is not None else None

    try:
        yield
    finally:
        # During Ctrl+C or parent-process termination, Playwright may already be
        # disconnected. Shutdown must remain best-effort and never crash app exit.
        with suppress(Exception):
            if browser.is_connected():
                await browser.close()
        with suppress(Exception):
            await playwright.stop()
        with suppress(Exception):
            await close_mongo()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_supported_model(model_id: str) -> bool:
    normalized = model_id.lower()
    blocked_prefixes = (
        "whisper",
        "tts",
        "dall",
        "omni-moderation",
        "gpt-image",
        "text-embedding",
        "embedding",
    )
    if normalized.startswith(blocked_prefixes):
        return False

    allowed_prefixes = ("gpt", "o", "chatgpt")
    return normalized.startswith(allowed_prefixes)


def _extract_model_ids(models: Iterable[object]) -> list[str]:
    model_ids: list[str] = []
    for model in models:
        model_id = str(getattr(model, "id", "")).strip()
        if model_id and _is_supported_model(model_id):
            model_ids.append(model_id)
    # Keep stable, de-duplicated ordering for predictable dropdown display.
    return sorted(dict.fromkeys(model_ids))


def _get_available_models(api_key: str) -> list[str]:
    client = OpenAI(api_key=api_key)
    models = client.models.list()
    return _extract_model_ids(models)


def _schema_repo(app: FastAPI) -> SchemaRepository | None:
    return getattr(app.state, "schema_repo", None)


def _task_repo(app: FastAPI) -> TaskRepository | None:
    return getattr(app.state, "task_repo", None)


def _extraction_repo(app: FastAPI) -> ExtractionRepository | None:
    return getattr(app.state, "extraction_repo", None)


def _schema_public_view(schema_doc: dict[str, Any]) -> dict[str, Any]:
    selectors = schema_doc.get("selectors_config", {})
    expected_fields = selectors.get("expected_fields", [])
    return {
        "id": schema_doc.get("id"),
        "schemaName": schema_doc.get("schema_name", ""),
        "domain": schema_doc.get("domain", ""),
        "version": schema_doc.get("version", 1),
        "source": schema_doc.get("source", "unknown"),
        "createdAt": schema_doc.get("created_at"),
        "updatedAt": schema_doc.get("updated_at"),
        "sourcePath": schema_doc.get("source_path"),
        "selectorsConfig": selectors,
        "fieldCount": len(expected_fields) if isinstance(expected_fields, list) else 0,
    }


def _resolve_domain_for_file(path: Path) -> str:
    parsed_domain = extract_domain_from_mhtml(path)
    if parsed_domain:
        return parsed_domain
    return domain_from_filename(path.name)


def _safe_schema_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    cleaned = cleaned.strip("._")
    return cleaned or "schema"


def _materialize_schema_config(schema_name: str, selectors_config: dict[str, Any]) -> str:
    TEMP_SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{_safe_schema_filename(schema_name)}_{uuid.uuid4().hex}.json"
    path = TEMP_SCHEMA_DIR / file_name
    path.write_text(json.dumps(selectors_config, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


@app.get("/")
def read_root():
    return {
        "service": "Price Claw FastAPI backend",
        "status": "ok",
        "health": "/api/health",
    }


@app.get("/api/health")
def get_health():
    return {"ok": True}


@app.head("/api/health")
def head_health():
    return Response(status_code=200)


@app.get("/api/settings")
def get_settings():
    return get_settings_public_view()


@app.post("/api/models")
def get_models(payload: ModelsPayload):
    runtime = get_runtime_settings()
    api_key = (payload.apiKey or "").strip() or (runtime.api_key if runtime else "")
    if not api_key:
        raise HTTPException(status_code=400, detail="apiKey is required")

    try:
        model_ids = _get_available_models(api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch models: {exc}")

    return {"models": model_ids}


@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    runtime = get_runtime_settings()
    api_key = payload.apiKey.strip() or (runtime.api_key if runtime else "")
    if not api_key:
        raise HTTPException(status_code=400, detail="apiKey is required")

    selected_model = (payload.model or "").strip()
    if selected_model:
        try:
            model_ids = _get_available_models(api_key)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to fetch models: {exc}")

        if selected_model not in model_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Selected model '{selected_model}' is not available for this API key",
            )

    save_runtime_settings(
        api_key=api_key,
        model=payload.model,
        reasoning_model=payload.reasoningModel,
    )
    view = get_settings_public_view()
    view["message"] = "Settings saved"
    return view


@app.get("/api/schemas")
async def list_schemas(domain: str | None = None):
    schema_repo = _schema_repo(app)
    if schema_repo is None:
        raise HTTPException(status_code=503, detail="MongoDB is not available")

    schemas = await schema_repo.list_schemas(domain=domain)
    return {"schemas": [_schema_public_view(doc) for doc in schemas]}


@app.get("/api/schemas/{schema_id}")
async def get_schema(schema_id: str):
    schema_repo = _schema_repo(app)
    if schema_repo is None:
        raise HTTPException(status_code=503, detail="MongoDB is not available")

    schema_doc = await schema_repo.get_schema_by_id(schema_id)
    if schema_doc is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    return _schema_public_view(schema_doc)


@app.put("/api/schemas/{schema_id}")
async def update_schema(schema_id: str, payload: SchemaUpdatePayload):
    schema_repo = _schema_repo(app)
    if schema_repo is None:
        raise HTTPException(status_code=503, detail="MongoDB is not available")

    updated = await schema_repo.update_schema(
        schema_id=schema_id,
        schema_name=payload.schemaName,
        domain=payload.domain,
        selectors_config=payload.selectorsConfig,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"schema": _schema_public_view(updated)}


@app.post("/api/schemas/{schema_id}/clone")
async def clone_schema(schema_id: str, payload: SchemaClonePayload):
    schema_repo = _schema_repo(app)
    if schema_repo is None:
        raise HTTPException(status_code=503, detail="MongoDB is not available")

    new_name = payload.newName.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="newName is required")

    cloned = await schema_repo.clone_schema(schema_id=schema_id, new_name=new_name)
    if cloned is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"schema": _schema_public_view(cloned)}


@app.delete("/api/schemas/{schema_id}")
async def archive_schema(schema_id: str):
    schema_repo = _schema_repo(app)
    if schema_repo is None:
        raise HTTPException(status_code=503, detail="MongoDB is not available")

    archived = await schema_repo.archive_schema(schema_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"success": True}


@app.post("/api/upload")
async def upload_file(file: list[UploadFile] = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="At least one .mhtml file is required")

    uploaded_filenames: list[str] = []
    for upload in file:
        if not upload.filename or not upload.filename.endswith(".mhtml"):
            raise HTTPException(status_code=400, detail="Only .mhtml files are allowed")

        file_path = MHTML_DIR / upload.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        uploaded_filenames.append(upload.filename)

    return {
        "filename": uploaded_filenames[0],
        "filenames": uploaded_filenames,
        "message": f"Upload successful: {len(uploaded_filenames)} file(s)",
    }


async def run_pipeline(
    websocket: WebSocket,
    extraction_request: str,
    browser: Browser,
    filenames: list[str] | None = None,
    default_schema_id: str | None = None,
    task_mode: str = "uniform",
    file_plans: list[dict[str, Any]] | None = None,
    use_llm: bool = False,
) -> None:
    settings = get_runtime_settings()
    if not settings:
        await websocket.send_json(
            {
                "type": "fatal",
                "message": "OpenAI API key is not configured. Please save it in Settings first.",
            }
        )
        return

    apply_runtime_settings(settings)
    ctx = WsContext(websocket)
    schema_repo = _schema_repo(websocket.app)
    task_repo = _task_repo(websocket.app)
    extraction_repo = _extraction_repo(websocket.app)

    requested_names = [name for name in (filenames or []) if name]
    if not requested_names:
        requested_names = [path.name for path in sorted(MHTML_DIR.glob("*.mhtml"))]

    existing_names = [name for name in requested_names if (MHTML_DIR / name).exists()]
    if not existing_names:
        await websocket.send_json(
            {
                "type": "fatal",
                "message": "No uploaded MHTML file found for this task",
            }
        )
        return

    task_id = uuid.uuid4().hex
    if task_repo is not None:
        await task_repo.create_task(task_id=task_id, filenames=existing_names, mode=task_mode)

    await websocket.send_json({"type": "log", "message": "Extraction pipeline started"})
    await websocket.send_json({"type": "task", "taskId": task_id, "status": "queued"})

    try:
        if task_repo is not None:
            await task_repo.set_status(task_id=task_id, status="running")

        await websocket.send_json(
            {"type": "progress", "step": "Taking screenshots (screenshot_step)"}
        )
        screenshot_result = await capture_mhtml_screenshots(browser, ctx)
        await websocket.send_json(
            {
                "type": "step_done",
                "step": "screenshot_step",
                "data": screenshot_result,
            }
        )

        await websocket.send_json(
            {
                "type": "progress",
                "step": "Processing product names (name_processing_step)",
            }
        )
        name_result = await process_product_names(ctx)
        await websocket.send_json(
            {
                "type": "step_done",
                "step": "name_processing_step",
                "data": name_result,
            }
        )

        if not name_result.get("success", False):
            await websocket.send_json(
                {
                    "type": "progress",
                    "step": "Fallback: processing product prices (price_processing_step)",
                }
            )
            price_result = await process_product_prices(ctx)
            await websocket.send_json(
                {
                    "type": "step_done",
                    "step": "price_processing_step",
                    "data": price_result,
                }
            )

        baseline_schema_path = ""
        baseline_selectors: dict[str, Any] = {}

        async def ensure_baseline_schema() -> tuple[str, dict[str, Any]]:
            nonlocal baseline_schema_path, baseline_selectors

            if baseline_schema_path:
                return baseline_schema_path, baseline_selectors

            await websocket.send_json(
                {
                    "type": "progress",
                    "step": "Generating extraction schema (schema_generation_step)",
                }
            )
            schema_result = await build_extraction_schema(extraction_request, ctx)
            await websocket.send_json(
                {
                    "type": "step_done",
                    "step": "schema_generation_step",
                    "data": schema_result,
                }
            )
            if not schema_result.get("success", False):
                raise RuntimeError("Failed to generate extraction schema")

            baseline_schema_path = str(schema_result.get("schema_path", ""))
            baseline_selectors = schema_result.get("selectors_config", {})
            return baseline_schema_path, baseline_selectors

        llm_cache: dict[str, tuple[str | None, str]] = {}
        resolved_groups: dict[str, dict[str, Any]] = {}
        plan_items: list[dict[str, Any]] = []

        if task_mode == "per_file" and file_plans:
            for raw in file_plans:
                filename = str(raw.get("filename", "")).strip()
                if not filename or filename not in existing_names:
                    continue
                plan_items.append(
                    {
                        "filename": filename,
                        "schema_id": str(
                            raw.get("schema_id") or raw.get("schemaId") or ""
                        ).strip()
                        or None,
                        "use_llm": bool(raw.get("use_llm", raw.get("useLlm", False))),
                    }
                )

        if not plan_items:
            for filename in existing_names:
                plan_items.append(
                    {
                        "filename": filename,
                        "schema_id": default_schema_id,
                        "use_llm": use_llm,
                    }
                )

        for plan in plan_items:
            filename = plan["filename"]
            schema_id = plan.get("schema_id")
            prefer_llm = bool(plan.get("use_llm", False))
            resolved_schema_id = schema_id
            resolved_schema_path = ""

            if schema_id and schema_repo is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Schema selection requires MongoDB for file {filename}",
                    }
                )
                continue

            if schema_id and schema_repo is not None:
                schema_doc = await schema_repo.get_schema_by_id(schema_id)
                if schema_doc is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Schema id not found for file {filename}: {schema_id}",
                        }
                    )
                    continue
                selectors_config = schema_doc.get("selectors_config", {})
                resolved_schema_path = _materialize_schema_config(
                    schema_name=schema_doc.get("schema_name", "schema"),
                    selectors_config=selectors_config,
                )
            else:
                target_file_path = MHTML_DIR / filename
                domain = _resolve_domain_for_file(target_file_path)

                if not prefer_llm and schema_repo is not None:
                    cached = await schema_repo.find_latest_active_by_domain(domain)
                    if cached is not None:
                        resolved_schema_id = cached.get("id")
                        resolved_schema_path = _materialize_schema_config(
                            schema_name=cached.get("schema_name", domain),
                            selectors_config=cached.get("selectors_config", {}),
                        )

                if not resolved_schema_path:
                    if domain in llm_cache:
                        resolved_schema_id, resolved_schema_path = llm_cache[domain]
                    else:
                        generated_path, generated_selectors = await ensure_baseline_schema()

                        if prefer_llm and filename != existing_names[0]:
                            generated = await build_extraction_schema(extraction_request, ctx)
                            if not generated.get("success", False):
                                await websocket.send_json(
                                    {
                                        "type": "error",
                                        "message": f"Failed to generate schema for {filename}",
                                    }
                                )
                                continue
                            generated_path = str(generated.get("schema_path", ""))
                            generated_selectors = generated.get("selectors_config", {})

                        if schema_repo is not None and generated_selectors:
                            created = await schema_repo.create_schema(
                                schema_name=domain,
                                domain=domain,
                                selectors_config=generated_selectors,
                                source="llm",
                                source_path=generated_path,
                            )
                            resolved_schema_id = created.get("id")

                        resolved_schema_path = generated_path
                        llm_cache[domain] = (resolved_schema_id, resolved_schema_path)

            if not resolved_schema_path:
                continue

            group = resolved_groups.setdefault(
                resolved_schema_path,
                {
                    "schema_id": resolved_schema_id,
                    "filenames": [],
                },
            )
            group["filenames"].append(filename)

        if not resolved_groups:
            await websocket.send_json(
                {"type": "fatal", "message": "No valid extraction plan generated"}
            )
            if task_repo is not None:
                await task_repo.set_status(task_id=task_id, status="failed", error="No valid extraction plan generated")
            return

        execution_results: list[dict[str, Any]] = []
        for schema_path, group in resolved_groups.items():
            await websocket.send_json(
                {
                    "type": "progress",
                    "step": "Executing extraction (execute_extraction_step)",
                    "schemaId": group.get("schema_id"),
                    "filenames": group.get("filenames", []),
                }
            )
            extraction_result = await run_extraction_with_schema(
                browser=browser,
                selectors_config_path=schema_path,
                ctx=ctx,
                mhtml_filenames=group.get("filenames", []),
                concurrency=3,
                write_local_output=False,
            )
            execution_results.append(
                {
                    "schemaId": group.get("schema_id"),
                    "filenames": group.get("filenames", []),
                    "result": extraction_result,
                }
            )

            if extraction_repo is not None and extraction_result.get("success", False):
                for file_result in extraction_result.get("results", []):
                    await extraction_repo.create_extraction(
                        task_id=task_id,
                        file_name=file_result.get("file_name", "unknown"),
                        schema_id=group.get("schema_id"),
                        extraction_request=extraction_request,
                        result=file_result,
                    )

        total_items = sum(
            chunk.get("result", {}).get("total_items", 0) for chunk in execution_results
        )
        total_files = sum(
            chunk.get("result", {}).get("files_processed", 0) for chunk in execution_results
        )
        final_result = {
            "taskId": task_id,
            "groups": execution_results,
            "filesProcessed": total_files,
            "totalItems": total_items,
        }

        if task_repo is not None:
            await task_repo.set_status(
                task_id=task_id,
                status="success",
                summary={"filesProcessed": total_files, "totalItems": total_items},
            )

        await websocket.send_json(
            {
                "type": "step_done",
                "step": "execute_extraction_step",
                "data": final_result,
            }
        )
        await websocket.send_json({"type": "result", "data": final_result})
        await websocket.send_json({"type": "complete", "taskId": task_id})
    except Exception as exc:
        if task_repo is not None:
            await task_repo.set_status(task_id=task_id, status="failed", error=str(exc))
        await websocket.send_json({"type": "fatal", "message": str(exc)})


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        message_text = await websocket.receive_text()
        message = json.loads(message_text)
        if message.get("action") != "start":
            await websocket.send_json({"type": "error", "message": "Unknown action"})
            return

        extraction_request = (
            message.get("extraction_request", "").strip()
            or "I want to extract all product names and prices"
        )
        filenames = message.get("filenames")
        if not isinstance(filenames, list):
            filenames = []

        single_filename = str(message.get("filename", "")).strip()
        if single_filename and single_filename not in filenames:
            filenames.append(single_filename)

        schema_id = str(message.get("schema_id") or message.get("schemaId") or "").strip() or None
        task_mode = str(message.get("task_mode") or message.get("taskMode") or "uniform").strip() or "uniform"
        use_llm = bool(message.get("use_llm", message.get("useLlm", False)))
        raw_file_plans = message.get("file_plans") or message.get("filePlans")
        file_plans = raw_file_plans if isinstance(raw_file_plans, list) else []

        browser: Browser = websocket.app.state.browser
        await run_pipeline(
            websocket=websocket,
            extraction_request=extraction_request,
            browser=browser,
            filenames=filenames,
            default_schema_id=schema_id,
            task_mode=task_mode,
            file_plans=file_plans,
            use_llm=use_llm,
        )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "fatal", "message": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
