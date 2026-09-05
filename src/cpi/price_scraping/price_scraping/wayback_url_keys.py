"""
Per-spider URL key extractors for Wayback Machine prefix matching.

IA archives the same product page in many URL forms (scheme, www/non-www,
:80, .html, query strings, utm_* tracking, page=N, etc.). Pure character
normalization can't reliably bridge these, so each spider declares an
extractor that returns a stable product identifier from any URL form.

Extractor contract:
    (url: str) -> Optional[str]
    Return None for non-product URLs (homepage, category, etc.) — those are
    skipped during matching.

When a spider has no registered extractor, the wayback scraper falls back to
lowercase + strip-trailing-slash matching, which usually misses everything.
Registering an extractor is the explicit opt-in for "this spider's wayback
data is recoverable."
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Optional

URL_KEY_EXTRACTORS: Dict[str, Callable[[str], Optional[str]]] = {}


def register(spider_name: str):
    def decorator(fn: Callable[[str], Optional[str]]):
        URL_KEY_EXTRACTORS[spider_name] = fn
        return fn

    return decorator


def get_key_extractor(
    spider_name: str,
) -> Optional[Callable[[str], Optional[str]]]:
    return URL_KEY_EXTRACTORS.get(spider_name)


# ---------------------------------------------------------------------------
# Registered extractors
# ---------------------------------------------------------------------------


@register("horizon_farms")
def _horizon_farms(url: str) -> Optional[str]:
    """Shopify URL pattern: /products/<slug> on en.horizonfarms.jp.
    The slug (e.g. 'bf100', 'pl506') is the stable product key.
    """
    m = re.search(r"/products/([^/?#]+)", url)
    return m.group(1).lower() if m else None


@register("guardian_my")
def _guardian_my(url: str) -> Optional[str]:
    """Product ID is a 6+ digit run anywhere in the URL path. Real IDs are
    9 digits (e.g. 121123528) so we pick the longest digit run to avoid
    accidental matches on size/quantity tokens. Strips query string first
    so tracking IDs (utm_*, srsltid, etc.) are ignored.

    Matches all of:
      .../dermacyn-solution-500ml-121123528
      .../dermacyn-solution-500ml-121123528.html?page=1
      .../121110853-similac-neosure-850g     (ID at start)
      .../3m-kn95-respirator-mask-1s-121111651.html

    Returns None for products without a numeric ID (older items like
    '1028-dew-block-…') — those are genuinely unmatchable via URL key.
    """
    path = url.split("?", 1)[0].split("#", 1)[0]
    matches = re.findall(r"\d{6,}", path)
    if not matches:
        return None
    return max(matches, key=len)
