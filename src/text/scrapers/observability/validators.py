"""
Field validators for data quality checking.

Provides validators for url, title, date, body fields.
"""

import re
from datetime import datetime
from typing import Optional


def validate_url(url: Optional[str]) -> tuple[bool, str]:
    """
    Validate URL field.

    Args:
        url: URL string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL is empty"

    if not isinstance(url, str):
        return False, f"URL is not a string: {type(url)}"

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return False, f"URL missing http/https scheme: {url}"

    # Check for common issues
    if " " in url:
        return False, f"URL contains spaces: {url}"

    return True, ""


def validate_title(title: Optional[str]) -> tuple[bool, str]:
    """
    Validate title field.

    Args:
        title: Title string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not title:
        return False, "Title is empty"

    if not isinstance(title, str):
        return False, f"Title is not a string: {type(title)}"

    # Title should have reasonable length
    if len(title) < 5:
        return False, f"Title too short ({len(title)} chars): {title}"

    if len(title) > 500:
        return False, f"Title too long ({len(title)} chars)"

    return True, ""


def validate_date(date: Optional[str]) -> tuple[bool, str]:
    """
    Validate date field.

    Args:
        date: Date string to validate (expected format: YYYY-MM-DD)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not date:
        return False, "Date is empty"

    if not isinstance(date, str):
        return False, f"Date is not a string: {type(date)}"

    # Check format: YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return False, f"Date wrong format (expected YYYY-MM-DD): {date}"

    # Validate actual date
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        return False, f"Invalid date: {date} ({e})"

    return True, ""


def validate_body(body: Optional[str]) -> tuple[bool, str]:
    """
    Validate body field.

    Args:
        body: Body text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not body:
        return False, "Body is empty"

    if not isinstance(body, str):
        return False, f"Body is not a string: {type(body)}"

    # Body should have substantial content
    if len(body) < 50:
        return False, f"Body too short ({len(body)} chars) - likely extraction failure"

    return True, ""
