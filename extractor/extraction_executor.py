#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extraction Executor
---------
This module is responsible for executing data extraction operations, extracting data from mhtml files based on the provided selector configuration.
"""

import asyncio
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExtractionExecutor")

# Import Playwright
try:
    from playwright.async_api import Page, Browser
except ImportError:
    logger.error("Please install the Playwright library: pip install playwright")
    raise

class ExtractionExecutor:
    """
    Extraction Executor Class: Responsible for extracting data from MHTML files using configured selectors.
    """

    def __init__(self, browser: Browser, info_callback: Optional[Callable] = None, error_callback: Optional[Callable] = None):
        """
        Initialize the Extraction Executor
        
        Parameters:
            browser: Playwright browser instance
            info_callback: Information callback function for sending notifications
            error_callback: Error callback function for sending error notifications
        """
        self.browser = browser
        self.info_callback = info_callback or (lambda msg: logger.info(msg))
        self.error_callback = error_callback or (lambda msg: logger.error(msg))

    async def load_selector_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load the selector configuration file
        
        Parameters:
            config_path: Path to the configuration file
            
        Returns:
            Parsed configuration dictionary
        """
        path = Path(config_path)
        if not path.exists() or not path.is_file():
            error_msg = f"Configuration file does not exist: {config_path}"
            self.error_callback(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.info_callback("✅ Successfully loaded configuration file")
            
            # Display configuration file information
            self.info_callback(f"📋 Website Type: {config.get('website_type', 'Not Specified')}")
            self.info_callback(f"📝 Description: {config.get('description', 'Not Provided')}")
            
            # Output extraction field information
            fields = config.get("expected_fields", [])
            if fields:
                field_names = [field.get("name", "") for field in fields]
                self.info_callback(f"🔍 Extraction Fields: {', '.join(field_names)}")
                
            # Check for container selector
            if "container_selector" not in config:
                self.error_callback("⚠️ Container selector not specified in the configuration, default container selector will be used")
                config["container_selector"] = ".product-item, .item, .product, li.product, div.product, [class*='product-'], [class*='item-']"
                
                # Update the configuration file
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                self.info_callback(f"✅ Default container selector added: {config['container_selector']}")
            
            return config
            
        except Exception as e:
            error_msg = f"Failed to read configuration file: {str(e)}"
            self.error_callback(f"❌ {error_msg}")
            raise ValueError(error_msg)

    async def find_mhtml_files(
        self,
        directory: str = "mhtml_output",
        include_filenames: Optional[List[str]] = None,
    ) -> List[Path]:
        """
        Find MHTML files
        
        Parameters:
            directory: Directory path
            
        Returns:
            List of MHTML file paths
        """
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            error_msg = f"Directory does not exist: {directory}"
            self.error_callback(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
            
        if include_filenames:
            requested = {name.strip() for name in include_filenames if name and name.strip()}
            mhtml_files = [dir_path / name for name in requested]
            missing_files = [file.name for file in mhtml_files if not file.exists()]
            if missing_files:
                error_msg = f"Requested MHTML files do not exist: {', '.join(sorted(missing_files))}"
                self.error_callback(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)
        else:
            mhtml_files = list(dir_path.glob("*.mhtml"))

        if not mhtml_files:
            error_msg = f"No MHTML files found in the {directory} directory"
            self.error_callback(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
            
        self.info_callback(f"🔍 Found {len(mhtml_files)} MHTML files")
        return mhtml_files

    async def extract_from_file(self, mhtml_file: Path, selectors_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract data from a single MHTML file
        
        Parameters:
            mhtml_file: Path to the MHTML file
            selectors_config: Selector configuration
            
        Returns:
            Dictionary of extraction results
        """
        self.info_callback(f"📄 Processing MHTML file: {mhtml_file.name}")
        
        try:
            # Create a new page
            page = await self.browser.new_page()
            
            try:
                # Navigate to the MHTML file
                file_url = f"file://{mhtml_file.absolute()}"
                self.info_callback(f"🌐 Loading file: {file_url}")
                await page.goto(file_url)
                await page.wait_for_load_state("networkidle")
                
                # Get configuration information
                container_selector = selectors_config.get("container_selector", "")
                fields = selectors_config.get("expected_fields", [])
                
                # Use the container selector to extract all item containers
                self.info_callback(f"🔍 Searching for item containers using selector: {container_selector}")
                item_elements = await page.query_selector_all(container_selector)
                
                if not item_elements:
                    self.error_callback(f"⚠️ No item containers found, extracting directly from the page")
                    
                    # If no containers are found, attempt to extract each field as an independent item
                    product_items = []
                    
                    # Extract each field type separately
                    field_values = {}
                    for field in fields:
                        field_name = field.get("name", "")
                        selector = field.get("selector", "")
                        
                        if not field_name or not selector:
                            continue
                            
                        try:
                            elements = await page.query_selector_all(selector)
                            if elements:
                                texts = []
                                for element in elements:
                                    text = await element.text_content()
                                    if text:
                                        texts.append(text.strip())
                                
                                field_values[field_name] = texts
                                self.info_callback(f"✅ Found {len(texts)} {field_name}")
                            else:
                                field_values[field_name] = []
                        except Exception as e:
                            self.error_callback(f"❌ Failed to extract field {field_name}: {str(e)}")
                            field_values[field_name] = []
                    
                    # Pair results of different fields into product items
                    max_items = max([len(values) for values in field_values.values()]) if field_values else 0
                    
                    for idx in range(max_items):
                        item = {}
                        for field_name, values in field_values.items():
                            item[field_name] = values[idx] if idx < len(values) else ""
                        product_items.append(item)
                        
                    self.info_callback(f"📊 Successfully paired {len(product_items)} product items")
                else:
                    self.info_callback(f"✅ Found {len(item_elements)} item containers")
                    
                    # Process each container
                    product_items = []
                    for idx, element in enumerate(item_elements):
                        item_data = {}
                        
                        # Extract content for each field within the container
                        for field in fields:
                            field_name = field.get("name", "")
                            field_selector = field.get("selector", "")
                            
                            if not field_name or not field_selector:
                                continue
                            
                            try:
                                # Search for elements within the container
                                sub_elem = await element.query_selector(field_selector)
                                if sub_elem:
                                    raw = await sub_elem.text_content()
                                    text = raw.strip() if raw and raw.strip() else None

                                    # 2) If text is empty, try the aria-label attribute
                                    if not text:
                                        raw_attr = await sub_elem.get_attribute("aria-label")
                                        text = raw_attr.strip() if raw_attr and raw_attr.strip() else None
                                    
                                    # 3) Final assignment (set to "" if none)
                                    item_data[field_name] = text or ""
                                else:
                                    item_data[field_name] = ""                                   
                            except Exception as e:
                                self.error_callback(f"❌ Failed to extract field '{field_name}' in container #{idx+1}: {str(e)}")
                                item_data[field_name] = ""
                        
                        # Add to results
                        product_items.append(item_data)
                
                # Display partial extraction results
                if product_items:
                    self.info_callback(f"📊 Successfully extracted {len(product_items)} product items")
                    if len(product_items) > 0:
                        sample = product_items[0]
                        sample_str = ", ".join([f"{k}: {v}" for k, v in sample.items()])
                        self.info_callback(f"📌 Sample: {sample_str}")
                
                # Return results for this file
                return {
                    "file_name": mhtml_file.name,
                    "items_count": len(product_items),
                    "items": product_items
                }
                
            except Exception as e:
                self.error_callback(f"❌ Failed to process MHTML file: {str(e)}")
                return {
                    "file_name": mhtml_file.name,
                    "items_count": 0,
                    "items": [],
                    "error": str(e)
                }
            finally:
                await page.close()
                
        except Exception as e:
            self.error_callback(f"❌ Failed to create page: {str(e)}")
            return {
                "file_name": mhtml_file.name,
                "items_count": 0,
                "items": [],
                "error": str(e)
            }

    async def execute_extraction(
        self,
        selectors_config_path: str,
        output_dir: str = "price_info_output",
        include_filenames: Optional[List[str]] = None,
        concurrency: int = 3,
        write_local_output: bool = False,
    ) -> Dict[str, Any]:
        """
        Main function to execute extraction operations
        
        Parameters:
            selectors_config_path: Path to the selector configuration file
            output_dir: Output directory
            
        Returns:
            Dictionary containing extraction results
        """
        try:
            # Load selector configuration
            selectors_config = await self.load_selector_config(selectors_config_path)
            
            # Find MHTML files
            mhtml_files = await self.find_mhtml_files(include_filenames=include_filenames)
            
            # Prepare for extraction operations
            self.info_callback("🔍 Starting data extraction...")
            
            # Process all files with controlled concurrency to avoid browser resource contention.
            safe_concurrency = max(1, min(concurrency, len(mhtml_files)))
            semaphore = asyncio.Semaphore(safe_concurrency)

            async def _extract_with_limit(mhtml_file: Path) -> Dict[str, Any]:
                async with semaphore:
                    return await self.extract_from_file(mhtml_file, selectors_config)

            gathered = await asyncio.gather(
                *[_extract_with_limit(mhtml_file) for mhtml_file in mhtml_files],
                return_exceptions=True,
            )

            all_files_results = []
            for idx, item in enumerate(gathered):
                if isinstance(item, Exception):
                    failed_file = mhtml_files[idx]
                    error_text = str(item)
                    self.error_callback(f"❌ Failed to process {failed_file.name}: {error_text}")
                    all_files_results.append(
                        {
                            "file_name": failed_file.name,
                            "items_count": 0,
                            "items": [],
                            "error": error_text,
                        }
                    )
                else:
                    all_files_results.append(item)
            
            # Use MHTML file name as the output JSON name
            if len(mhtml_files) == 1:
            # If there is only one MHTML file, use its name directly
                mhtml_name = mhtml_files[0].stem  # Get the file name without extension
                results_filename = f"{mhtml_name}.json"
            else:
            # If there are multiple MHTML files, use the first file name and add an indicator
                mhtml_name = mhtml_files[0].stem
                results_filename = f"{mhtml_name}_and_{len(mhtml_files)-1}_more.json"
            
            results_path = ""
            if write_local_output:
                # Ensure the output directory exists
                output_path = Path(output_dir)
                output_path.mkdir(exist_ok=True)

                # Result file path
                output_path_file = output_path / results_filename
                results_path = str(output_path_file)
            
            # Calculate total number of items
            total_items = sum(file_result.get("items_count", 0) for file_result in all_files_results)
            
            # Build the final result object
            final_results = {
                "files_processed": len(all_files_results),
                "total_items": total_items,
                "results": all_files_results
            }
            
            if write_local_output:
                # Save results
                with open(results_path, 'w', encoding='utf-8') as f:
                    json.dump(final_results, f, indent=2, ensure_ascii=False)

                self.info_callback(f"💾 Extraction results saved to: {results_path}")
            
            # Display overall results
            self.info_callback(f"📊 Successfully processed {len(all_files_results)}/{len(mhtml_files)} MHTML files, extracted {total_items} data items in total")
                
            return {
                "success": True,
                "files_processed": len(all_files_results),
                "total_items": total_items,
                "results_path": results_path,
                "results": all_files_results,
            }
            
        except Exception as e:
            self.error_callback(f"❌ Error during data extraction process: {str(e)}")
            return {"success": False, "error": str(e)}

# Export simplified asynchronous function for server.py to call
async def execute_extraction(
    browser: Browser, 
    selectors_config_path: str,
    info_callback: Optional[Callable] = None,
    error_callback: Optional[Callable] = None,
    include_filenames: Optional[List[str]] = None,
    concurrency: int = 3,
    write_local_output: bool = False,
) -> Dict[str, Any]:
    """
    Convenient function to execute data extraction
    
    Parameters:
        browser: Playwright browser instance
        selectors_config_path: Path to the selector configuration file
        info_callback: Information callback function
        error_callback: Error callback function
        
    Returns:
        Dictionary containing extraction results
    """
    executor = ExtractionExecutor(browser, info_callback, error_callback)
    return await executor.execute_extraction(
        selectors_config_path,
        include_filenames=include_filenames,
        concurrency=concurrency,
        write_local_output=write_local_output,
    )