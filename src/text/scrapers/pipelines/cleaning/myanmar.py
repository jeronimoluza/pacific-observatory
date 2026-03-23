"""Cleaning functions for Myanmar news sources."""

import re

from .registry import register_cleaner
from .common import clean_wp_html_body


@register_cleaner
def clean_frontier_myanmar_body(html_content: str) -> str:
    """
    Clean Frontier Myanmar WordPress excerpt HTML.

    Frontier uses Paid Memberships Pro (PMPro) for paywalled posts; the
    `excerpt.rendered` field commonly includes a teaser paragraph followed by an
    "Account Required" block. We keep the teaser and remove subscription prompts.
    """

    if not html_content:
        return ""

    text = clean_wp_html_body(html_content)
    if not text:
        return ""

    # Strong markers observed in PMPro paywall blocks.
    markers = [
        "account required",
        "you must have an account to access this content",
        "create account",
        "already a member?",
        "log in here",
    ]

    lower = text.lower()
    cut_positions = [lower.find(m) for m in markers if lower.find(m) != -1]
    if cut_positions:
        text = text[: min(cut_positions)]

    # Remove any residual marker phrases (defensive) and normalize whitespace.
    for m in markers:
        text = re.sub(re.escape(m), "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text
