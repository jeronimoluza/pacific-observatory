"""Keyword pack and known-storefront domain list for Common Crawl scanning.

Split out of ``cc_table.py`` to keep that module under the 500-line cap.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Shorter slugs collide with unrelated words often enough to swamp the result.
_MIN_TERM_LENGTH = 4


def known_domains() -> List[str]:
    """Registered domains of every storefront that has an ``archive_prefix``.

    Matching on the registered domain rather than the exact host also picks up
    sibling subdomains (``shop.cosmed.com.tw`` under ``cosmed.com.tw``), which
    is what an enumeration wants; ``archive_path_re`` narrows it back down
    later. The same set is what the candidate summary excludes on, so a
    retailer we already scrape never comes back as a discovery.
    """
    import tldextract

    from .cc_config import all_cc_configs

    domains: set = set()
    for cfg in all_cc_configs().values():
        host = cfg["prefix"].partition("/")[0].lower()
        if not host:
            continue
        ext = tldextract.extract(host)
        if ext.registered_domain:
            domains.add(ext.registered_domain)
    return sorted(domains)


def load_keyword_regex(path: Path, max_terms: Optional[int] = None) -> str:
    """Build one alternation from a newline-delimited term file.

    Terms go into the URL *path*, so they are slug-matched: spaces become the
    hyphen-or-underscore class that storefront slugs actually use. One
    alternation over one scan costs the same as a single term — the scan, not
    the pattern, is what the read is paying for.
    """
    lines = (ln.strip().lower() for ln in path.read_text().splitlines())
    terms = [ln for ln in lines if ln and not ln.startswith("#")]
    terms = [t for t in terms if len(t) >= _MIN_TERM_LENGTH]
    if max_terms:
        terms = terms[:max_terms]
    if not terms:
        raise ValueError(f"{path} has no usable terms (>= {_MIN_TERM_LENGTH} chars)")

    alts = []
    for term in sorted(set(terms)):
        parts = [re.escape(p) for p in term.split()]
        alts.append("[-_]".join(parts))
    body = "|".join(alts)
    # Slug boundaries, or `rice` matches `/price-list` on every storefront and
    # the candidate list degenerates into "every site that sells anything".
    return f"(^|[-_/])({body})([-_/.]|$)"
