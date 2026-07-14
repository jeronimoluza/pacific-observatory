"""Country-slug -> primary language resolution via countries.yaml.

Small shared helper (lazy module-level cache) used by the regex registry to pick
per-country pack patterns. Returns None when the slug is missing or the yaml is
unavailable.
"""

from __future__ import annotations

from typing import Optional

_LANG_MAP_CACHE: Optional[dict[str, str]] = None


def resolve_lang(country: str) -> Optional[str]:
    global _LANG_MAP_CACHE
    if _LANG_MAP_CACHE is None:
        try:
            from core.config import load_countries

            mp: dict[str, str] = {}
            for slug, meta in load_countries().items():
                langs = meta.get("languages") or []
                if langs:
                    mp[slug] = langs[0]
            _LANG_MAP_CACHE = mp
        except Exception:
            _LANG_MAP_CACHE = {}
    return _LANG_MAP_CACHE.get(country)
