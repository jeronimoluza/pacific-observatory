"""
Cleaning functions for Palauan newspapers.

Handles cleaning for:
- Island Times
"""

import re
from .registry import register_cleaner


@register_cleaner
def clean_island_times_body(body: str) -> str:
    """
    Clean Island Times article body text.

    Removes:
    - Author bylines that start with "By: "

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    # split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\.\s", body) if p.strip()]

    remove_keys = ["By: "]
    for key in remove_keys:
        paragraphs = [p for p in paragraphs if not p.startswith(key)]
    # join back together
    body = ". ".join(paragraphs)
    return body
