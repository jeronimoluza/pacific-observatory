"""
API strategy for JSON-based article discovery.

This module implements strategies for discovering articles from JSON API endpoints.
"""

import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional, AsyncGenerator

from bs4 import BeautifulSoup

from .base import ListingStrategy

logger = logging.getLogger(__name__)


class ApiStrategy(ListingStrategy):
    """
    API strategy for JSON-based article discovery.

    This strategy fetches article listings from JSON API endpoints
    instead of scraping HTML pages. Supports both offset-based and
    page-based pagination.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize API strategy.

        Expected config keys:
        - url_template: API URL template(s) with placeholders like {offset}, {size}, {page}
        - pagination_type: "offset" or "page"
        - offset_start: Starting offset (for offset-based, default: 0)
        - offset_step: Offset increment (for offset-based, default: 100)
        - page_start: Starting page number (for page-based, default: 0)
        - page_step: Page increment (for page-based, default: 1)
        - json_paths: Dictionary mapping field names to JSON paths
          (or CSS sub-selectors when view_path is set)
        - view_path: JSON key containing HTML string (optional)
        - view_container: CSS selector for article containers in HTML view (optional)
        - headers: Custom request headers dict (optional)
        - request_method: "GET" or "POST" (optional, default: "GET")
        - form_data: Dictionary of POST form data with optional {offset}/{page} placeholders
        """
        super().__init__(config, max_pages)

        url_template_config = config["url_template"]
        if isinstance(url_template_config, str):
            self.url_templates = [url_template_config]
        else:
            self.url_templates = url_template_config

        self.pagination_type = config.get("pagination_type", "page")
        self.offset_start = config.get("offset_start", 0)
        self.offset_step = config.get("offset_step", 100)
        self.page_start = config.get("page_start", 0)
        self.page_step = config.get("page_step", 1)
        self.json_paths = config.get("json_paths", {})
        self.batch_size = config.get("batch_size", 10)
        self.exclude = config.get("exclude", None)
        self.view_path = config.get("view_path", None)
        self.view_container = config.get("view_container", None)
        self.headers = config.get("headers", None)
        self.request_method = config.get("request_method", "GET")
        self.form_data = config.get("form_data", None)

        # Validate pagination type
        if self.pagination_type not in ["offset", "page"]:
            raise ValueError(
                f"pagination_type must be 'offset' or 'page', got: {self.pagination_type}"
            )

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """
        Get a value from nested dictionaries/lists using dot notation.

        Supports list traversal by aggregating values when a key resolves to a
        list of dictionaries. Numeric keys are treated as list indices.

        Args:
            data: Dictionary to extract from
            path: Dot-separated path (e.g., "pagination.total" or "tags.slug")

        Returns:
            Extracted value(s) or None if the path cannot be resolved
        """
        if not path:
            return data

        keys = path.split(".")
        current_values = [data]

        for key in keys:
            next_values = []

            for value in current_values:
                if isinstance(value, dict):
                    if key in value and value[key] is not None:
                        next_values.append(value[key])
                elif isinstance(value, list):
                    # Numeric access: treat key as index
                    if key.isdigit():
                        idx = int(key)
                        if 0 <= idx < len(value):
                            next_values.append(value[idx])
                        continue

                    # Non-numeric key: apply to each element in the list
                    for item in value:
                        if isinstance(item, dict):
                            if key in item and item[key] is not None:
                                next_values.append(item[key])
                        elif isinstance(item, list):
                            # Preserve nested lists for further traversal
                            next_values.append(item)

            if not next_values:
                return None

            current_values = next_values

        if len(current_values) == 1:
            return current_values[0]

        return current_values

    def _extract_thumbnails_from_json(
        self, json_data: Dict, api_url: str
    ) -> List[Dict[str, Any]]:
        """
        Extract thumbnail data from JSON response.

        Args:
            json_data: Parsed JSON response
            api_url: API URL for logging

        Returns:
            List of thumbnail dictionaries
        """
        thumbnails = []

        # HTML-in-JSON mode: extract HTML from a JSON field and parse with CSS selectors
        if self.view_path:
            html_content = self._get_nested_value(json_data, self.view_path)
            if not html_content or not isinstance(html_content, str):
                logger.warning(f"No HTML content at '{self.view_path}' in {api_url}")
                return thumbnails
            return self._extract_thumbnails_from_html_view(html_content, api_url)

        # Standard JSON mode: traverse structured JSON with json_paths
        collection_path = self.json_paths.get("collection", "")
        if collection_path:
            articles = self._get_nested_value(json_data, collection_path)
        else:
            # Assume the root is the collection
            articles = json_data if isinstance(json_data, list) else []

        if not articles:
            logger.warning(f"No articles found in API response from {api_url}")
            return thumbnails

        # Extract data from each article
        for article in articles:
            try:
                thumbnail_data = {}

                # Extract each configured field
                for field, path in self.json_paths.items():
                    if field in ["collection", "total"]:
                        continue  # Skip metadata fields

                    value = self._get_nested_value(article, path) if path else None
                    thumbnail_data[field] = value

                if thumbnail_data:
                    thumbnails.append(thumbnail_data)

            except Exception as e:
                logger.error(
                    f"Error extracting thumbnail from article in {api_url}: {e}"
                )
                continue

        return thumbnails

    def _filter_excluded_thumbnails(
        self, thumbnails: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove thumbnails that match any configured exclusion condition."""
        if not self.exclude:
            return thumbnails

        filtered: List[Dict[str, Any]] = []

        for thumb in thumbnails:
            keep = True

            for condition in self.exclude:
                if not isinstance(condition, dict):
                    continue

                if all(
                    thumb.get(key) == expected for key, expected in condition.items()
                ):
                    keep = False
                    break

            if keep:
                filtered.append(thumb)

        excluded_count = len(thumbnails) - len(filtered)
        if excluded_count:
            logger.info(
                f"Excluded {excluded_count} API records based on 'exclude' filters"
            )

        return filtered

    def _extract_css_value(self, element, selector: str) -> Optional[str]:
        """Extract a value from a BeautifulSoup element using a CSS selector.

        Supports ::text and ::attr(name) pseudo-elements.
        """
        attr_match = re.match(r"(.+?)::attr\((\w+)\)$", selector)
        text_match = re.match(r"(.+?)::text$", selector)

        if attr_match:
            css, attr_name = attr_match.groups()
            el = element.select_one(css)
            return el.get(attr_name) if el else None
        elif text_match:
            css = text_match.group(1)
            el = element.select_one(css)
            return el.get_text(strip=True) if el else None
        else:
            el = element.select_one(selector)
            return el.get_text(strip=True) if el else None

    def _extract_thumbnails_from_html_view(
        self, html_content: str, api_url: str
    ) -> List[Dict[str, Any]]:
        """Extract thumbnails from an HTML string using CSS selectors.

        Uses view_container to find article containers, then json_paths
        values as CSS sub-selectors within each container.
        """
        thumbnails = []
        soup = BeautifulSoup(html_content, "html.parser")
        containers = soup.select(self.view_container)

        if not containers:
            logger.warning(
                f"No containers matching '{self.view_container}' in {api_url}"
            )
            return thumbnails

        for container in containers:
            thumb_data = {}
            for field, selector in self.json_paths.items():
                if field in ["collection", "total"]:
                    continue
                value = self._extract_css_value(container, selector)
                if value:
                    thumb_data[field] = value

            if thumb_data:
                thumbnails.append(thumb_data)

        return thumbnails

    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Discover and fetch article listings from API endpoints.

        Note: thumbnail_selector is not used for API strategy since we parse JSON.
        """
        for url_template in self.url_templates:
            logger.info(f"Starting API discovery for template: {url_template}")

            if self.pagination_type == "offset":
                # Offset-based pagination
                current_offset = self.offset_start
                total_articles = None
                pages_scraped = 0

                while True:
                    # Check max_pages limit
                    if self.max_pages and pages_scraped >= self.max_pages:
                        logger.info(f"Reached max_pages limit: {self.max_pages}")
                        break

                    # Generate API URL with current offset
                    api_url = url_template.format(
                        offset=current_offset, size=self.offset_step
                    )

                    # Resolve placeholders in form_data
                    resolved_data = None
                    if self.form_data:
                        resolved_data = {
                            k: str(v).format(offset=current_offset, page=current_offset)
                            for k, v in self.form_data.items()
                        }

                    try:
                        # Fetch response
                        import httpx

                        async with httpx.AsyncClient() as http_client:
                            content, status_code = await client.request_url(
                                http_client,
                                api_url,
                                method=self.request_method,
                                data=resolved_data,
                            )

                        if content is None:
                            logger.warning(f"Failed to fetch API URL: {api_url}")
                            break

                        # Raw HTML mode: view_container without view_path
                        if self.view_container and not self.view_path:
                            html_text = (
                                content.decode("utf-8", errors="replace")
                                if isinstance(content, bytes)
                                else content
                            )
                            thumbnails = self._extract_thumbnails_from_html_view(
                                html_text, api_url
                            )
                        else:
                            # Parse JSON
                            json_data = json.loads(content)

                            # Get total count if available (first request only)
                            if total_articles is None:
                                total_path = self.json_paths.get("total")
                                if total_path:
                                    total_articles = self._get_nested_value(
                                        json_data, total_path
                                    )
                                    logger.info(
                                        f"API reports {total_articles} total articles"
                                    )

                            # Extract thumbnails from JSON
                            thumbnails = self._extract_thumbnails_from_json(
                                json_data, api_url
                            )

                        if not thumbnails:
                            logger.info(
                                f"No more articles found at offset {current_offset}"
                            )
                            break

                        thumbnails = self._filter_excluded_thumbnails(thumbnails)
                        logger.info(
                            f"Extracted {len(thumbnails)} articles from offset {current_offset}"
                        )
                        yield thumbnails

                        # Increment offset by the step size
                        current_offset += self.offset_step
                        if total_articles and current_offset >= total_articles:
                            logger.info(
                                f"Reached end of articles (offset {current_offset} >= total {total_articles})"
                            )
                            break

                        pages_scraped += 1
                        await asyncio.sleep(0.5)

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from {api_url}: {e}")
                        break
                    except Exception as e:
                        logger.error(f"Error fetching API URL {api_url}: {e}")
                        break

            else:
                # Page-based pagination
                current_page = self.page_start
                pages_scraped = 0
                consecutive_failures = 0
                MAX_CONSECUTIVE_FAILURES = 3

                while True:
                    # Check max_pages limit
                    if self.max_pages and pages_scraped >= self.max_pages:
                        logger.info(f"Reached max_pages limit: {self.max_pages}")
                        break

                    # Generate API URL with current page
                    api_url = url_template.format(page=current_page)

                    # Resolve placeholders in form_data
                    resolved_data = None
                    if self.form_data:
                        resolved_data = {
                            k: str(v).format(page=current_page, offset=current_page)
                            for k, v in self.form_data.items()
                        }

                    try:
                        # Fetch response
                        import httpx

                        async with httpx.AsyncClient() as http_client:
                            content, status_code = await client.request_url(
                                http_client,
                                api_url,
                                method=self.request_method,
                                data=resolved_data,
                            )

                        if content is None:
                            logger.warning(f"Failed to fetch API URL: {api_url}")
                            break

                        # Raw HTML mode: view_container without view_path
                        if self.view_container and not self.view_path:
                            html_text = (
                                content.decode("utf-8", errors="replace")
                                if isinstance(content, bytes)
                                else content
                            )
                            thumbnails = self._extract_thumbnails_from_html_view(
                                html_text, api_url
                            )
                        else:
                            # Bail early if the host returned HTML (e.g. WAF/captcha)
                            # rather than JSON — saves a JSONDecodeError and gives a
                            # clearer log line.
                            preview = (
                                content[:64].lstrip()
                                if isinstance(content, (bytes, bytearray))
                                else content[:64].lstrip().encode("utf-8", "replace")
                            )
                            if preview.startswith(b"<"):
                                consecutive_failures += 1
                                logger.error(
                                    f"Non-JSON (HTML) response from {api_url} "
                                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}) "
                                    f"— likely WAF/captcha"
                                )
                                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                                    logger.warning(
                                        f"Stopping discovery after {consecutive_failures} "
                                        f"consecutive non-JSON responses"
                                    )
                                    break
                                current_page += self.page_step
                                pages_scraped += 1
                                await asyncio.sleep(0.5)
                                continue

                            # Parse JSON
                            json_data = json.loads(content)

                            # Extract thumbnails from JSON
                            thumbnails = self._extract_thumbnails_from_json(
                                json_data, api_url
                            )

                        if not thumbnails:
                            logger.info(
                                f"No more articles found at page {current_page}"
                            )
                            break

                        thumbnails = self._filter_excluded_thumbnails(thumbnails)
                        logger.info(
                            f"Extracted {len(thumbnails)} articles from page {current_page}"
                        )
                        yield thumbnails

                        consecutive_failures = 0
                        current_page += self.page_step
                        pages_scraped += 1
                        await asyncio.sleep(0.5)

                    except json.JSONDecodeError as e:
                        consecutive_failures += 1
                        logger.error(
                            f"Failed to parse JSON from {api_url}: {e} "
                            f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                        )
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            logger.warning(
                                f"Stopping discovery after {consecutive_failures} "
                                f"consecutive JSON parse failures"
                            )
                            break
                        current_page += self.page_step
                        pages_scraped += 1
                        await asyncio.sleep(0.5)
                        continue
                    except Exception as e:
                        logger.error(f"Error fetching API URL {api_url}: {e}")
                        break
