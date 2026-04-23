from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from playwright.async_api import Browser

from extractor import ocr
from extractor.DrissionPage_Downloader import OUTPUT_DIR
from extractor.Tag_Locating import process_name_tag_location, process_price_tag_location
from extractor.css_selector_generator import process_natural_language_request
from extractor.extraction_executor import execute_extraction


class LogContext(Protocol):
    async def info(self, msg: str) -> None: ...

    async def warning(self, msg: str) -> None: ...

    async def error(self, msg: str) -> None: ...


def _callback_for(async_logger: Callable[[str], Awaitable[None]]) -> Callable[[str], None]:
    def _callback(message: str) -> None:
        asyncio.create_task(async_logger(str(message)))

    return _callback


def _reset_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    path.touch()


def _clear_directory_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for file in directory.iterdir():
        if file.is_file():
            file.unlink()


async def capture_mhtml_screenshots(browser: Browser, ctx: LogContext) -> dict:
    await ctx.info("Running screenshot step on mhtml files")
    public_dir = Path(__file__).parent / "public"
    _clear_directory_files(public_dir)

    results: dict[str, bool] = {}
    mhtml_files = list(OUTPUT_DIR.glob("*.mhtml"))
    if not mhtml_files:
        await ctx.warning("No .mhtml files found in mhtml_output")
        return {"screenshots": results}

    for path in mhtml_files:
        success = False
        page = await browser.new_page()
        try:
            await page.goto(f"file://{path.resolve()}")
            await page.wait_for_load_state("networkidle")
            viewport_size = await page.evaluate(
                """() => ({
                    width: Math.max(document.documentElement.clientWidth, window.innerWidth || 0),
                    height: Math.max(document.documentElement.clientHeight, window.innerHeight || 0)
                })"""
            )
            await page.set_viewport_size(viewport_size)

            screenshot_path = public_dir / path.with_suffix(".png").name
            await page.screenshot(path=str(screenshot_path), full_page=True)
            success = True
            await ctx.info(f"Screenshot saved: {screenshot_path.name}")
        except Exception as exc:
            await ctx.error(f"Screenshot failed for {path.name}: {exc}")
        finally:
            await page.close()
            results[path.name] = success

    return {"screenshots": results}


async def process_product_names(ctx: LogContext) -> dict:
    await ctx.info("Running OCR + name tag location")
    _reset_file(Path("extractor/item_info.json"))
    _reset_file(Path("extractor/BeautifulSoup_Content.json"))

    ocr_success = await ocr.process_ocr_name(ctx)
    if not ocr_success:
        await ctx.error("OCR for product names failed")
        return {"success": False, "step_completed": "ocr"}

    tag_success = await process_name_tag_location(ctx)
    if not tag_success:
        await ctx.error("Tag location for product names failed")
        return {"success": False, "step_completed": "ocr_only"}

    return {"success": True, "step_completed": "both"}


async def process_product_prices(ctx: LogContext) -> dict:
    await ctx.info("Running OCR + price tag location")
    _reset_file(Path("extractor/item_info.json"))
    _reset_file(Path("extractor/BeautifulSoup_Content.json"))

    ocr_success = await ocr.process_ocr_price(ctx)
    if not ocr_success:
        await ctx.error("OCR for prices failed")
        return {"success": False, "step_completed": "ocr"}

    tag_success = await process_price_tag_location(ctx)
    if not tag_success:
        await ctx.error("Tag location for prices failed")
        return {"success": False, "step_completed": "ocr_only"}

    return {"success": True, "step_completed": "both"}


async def build_extraction_schema(extraction_request: str, ctx: LogContext) -> dict:
    await ctx.info("Generating extraction schema from natural language request")
    result = await process_natural_language_request(extraction_request)
    if "error" in result:
        await ctx.error(f"Schema generation failed: {result['error']}")
        return {"success": False, "error": result["error"]}

    return {
        "success": True,
        "selectors_config": result.get("selectors_config", {}),
        "schema_path": str(result.get("schema_path", "")),
    }


def _resolve_schema_path(path_value: str | None) -> str:
    if path_value:
        return path_value
    schemas_dir = Path("extraction_schemas")
    if not schemas_dir.exists():
        return ""
    config_files = list(schemas_dir.glob("*.json"))
    if not config_files:
        return ""
    latest_config = max(config_files, key=lambda item: item.stat().st_mtime)
    return str(latest_config)


async def run_extraction_with_schema(
    browser: Browser,
    selectors_config_path: str | None,
    ctx: LogContext,
) -> dict:
    resolved_path = _resolve_schema_path(selectors_config_path)
    if not resolved_path:
        await ctx.error("No selectors config file found")
        return {"success": False, "error": "No selectors config file found"}

    return await execute_extraction(
        browser=browser,
        selectors_config_path=resolved_path,
        info_callback=_callback_for(ctx.info),
        error_callback=_callback_for(ctx.error),
    )

