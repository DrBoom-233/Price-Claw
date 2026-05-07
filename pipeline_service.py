from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Protocol

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
    def _mark_exception_retrieved(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        try:
            task.exception()
        except Exception:
            pass

    def _callback(message: str) -> None:
        task = asyncio.create_task(async_logger(str(message)))
        task.add_done_callback(_mark_exception_retrieved)

    return _callback


def _reset_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    if path.suffix.lower() == ".json":
        path.write_text("[]", encoding="utf-8")
    else:
        path.touch()


def _clear_directory_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for file in directory.iterdir():
        if file.is_file():
            file.unlink()


def _resolve_mhtml_files(mhtml_filenames: Iterable[str] | None = None) -> list[Path]:
    if mhtml_filenames:
        return [OUTPUT_DIR / name for name in mhtml_filenames if name]
    return list(OUTPUT_DIR.glob("*.mhtml"))


def screenshot_path_for_mhtml(mhtml_filename: str) -> Path:
    return Path(__file__).parent / "public" / Path(mhtml_filename).with_suffix(".png").name


async def capture_mhtml_screenshots(
    browser: Browser,
    ctx: LogContext,
    mhtml_filenames: list[str] | None = None,
    clear_public_dir: bool = True,
) -> dict:
    await ctx.info("Running screenshot step on mhtml files")
    public_dir = Path(__file__).parent / "public"
    if clear_public_dir:
        _clear_directory_files(public_dir)
    else:
        public_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, bool] = {}
    screenshot_paths: dict[str, str] = {}
    mhtml_files = _resolve_mhtml_files(mhtml_filenames)
    if not mhtml_files:
        await ctx.warning("No .mhtml files found in mhtml_output")
        return {"screenshots": results, "screenshot_paths": screenshot_paths}

    for path in mhtml_files:
        success = False
        if not path.exists():
            await ctx.error(f"Screenshot skipped; MHTML file not found: {path.name}")
            results[path.name] = False
            continue

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
            screenshot_paths[path.name] = str(screenshot_path)
            await ctx.info(f"Screenshot saved: {screenshot_path.name}")
        except Exception as exc:
            await ctx.error(f"Screenshot failed for {path.name}: {exc}")
        finally:
            await page.close()
            results[path.name] = success

    return {"screenshots": results, "screenshot_paths": screenshot_paths}


async def process_product_names(
    ctx: LogContext,
    mhtml_path: Path | None = None,
    image_paths: list[Path] | None = None,
) -> dict:
    await ctx.info("Running OCR + name tag location")
    _reset_file(Path("extractor/item_info.json"))
    _reset_file(Path("extractor/BeautifulSoup_Content.json"))

    ocr_success = await ocr.process_ocr_name(ctx, image_paths=image_paths)
    if not ocr_success:
        await ctx.error("OCR for product names failed")
        return {"success": False, "step_completed": "ocr"}

    tag_success = await process_name_tag_location(
        ctx,
        str(mhtml_path) if mhtml_path else None,
    )
    if not tag_success:
        await ctx.error("Tag location for product names failed")
        return {"success": False, "step_completed": "ocr_only"}

    return {"success": True, "step_completed": "both"}


async def process_product_prices(
    ctx: LogContext,
    mhtml_path: Path | None = None,
    image_paths: list[Path] | None = None,
) -> dict:
    await ctx.info("Running OCR + price tag location")
    _reset_file(Path("extractor/item_info.json"))
    _reset_file(Path("extractor/BeautifulSoup_Content.json"))

    ocr_success = await ocr.process_ocr_price(ctx, image_paths=image_paths)
    if not ocr_success:
        await ctx.error("OCR for prices failed")
        return {"success": False, "step_completed": "ocr"}

    tag_success = await process_price_tag_location(
        ctx,
        str(mhtml_path) if mhtml_path else None,
    )
    if not tag_success:
        await ctx.error("Tag location for prices failed")
        return {"success": False, "step_completed": "ocr_only"}

    return {"success": True, "step_completed": "both"}


async def build_extraction_schema(
    extraction_request: str,
    ctx: LogContext,
    mhtml_path: Path | None = None,
) -> dict:
    await ctx.info("Generating extraction schema from natural language request")
    result = await process_natural_language_request(
        extraction_request,
        schema_base_filename=mhtml_path.stem if mhtml_path else None,
    )
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
    mhtml_filenames: list[str] | None = None,
    concurrency: int = 3,
    write_local_output: bool = False,
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
        include_filenames=mhtml_filenames,
        concurrency=concurrency,
        write_local_output=write_local_output,
    )
