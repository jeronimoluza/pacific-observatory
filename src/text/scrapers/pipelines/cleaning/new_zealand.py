"""
Cleaning functions for New Zealand newspapers.

Handles cleaning for:
- New Zealand Herald
"""

from .registry import register_cleaner


@register_cleaner
def clean_nz_herald_body(body: str) -> str:
    """
    Clean NZ Herald article body text.

    Removes:
    - Newsletter signup prompts

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    body = body.replace(
        "Sign up to The Daily H , a free newsletter curated by our editors and delivered straight to your inbox every weekday.",
        "",
    )
    return body
