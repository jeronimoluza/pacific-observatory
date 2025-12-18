"""
Utility functions for the price_scraping project.
"""

import hashlib
import re
from datetime import datetime
from typing import Optional, List, Union
import logging


def extract_price(price_text: str) -> Optional[float]:
    """
    Extract numeric price from text.
    Handles various formats like "$10.99", "FJD 10.99", etc.
    """
    if not price_text:
        return None

    # Remove common currency symbols and text
    cleaned = re.sub(r"[A-Z$£€¥]", "", price_text).strip()

    # Extract first number with decimal point
    match = re.search(r"\d+\.?\d*", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None

    return None


def extract_currency(price_text: str) -> Optional[str]:
    """
    Extract currency code from price text.
    """
    if not price_text:
        return None

    # Common currency patterns
    currencies = {
        "FJD": r"FJD|F\$|\$",
        "USD": r"USD|\$",
        "AUD": r"AUD|A\$",
        "NZD": r"NZD|NZ\$",
        "EUR": r"EUR|€",
        "GBP": r"GBP|£",
    }

    for code, pattern in currencies.items():
        if re.search(pattern, price_text, re.IGNORECASE):
            return code

    return None


def generate_url_hash(url: str) -> str:
    """
    Generate MD5 hash of URL for deduplication.
    """
    return hashlib.md5(url.encode()).hexdigest()


def generate_version_hash(html_content: str) -> str:
    """
    Generate MD5 hash of HTML content for change tracking.
    """
    return hashlib.md5(html_content.encode()).hexdigest()


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse HTTP timestamp to datetime object.
    Handles RFC 2822 format (e.g., "Mon, 01 Jan 2024 12:00:00 GMT").
    """
    if not timestamp_str:
        return None

    try:
        return datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError:
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return None


def normalize_category(category_text: str) -> str:
    """
    Normalize category text for consistency.
    """
    if not category_text:
        return None

    # Remove extra whitespace and convert to title case
    return " > ".join(
        part.strip().title() for part in category_text.split(">") if part.strip()
    )


class SelectorExtractor:
    """
    Handles CSS selector extraction with fallback support.
    Tries multiple selectors in order and returns the first match.
    """

    def __init__(self, response, logger: Optional[logging.Logger] = None):
        """
        Initialize the extractor.

        Args:
            response: Scrapy response object
            logger: Optional logger for debugging selector attempts
        """
        self.response = response
        self.logger = logger or logging.getLogger(__name__)

    def extract(
        self,
        field_name: str,
        selectors: List[str],
        method: str = "get",
        strip: bool = True,
    ) -> Union[str, List[str], None]:
        """
        Extract data using multiple CSS selectors with fallback.

        Args:
            field_name: Name of the field being extracted (for logging)
            selectors: List of CSS selector strings to try in order
            method: 'get' for single value, 'getall' for list
            strip: Whether to strip whitespace from results

        Returns:
            First matching value, list of values, or None if no match found
        """
        if not selectors:
            self.logger.warning(f"{field_name}: no selectors provided")
            return None

        for i, selector in enumerate(selectors, 1):
            try:
                result = getattr(self.response.css(selector), method)()
                if result:
                    self.logger.debug(
                        f"{field_name}: matched selector {i}/{len(selectors)}"
                    )
                    # Handle stripping for single values
                    if method == "get" and strip and isinstance(result, str):
                        return result.strip()
                    # Handle stripping for lists
                    elif method == "getall" and strip and isinstance(result, list):
                        return [
                            item.strip() if isinstance(item, str) else item
                            for item in result
                        ]
                    return result
            except Exception as e:
                self.logger.debug(f"{field_name}: selector {i} failed with error: {e}")
                continue

        self.logger.warning(
            f"{field_name}: no selectors matched (tried {len(selectors)})"
        )
        return None
