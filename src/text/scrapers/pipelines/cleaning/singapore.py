"""
Cleaning functions for Singaporean newspapers.

Handles cleaning for:
- The Independent Singapore (TISG)
"""

from .registry import register_cleaner


@register_cleaner
def clean_the_independent_body(body: str) -> str:
    """
    Clean The Independent Singapore article body text.

    Removes:
    - "/TISG" signature
    - "Read also: " sections and everything after

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    body = body.replace("/TISG ", "")
    if "Read also: " in body:
        body = body.split("Read also: ")[0].strip()
    return body
