"""
Cleaning functions for Australian newspapers.

Handles cleaning for:
- ABC (Australian Broadcasting Corporation)
"""

from .registry import register_cleaner


@register_cleaner
def filter_abc_au_articles(record: dict) -> bool:
    """
    Filter out non-article content from ABC AU API results.

    Args:
        record: The record dictionary extracted from the API.

    Returns:
        True if the record is an article, False otherwise.
    """
    # The media type is derived from the contentUri field
    content_uri = record.get("contentUri", "")
    if content_uri:
        media_type = content_uri.split("//")[-1].split("/")[0]
        if media_type == "article":
            return True
    return False
