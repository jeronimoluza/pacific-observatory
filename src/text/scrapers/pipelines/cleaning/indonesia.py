"""
Cleaning functions for Indonesian newspapers.

Handles cleaning for:
- The Jakarta Post
- Antara News
"""

import re
from .registry import register_cleaner


@register_cleaner
def clean_jakarta_post_body(body: str) -> str:
    """
    Clean Jakarta Post article body text.

    Removes:
    - Year-specific article references like "The Jakarta Post's Most-Read Articles of 2025"
    - Newsletter subscription prompts
    - Author bylines

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    # remove "The Jakarta Post's Most-Read Articles of 2025"
    body = re.sub(r"\bThe Jakarta Post's Most-Read Articles of \d{4}\b", "", body)
    # split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\.", body) if p.strip()]

    remove_keys = [
        "By: ",
        "View More Newsletter",
        "Delivered straight to your inbox",
        "By registering, you agree with The Jakarta Post",
    ]
    for key in remove_keys:
        paragraphs = [p for p in paragraphs if not p.startswith(key)]
    # join back together
    body = ". ".join(paragraphs)
    return body


@register_cleaner
def clean_antara_body(body: str) -> str:
    """
    Clean Antara News article body text.

    Removes:
    - Location prefixes like "Jakarta (ANTARA) - "
    - Related news links
    - Translator/Editor credits
    - Copyright notices

    Args:
        body: Raw article body text

    Returns:
        Cleaned article body text
    """
    to_remove = "Jakarta (ANTARA) - "
    remove_keys = ["Related news: ", "Translator: ", "Editor", "Copyright"]
    for key in remove_keys:
        body = body.replace(key, "")
    if body.startswith(to_remove):
        body = body[len(to_remove) :]
    return body
