from __future__ import annotations

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import Browser, async_playwright

from app_settings import (
    apply_runtime_settings,
    get_runtime_settings,
    get_settings_public_view,
    save_runtime_settings,
)
from pipeline_service import (
    build_extraction_schema,
    capture_mhtml_screenshots,
    process_product_names,
    process_product_prices,
    run_extraction_with_schema,
)


MHTML_DIR = Path("mhtml_output")
PRICE_INFO_DIR = Path("price_info_output")
PUBLIC_DIR = Path("public")


class SettingsPayload(BaseModel):
    apiKey: str
    model: str | None = None
    reasoningModel: str | None = None


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
    for directory in (MHTML_DIR, PRICE_INFO_DIR, PUBLIC_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    settings = get_runtime_settings()
    if settings:
        apply_runtime_settings(settings)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    app.state.playwright = playwright
    app.state.browser = browser

    try:
        yield
    finally:
        await browser.close()
        await playwright.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/settings")
def get_settings():
    return get_settings_public_view()


@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    api_key = payload.apiKey.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="apiKey is required")

    save_runtime_settings(
        api_key=api_key,
        model=payload.model,
        reasoning_model=payload.reasoningModel,
    )
    view = get_settings_public_view()
    view["message"] = "Settings saved"
    return view


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".mhtml"):
        raise HTTPException(status_code=400, detail="Only .mhtml files are allowed")

    for old_file in MHTML_DIR.glob("*.mhtml"):
        old_file.unlink()

    file_path = MHTML_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename, "message": "Upload successful"}


async def run_pipeline(
    websocket: WebSocket,
    extraction_request: str,
    browser: Browser,
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
    await websocket.send_json({"type": "log", "message": "Extraction pipeline started"})

    try:
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
            await websocket.send_json(
                {"type": "error", "message": "Failed to generate extraction schema"}
            )
            return

        await websocket.send_json(
            {
                "type": "progress",
                "step": "Executing extraction (execute_extraction_step)",
            }
        )
        extraction_result = await run_extraction_with_schema(
            browser=browser,
            selectors_config_path=schema_result.get("schema_path", ""),
            ctx=ctx,
        )
        await websocket.send_json(
            {
                "type": "step_done",
                "step": "execute_extraction_step",
                "data": extraction_result,
            }
        )
        await websocket.send_json({"type": "result", "data": extraction_result})
        await websocket.send_json({"type": "complete"})
    except Exception as exc:
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
        browser: Browser = websocket.app.state.browser
        await run_pipeline(websocket, extraction_request, browser)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "fatal", "message": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
