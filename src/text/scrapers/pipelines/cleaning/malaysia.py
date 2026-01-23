"""
Cleaning functions for Malaysian newspapers.

Handles cleaning for:
- Kosmo! Online
"""

import re
from .registry import register_cleaner


@register_cleaner
def clean_kosmo_body(body: str) -> str:
    """
    Clean Kosmo! Online article body text.

    Removes:
    - Copyright footer text
    - "– KOSMO! ONLINE" signatures

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    body = body.replace(
        " – KOSMO! ONLINE Hak cipta terpelihara © 2026 Media Mulia Sdn Bhd 201801030285 (1292311-H) Satu lagi produk Media Mulia Sdn.",
        "",
    )
    remove_keys = [
        " – KOSMO! ONLINE",
    ]
    paragraphs = [p.strip() for p in re.split(r"\.", body) if p.strip()]
    for key in remove_keys:
        paragraphs = [p for p in paragraphs if not p.startswith(key)]
    # join back together
    body = ". ".join(paragraphs)
    return body
