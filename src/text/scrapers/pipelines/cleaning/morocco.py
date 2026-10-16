"""
Cleaning functions for Moroccan newspapers.
"""

import json
import re

from .registry import register_cleaner


@register_cleaner
def clean_arc_fusion_body(script_text: str) -> str:
    """
    Article text from an Arc Publishing page (Le360), which renders the body
    client-side: the paragraphs are only in the inline
    ``Fusion.globalContent={...}`` JSON, as ``content_elements`` of type "text".

    Args:
        script_text: Text of the <script> holding Fusion.globalContent

    Returns:
        The text paragraphs joined by spaces, tags stripped; empty if absent
    """
    start = (script_text or "").find("Fusion.globalContent=")
    if start < 0:
        return ""
    try:
        content, _ = json.JSONDecoder().raw_decode(script_text, start + len("Fusion.globalContent="))
    except ValueError:
        return ""
    texts = [
        re.sub(r"<[^>]+>", "", e.get("content", ""))
        for e in content.get("content_elements") or []
        if e.get("type") == "text"
    ]
    return re.sub(r"\s+", " ", " ".join(texts)).strip()
