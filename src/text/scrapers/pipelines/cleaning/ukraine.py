"""Cleaning functions for Ukraine sources."""

import re
from typing import Optional

from .common import handle_mixed_dates
from .registry import register_cleaner
from html import unescape


URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def _clean_ukrainska_pravda_date(
    date_str: str, page_url: Optional[str] = None, base_url: Optional[str] = None
) -> str:
    """Extract a stable article date for Ukrainska Pravda stories."""
    if page_url:
        match = URL_DATE_RE.search(page_url)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"

    if date_str:
        normalized = " ".join(str(date_str).split())
        # Strip author prefix: "Author Name— 31 March, 19:25" → "31 March, 19:25"
        if "—" in normalized:
            normalized = normalized.split("—", 1)[-1].strip()
        cleaned = handle_mixed_dates(normalized)
        if cleaned:
            return cleaned

    return ""


@register_cleaner
def clean_ukrainska_pravda_date(
    date_str: str, page_url: Optional[str] = None, base_url: Optional[str] = None
) -> str:
    """Extract a stable article date for Ukrainska Pravda stories."""
    return _clean_ukrainska_pravda_date(date_str, page_url=page_url, base_url=base_url)


@register_cleaner
def clean_ukrainska_pravda_eng_date(
    date_str: str, page_url: Optional[str] = None, base_url: Optional[str] = None
) -> str:
    """Backward-compatible alias for the English Ukrainska Pravda config."""
    return _clean_ukrainska_pravda_date(date_str, page_url=page_url, base_url=base_url)


@register_cleaner
def clean_spaced_html(text: str) -> str:
    # 1. Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # 2. Unescape HTML entities (just in case)
    text = unescape(text)

    # 3. Remove spaces between single characters (fix "T h e" → "The")
    text = re.sub(r"(?<=\b\w) (?=\w\b)", "", text)

    # 4. Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()
