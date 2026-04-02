"""
Cleaning functions for Russian Federation newspapers.
"""

import re

from .registry import register_cleaner


@register_cleaner
def parse_date_from_jsonld(jsonld_text: str) -> str:
    """
    Extract datePublished from a JSON-LD script element's text content.

    Used for sites where the article date is only available in a
    <script type="application/ld+json"> block (e.g. Lenta.ru, Meduza, Mediazona, TASS).

    Args:
        jsonld_text: Raw text content of the JSON-LD <script> element

    Returns:
        Normalized date string in YYYY-MM-DD format, or empty string
    """
    if not jsonld_text:
        return ""

    from .common import handle_mixed_dates

    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', jsonld_text)
    if m:
        return handle_mixed_dates(m.group(1))

    # Fallback: input may already be a clean date (double-cleaning scenario in scraper)
    return handle_mixed_dates(jsonld_text.strip())
