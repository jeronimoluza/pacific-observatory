"""Shared client for the doc.as.gov Wix FAQ widget, used by both the Basic
Food Index (`doc_bfi.py`) and Consumer Price Index (`doc_cpi.py`) fetchers --
doc.as.gov/stats renders both as tabs of the same Wix FAQ widget
(`_api/faq-server/v2/...`), one category per tab, one "question entry" per
year, with the actual monthly/quarterly release links embedded in each
entry's rich-text (`draftjs`) field.

The widget's API needs a bearer token, obtained from the unauthenticated,
per-visitor-session `_api/v1/access-tokens` endpoint -- not a secret, just
what any anonymous browser gets on page load. See `doc_bfi.py`'s module
docstring for the full verified request sequence.

Not a fetcher itself -- no `fetch_*` function, not referenced by any YAML
manifest.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_ACCESS_TOKENS_URL = "https://www.doc.as.gov/_api/v1/access-tokens"
_CATEGORIES_URL = "https://www.doc.as.gov/_api/faq-server/v2/categories"
_QUERY_URL = "https://www.doc.as.gov/_api/faq-server/v2/question-entries/query"
_FAQ_APP_DEF_ID = "14c92d28-031e-7910-c9a8-a670011e062d"

_GDRIVE_ID_RE = re.compile(r"/file/d/([^/]+)/")


def gdrive_direct(url: str) -> str:
    """Rewrite a Google Drive "share" link to a direct-download URL."""
    m = _GDRIVE_ID_RE.search(url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def get_faq_token(session, source_key: str) -> str | None:
    try:
        resp = session.get(_ACCESS_TOKENS_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["apps"][_FAQ_APP_DEF_ID]["accessToken"]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] could not obtain FAQ widget access token: %s", source_key, exc
        )
        return None


def get_category_id(
    session, token: str, title: str, fallback_id: str, source_key: str
) -> str:
    try:
        resp = session.get(
            _CATEGORIES_URL, headers={"Authorization": token}, timeout=30
        )
        resp.raise_for_status()
        for cat in resp.json().get("categories", []):
            if cat.get("title", "").strip() == title:
                return cat["id"]
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "[%s] category title lookup failed (%s), using last-known id",
            source_key,
            exc,
        )
    return fallback_id


def query_year_entries(
    session, token: str, category_id: str, source_key: str
) -> list[dict]:
    payload = {
        "query": {
            "cursorPaging": {"limit": 50},
            "filter": {"categoryId": category_id},
            "sort": [{"fieldName": "sortOrder", "order": "ASC"}],
        },
        "contentFormat": "DRAFTJS",
    }
    try:
        resp = session.post(
            _QUERY_URL,
            json=payload,
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("questionEntries", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] question-entries query failed: %s", source_key, exc)
        return []


def _parse_nodes_draftjs(dj: dict) -> list[tuple[str, str]]:
    """Wix Ricos {"nodes": [...]} rich-text format (current-year entries)."""
    out: list[tuple[str, str]] = []

    def walk(nodes):
        for node in nodes:
            if node.get("type") == "PARAGRAPH":
                for child in node.get("nodes", []):
                    if child.get("type") != "TEXT":
                        continue
                    text_data = child.get("textData", {})
                    text = text_data.get("text", "")
                    url = None
                    for dec in text_data.get("decorations", []):
                        if dec.get("type") == "LINK":
                            url = dec.get("linkData", {}).get("link", {}).get("url")
                    if url:
                        out.append((text, url))
            elif "nodes" in node:
                walk(node["nodes"])

    walk(dj.get("nodes", []))
    return out


def _parse_blocks_draftjs(dj: dict) -> list[tuple[str, str]]:
    """Classic draft.js {"blocks": [...], "entityMap": {...}} format (older entries)."""
    out: list[tuple[str, str]] = []
    entity_map = dj.get("entityMap", {})
    for block in dj.get("blocks", []):
        text = block.get("text", "")
        for er in block.get("entityRanges", []):
            ent = entity_map.get(str(er.get("key")), {})
            if ent.get("type") != "LINK":
                continue
            url = ent.get("data", {}).get("url")
            if not url:
                continue
            offset, length = er.get("offset", 0), er.get("length", 0)
            out.append((text[offset : offset + length], url))
    return out


def extract_links(draftjs_raw: str) -> list[tuple[str, str]]:
    """Return [(label, url), ...] from a question entry's draftjs field,
    handling both the Ricos and classic draft.js shapes."""
    try:
        dj = json.loads(draftjs_raw)
    except (TypeError, ValueError):
        return []
    if "nodes" in dj:
        return _parse_nodes_draftjs(dj)
    return _parse_blocks_draftjs(dj)
