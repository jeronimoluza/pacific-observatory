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

    # Pages often contain multiple JSON-LD blocks (e.g. Yoast WebPage schema
    # with sentinel "-0001-11-30" plus the real NewsArticle schema). Find all
    # datePublished values and pick the first plausible one.
    matches = re.findall(r'"datePublished"\s*:\s*"([^"]+)"', jsonld_text)
    for m in matches:
        # Skip Yoast/WordPress sentinels for missing CMS dates
        if m.startswith(("-", "0000-", "0001-")):
            continue
        # Skip implausible historical years (parser bugs / placeholder data)
        year_m = re.match(r"^(\d{4})", m)
        if year_m and int(year_m.group(1)) < 1990:
            continue
        return handle_mixed_dates(m)

    # All matches were sentinels — fall back to the first one for visibility
    if matches:
        return handle_mixed_dates(matches[0])

    # Fallback: input may already be a clean date (double-cleaning scenario in scraper)
    return handle_mixed_dates(jsonld_text.strip())
