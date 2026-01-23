"""
Cleaning functions for Laotian newspapers.

Handles cleaning for:
- Laotian Times
"""

from .registry import register_cleaner


@register_cleaner
def clean_laotian_times_body(body: str) -> str:
    """
    Clean Laotian Times article body text.

    Removes:
    - Footer text with contact information and copyright

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    body = body.replace(
        " The leading English language news website in Laos. Contact us info@laotiantimes.com © Laotiantimes.com",
        "",
    )
    return body
