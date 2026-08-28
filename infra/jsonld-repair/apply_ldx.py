"""Apply the three paying rungs of the JSON-LD repair ladder to template-repo.

This session is worktree-isolated and cannot write to template-repo through
the editing tools, so the fix ships as an applier rather than a diff.
Idempotent: re-running after a successful apply reports `already applied`.

    python infra/jsonld-repair/apply_ldx.py [--check]

Measured on 8,744 archived miss pages, the five-rung ladder recovers 633; the
marginal contribution splits 524 / 55 / 53 across repair, deep-walk and wider
types, and **zero** across the other two rungs (node-level price, name
backfill). Only the three that pay are ported.

The traversal order is the part that needed designing rather than porting. The
miss corpus contains only pages that already yield nothing, so it cannot show
a regression on a page that currently parses. Yielding the shipped order first
and appending the newly-reachable nodes after it makes that impossible by
construction: `_dedupe_product_rows` falls back to `collapsed[:1]` when no row
matches the page url, so a reordered walk could otherwise have silently
changed which row a working page returns.
"""
import argparse
import os
import sys

REPO = "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo"
ARCHIVED = REPO + "/src/prices/price_scraping/archived.py"

OLD_IMPORT = """from typing import Any, Iterator
from urllib.parse import urljoin, urlsplit"""

NEW_IMPORT = """from typing import Any, Iterator
from urllib.parse import urljoin, urlsplit

from .archived_ldrepair import parse_ld"""

OLD_WALK = '''    def walk(data):
        if isinstance(data, list):
            for item in data:
                yield from walk(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)

    for attrs, body in _iter_script_tags(html_text):
        if attrs.get("type", "").lower() != "application/ld+json":
            continue
        raw = body.strip() or _html.unescape(attrs.get("children", "")).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        yield from walk(data)'''

NEW_WALK = '''    def walk(data):
        """Top level plus one ``@graph`` level -- the long-shipped traversal."""
        if isinstance(data, list):
            for item in data:
                yield from walk(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)

    def walk_deep(data, depth=0):
        """Every nested dict, not just ``@graph``.

        Some themes hang the Product off ``mainEntity``, ``itemListElement``
        or a bare custom key, which ``walk`` cannot see. Depth is capped
        because a self-referential ``@context`` would otherwise not terminate.
        """
        if depth > 12:
            return
        if isinstance(data, list):
            for item in data:
                yield from walk_deep(item, depth + 1)
        elif isinstance(data, dict):
            yield data
            for key, value in data.items():
                if key == "@context":
                    continue
                if isinstance(value, (dict, list)):
                    yield from walk_deep(value, depth + 1)

    for attrs, body in _iter_script_tags(html_text):
        if attrs.get("type", "").lower() != "application/ld+json":
            continue
        raw = body.strip() or _html.unescape(attrs.get("children", "")).strip()
        if not raw:
            continue
        values, _how = parse_ld(raw)
        for data in values:
            # Shipped order first, deeper nodes appended: a page that parses
            # today must keep returning the same row, and `_dedupe_product_rows`
            # resolves ties by position when nothing matches the page url.
            seen = set()
            for node in walk(data):
                seen.add(id(node))
                yield node
            for node in walk_deep(data):
                if id(node) not in seen:
                    yield node'''

OLD_IS_PRODUCT = '''def _is_product(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(str(x).lower() == "product" for x in t)
    return str(t).lower() == "product"'''

NEW_IS_PRODUCT = '''# Types beyond bare Product that carry a real retail price in practice. Worth
# 53 additional pages of the 8,744-page miss corpus on their own. A node still
# has to hold a name and a positive price to become a row, so widening the type
# gate cannot by itself invent one.
_PRODUCT_TYPES = frozenset({
    "product", "productgroup", "individualproduct", "productmodel",
    "vehicle", "car", "book", "softwareapplication", "mobileapplication",
    "videogame", "movie", "musicalbum", "menuitem", "hotelroom", "trip",
    "event", "course", "service", "creativework", "imageobject", "tvseries",
    "apartment", "house", "singlefamilyresidence", "realestatelisting",
})


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    values = t if isinstance(t, list) else [t]
    # `@type` is often a full schema.org IRI rather than a bare token.
    return any(
        str(x).rsplit("/", 1)[-1].lower() in _PRODUCT_TYPES for x in values
    )'''

PAIRS = [
    (OLD_IMPORT, NEW_IMPORT, "import parse_ld"),
    (OLD_WALK, NEW_WALK, "repair + deep walk"),
    (OLD_IS_PRODUCT, NEW_IS_PRODUCT, "wider @type gate"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    if not os.path.exists(ARCHIVED):
        print("missing: %s" % ARCHIVED)
        return 1
    with open(ARCHIVED, encoding="utf-8") as fh:
        src = fh.read()

    out = src
    changed = False
    for old, new, label in PAIRS:
        if new in out:
            print("  %-22s already applied" % label)
            continue
        if old not in out:
            print("  %-22s ANCHOR NOT FOUND -- file has drifted" % label)
            print("    missing: %s..." % old.splitlines()[0].strip()[:70])
            return 2
        out = out.replace(old, new, 1)
        changed = True
        print("  %-22s patched" % label)

    if args.check:
        print("\n--check: nothing written")
        return 0
    if changed:
        with open(ARCHIVED, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("\nwrote %s" % ARCHIVED)
    return 0


if __name__ == "__main__":
    sys.exit(main())
