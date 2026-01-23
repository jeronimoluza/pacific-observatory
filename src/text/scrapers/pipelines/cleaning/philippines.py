"""
Cleaning functions for Philippine newspapers.

Handles cleaning for:
- ANN (ABS-CBN News)
- PhilStar
- Philippine Daily Inquirer
"""

import re
from .registry import register_cleaner


@register_cleaner
def clean_ann_body(body: str) -> str:
    """
    Clean ANN (ABS-CBN News) article body text.

    Removes:
    - Location/date prefixes after " – "
    - "READ: " article reference links

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    if " – " in body:
        body = body.split(" – ")[1]
    remove_keys = [
        "READ: ",
    ]
    paragraphs = [p.strip() for p in re.split(r"\.", body) if p.strip()]
    for key in remove_keys:
        paragraphs = [p for p in paragraphs if not p.startswith(key)]
    # join back together
    body = ". ".join(paragraphs)
    return body


@register_cleaner
def clean_philstar_body(body: str) -> str:
    """
    Clean PhilStar article body text.

    Removes:
    - Location prefixes after " – "
    - Extra double spaces

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    if " – " in body:
        body = body.split(" – ")[1]
    return body.replace("  ", " ")


@register_cleaner
def clean_inquirer_body(body: str) -> str:
    """
    Clean Philippine Daily Inquirer article body text.

    Removes:
    - Newsletter subscription prompts
    - "READ: " article reference links

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    body = body.replace(
        " Subscribe to our daily newsletter By providing an email address. I agree to the Terms of Use and acknowledge that I have read the Privacy Policy",
        "",
    )
    # split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\.", body) if p.strip()]

    remove_keys = [
        "READ: ",
    ]
    for key in remove_keys:
        paragraphs = [p for p in paragraphs if not p.startswith(key)]
    # join back together
    body = ". ".join(paragraphs)
    return body
