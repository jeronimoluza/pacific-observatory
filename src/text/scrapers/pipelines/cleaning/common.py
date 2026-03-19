"""
Common cleaning utilities used across all newspapers.

This module contains generic cleaning functions that are not specific to any
particular country or newspaper.
"""

import re
from datetime import datetime
import logging

from .registry import register_cleaner

logger = logging.getLogger(__name__)


@register_cleaner
def handle_mixed_dates(date_str: str | int) -> str:
    """
    Handle mixed date formats and normalize them with robust cleaning.

    This function handles various date formats and common formatting issues
    found in scraped content, including prefixes, suffixes, and extra text.
    Also handles Unix timestamps (as int or str).

    Args:
        date_str: Date string in various formats, or Unix timestamp (int or str)

    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    if not date_str:
        return ""

    # Handle Unix timestamps (int or numeric string)
    if isinstance(date_str, int):
        try:
            return datetime.fromtimestamp(date_str).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""

    # Check if string is a numeric Unix timestamp
    cleaned = str(date_str).strip()
    if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
        try:
            return datetime.fromtimestamp(int(cleaned)).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass  # Fall through to regular date parsing

    # Remove common prefixes and suffixes that appear in scraped dates
    # This handles cases like "- September 24, 2025", "• Sep 24, 2025", "| Date: ..."
    cleaned = re.sub(r"^[-•\*\+\|\s]+", "", cleaned).strip()
    cleaned = re.sub(r"[-•\*\+\|\s]+$", "", cleaned).strip()

    # Remove common date-related prefixes (case insensitive)
    cleaned = re.sub(
        r"^(Published|Posted|Date|On|Updated|Last\s+modified|Modified):\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Remove "By [Author]" patterns that might precede dates
    cleaned = re.sub(r"^By\s+[^,]+,?\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # Remove HTML entities and extra whitespace
    import html

    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return ""

    # Try to parse and normalize to ISO format
    try:
        # Comprehensive date patterns (most specific first)
        patterns = [
            # ISO and standard formats
            "%Y-%m-%d",  # 2025-09-24
            "%Y/%m/%d",  # 2025/09/24
            "%d/%m/%Y",  # 24/09/2025
            "%m/%d/%Y",  # 09/24/2025
            "%d-%m-%Y",  # 24-09-2025
            "%m-%d-%Y",  # 09-24-2025
            # Full month names with various formats
            "%B %d, %Y",  # September 24, 2025
            "%b %d, %Y",  # Sep 24, 2025
            "%d %B %Y",  # 24 September 2025
            "%d %b %Y",  # 24 Sep 2025
            "%B %d %Y",  # September 24 2025 (no comma)
            "%b %d %Y",  # Sep 24 2025 (no comma)
            # With day names
            "%A, %B %d, %Y",  # Monday, September 24, 2025
            "%A %B %d, %Y",  # Monday September 24, 2025
            "%a, %B %d, %Y",  # Mon, September 24, 2025
            "%a %B %d, %Y",  # Mon September 24, 2025
            "%A, %b %d, %Y",  # Monday, Sep 24, 2025
            "%A %b %d, %Y",  # Monday Sep 24, 2025
            # With times
            "%B %d, %Y %H:%M",  # September 24, 2025 14:30
            "%b %d, %Y %H:%M",  # Sep 24, 2025 14:30
            "%B %d, %Y %H:%M:%S",  # September 24, 2025 14:30:45
            "%b %d, %Y %H:%M:%S",  # Sep 24, 2025 14:30:45
            "%Y-%m-%dT%H:%M:%S",  # ISO datetime format
            "%Y-%m-%d %H:%M:%S",  # Standard datetime format
            "%Y-%m-%dT%H:%M:%SZ",  # ISO datetime with Z
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO datetime with microseconds
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO datetime with microseconds
            "%d %b, %Y %I:%M %p",  # 24 Sep, 2025 02:30 PM
            # Alternative formats
            "%d.%m.%Y",  # 24.09.2025
            "%m.%d.%Y",  # 09.24.2025
            "%Y.%m.%d",  # 2025.09.24
            "%d-%b-%Y",  # 24-Sep-2025
            "%d-%B-%Y",  # 24-September-2025
        ]

        for pattern in patterns:
            try:
                parsed_date = datetime.strptime(cleaned, pattern)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Fallback: Try to extract date using regex patterns
        # This handles cases where there's extra text around the date
        date_patterns = [
            # Match "Month DD, YYYY" patterns
            r"(\w+\s+\d{1,2},?\s+\d{4})",
            # Match "DD Month YYYY" patterns
            r"(\d{1,2}\s+\w+\s+\d{4})",
            # Match "YYYY-MM-DD" patterns
            r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
            # Match "MM/DD/YYYY" or "DD/MM/YYYY" patterns
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        ]

        for regex_pattern in date_patterns:
            match = re.search(regex_pattern, cleaned)
            if match:
                date_part = match.group(1).strip()

                # Try to parse the extracted date part
                for strp_pattern in patterns:
                    try:
                        parsed_date = datetime.strptime(date_part, strp_pattern)
                        # logger.info(f"Successfully parsed date using regex fallback: '{date_str}' -> '{parsed_date.strftime('%Y-%m-%d')}'")
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue

        # If still no match, log warning and return cleaned string
        logger.warning(f"Could not parse date format: {date_str}")
        return cleaned

    except Exception as e:
        logger.error(f"Error cleaning date '{date_str}': {e}")
        return cleaned


@register_cleaner
def clean_html_text(text: str) -> str:
    """
    Clean HTML text by removing extra whitespace and HTML artifacts.

    Args:
        text: Raw text that may contain HTML artifacts

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove HTML entities
    import html

    text = html.unescape(text)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


@register_cleaner
def normalize_tags(tags_str: str) -> list:
    """
    Normalize tag strings into a list of clean tags.

    Args:
        tags_str: Comma-separated or other delimited tag string

    Returns:
        List of cleaned tag strings
    """
    if not tags_str:
        return []

    # Split on common delimiters
    delimiters = [",", ";", "|", "\n"]
    tags = [tags_str]

    for delimiter in delimiters:
        new_tags = []
        for tag in tags:
            new_tags.extend(tag.split(delimiter))
        tags = new_tags

    # Clean each tag
    cleaned_tags = []
    for tag in tags:
        cleaned = tag.strip()
        if cleaned and cleaned not in cleaned_tags:
            cleaned_tags.append(cleaned)

    return cleaned_tags


@register_cleaner
def clean_url(url: str, base_url: str = None) -> str:
    """
    Clean and normalize URLs.

    Args:
        url: Raw URL
        base_url: Base URL for making relative URLs absolute

    Returns:
        Cleaned, absolute URL
    """
    if not url:
        return ""

    url = url.strip()

    # Make relative URLs absolute
    if base_url and not url.startswith(("http://", "https://")):
        from urllib.parse import urljoin

        url = urljoin(base_url, url)

    return url


@register_cleaner
def clean_title(title: str) -> str:
    """
    Clean article titles by removing extra whitespace and common artifacts.

    Args:
        title: Raw title text

    Returns:
        Cleaned title
    """
    if not title:
        return ""

    # Remove extra whitespace
    title = re.sub(r"\s+", " ", title)

    # Remove common title artifacts
    title = title.strip(" -|•")

    return title


@register_cleaner
def normalize_date(date_str: str) -> str:
    """
    Normalize any date string to YYYY-MM-DD format.

    This is a general-purpose date normalization function that can be used
    by any newspaper configuration to ensure consistent date formatting.

    Args:
        date_str: Date string in any supported format

    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    return handle_mixed_dates(date_str)


@register_cleaner
def handle_unix_timestamp_ms(timestamp: int | str) -> str:
    """
    Convert Unix timestamp in milliseconds to YYYY-MM-DD format.

    Args:
        timestamp: Unix timestamp in milliseconds (int or str)

    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    if not timestamp:
        return ""

    # If already a formatted date string (YYYY-MM-DD), return as-is (idempotent)
    if (
        isinstance(timestamp, str)
        and len(timestamp) == 10
        and timestamp[4] == "-"
        and timestamp[7] == "-"
    ):
        return timestamp

    try:
        # Convert to int if string
        if isinstance(timestamp, str):
            timestamp = int(timestamp)

        # Convert milliseconds to seconds
        timestamp_seconds = timestamp / 1000

        # Convert to datetime and format
        return datetime.fromtimestamp(timestamp_seconds).strftime("%Y-%m-%d")
    except (ValueError, OSError, TypeError) as e:
        logger.error(f"Error converting Unix timestamp {timestamp}: {e}")
        return ""


@register_cleaner
def handle_unix_timestamp_ms_or_iso(value: int | str) -> str:
    """
    Convert Unix timestamp in milliseconds (or seconds) OR ISO datetime strings to YYYY-MM-DD.

    Accepts:
    - Unix timestamps in ms (int or numeric string)
    - Unix timestamps in seconds (int or numeric string)
    - ISO datetime strings with timezone (e.g. 2026-03-18T08:00:00+08:00)

    Args:
        value: Timestamp or ISO datetime string

    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    if not value:
        return ""

    if isinstance(value, str):
        cleaned = value.strip()

        # Numeric timestamp (string)
        if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
            try:
                numeric = int(cleaned)
                # Treat 13+ digit values as milliseconds
                if abs(numeric) >= 10**11:
                    numeric = numeric / 1000
                return datetime.fromtimestamp(numeric).strftime("%Y-%m-%d")
            except (ValueError, OSError, TypeError) as e:
                logger.error(f"Error converting Unix timestamp {value}: {e}")
                return ""

        # ISO datetime with timezone or 'Z'
        if "T" in cleaned:
            try:
                normalized = cleaned.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Fallback to mixed date parsing
        return handle_mixed_dates(cleaned)

    # Numeric timestamp (int)
    if isinstance(value, (int, float)):
        try:
            numeric = int(value)
            if abs(numeric) >= 10**11:
                numeric = numeric / 1000
            return datetime.fromtimestamp(numeric).strftime("%Y-%m-%d")
        except (ValueError, OSError, TypeError) as e:
            logger.error(f"Error converting Unix timestamp {value}: {e}")
            return ""

    return handle_mixed_dates(str(value))


@register_cleaner
def join_body_list(body_text_list: list) -> str:
    """
    Join body text from a list of strings.

    Args:
        body_text_list: List of strings to join

    Returns:
        Joined string
    """
    return " ".join([s.strip() for s in body_text_list])


@register_cleaner
def clean_wp_html_body(html_content: str) -> str:
    """
    Clean WordPress API HTML body content by stripping tags and normalizing whitespace.

    Args:
        html_content: Raw HTML string from WordPress content.rendered

    Returns:
        Plain text with HTML tags removed
    """
    if not html_content:
        return ""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text(separator=" ")

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()
