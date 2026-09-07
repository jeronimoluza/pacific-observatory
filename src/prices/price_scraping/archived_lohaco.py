"""Per-source extractor for archived lohaco (Yahoo storefront) captures.

lohaco is a Yahoo!-hosted supermarket (``lohaco.yahoo.co.jp/store/<shop>/item/
<id>``). Every capture in the corpus abstains under every generic tier because
the page carries no JSON-LD, microdata or product OpenGraph tag, yet the page
is dense with real prices: a "popular items" ranking rail rendered on the side
of every product page, pricing 16-50 different products per capture on the 30
design captures and 8-52 on the 80 held-out ones, never the page's own item.
Yield per capture is 28.6 on the design set and 19.5 held out, so the corpus
figure to plan against is the held-out one.

The class ``itemPrice`` is the whole tier. Measured over 30 design captures it
carries a bare yen figure and nothing else on every element wearing it, and
appears on every capture -- 100% precision, 100% coverage. There is no
vocabulary rule anywhere in this file; the two things that make a name and a
price trustworthy are both shape, not words.

The name comes from ``v-card__title``, not from the anchor's own text. Each
priced item is a single ``<div class="v-card__title">`` living inside the
product's own ``<a>``, and reading it directly -- rather than the anchor's
full ``text_content()`` -- sidesteps two problems for free. The anchor also
wraps an SVG rank badge (``<title>ランキング/1位</title>``) and the price div
itself, so the anchor's own text reads ``ランキング/1位 1 <name> 390円``: a
rank prefix ahead of the name and the item's own price appended after it.
Stripping both with a prefix/suffix regex would work until the badge or the
price template changed shape; reading ``v-card__title`` instead never sees
either one to begin with. Measured over every priced item in the 30 design
captures, the title carries the rank prefix zero times and an embedded yen
figure zero times, so no stripping is written here at all.

Both classes sit at a fixed structural depth: the nearest ancestor ``<a>`` of
an ``itemPrice`` element carries exactly one ``v-card__title``, in all 880 of
880 priced items across the design set, with no case of zero or several. That
was true for every product on every capture, so a page carrying a differently
shaped card abstains rather than guessing which title belongs to which price.

The link is the one genuine wrinkle. 596 of 880 anchors carry the product's
own ``/store/<shop>/item/<id>/`` path directly, but 284 route through a
signed ``ck.storematch.jp`` ad redirect whose query string -- a ``rid``/``qid``
request id and a ``sig`` signature -- is unique on every single occurrence
(284 distinct redirect URLs for 284 redirect rows). Banking that link as the
row's URL would give the same product a new identity on every capture, which
is exactly what a price series must not do. Its ``code`` query parameter is
the same ``<shop>_<id>`` pair the direct links carry in their path --
confirmed by reconstructing a path from every redirect's ``code`` and finding
it lands on a path a direct anchor elsewhere in the design set already used,
for all 21 products the design set happened to show both ways -- so the
canonical path is rebuilt from that parameter instead of the redirect being
followed.

Reconstructing that path surfaces one more thing once it is done: 23 of the
880 rows across the design set turn out to duplicate another row on the very
same capture -- the same product reachable twice on one page, once through a
direct link and once through the ad redirect, so it prices twice with the
resolved URL now identical. Every one of those 23 pairs agreed on the price,
so the second occurrence is dropped as a redundant read of the same
observation rather than a second one; a resolved URL that disagreed with
itself on the same page would instead be dropped entirely, since nothing here
says which of the two figures is the real one.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from .archived import normalize_price, price_row

_YEN_FIGURE = re.compile("[\\d,]{2,}\\s*円")
_REDIRECT_CODE = re.compile("^([^_]+)_(.+)$")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _resolve_href(href: str | None, url: str) -> str:
    if not href:
        return url
    if href.startswith("/store/"):
        return urljoin(url, href)
    if "storematch.jp" in href:
        code = parse_qs(urlparse(href).query).get("code", [""])[0]
        m = _REDIRECT_CODE.match(code)
        if m:
            return urljoin(url, "/store/%s/item/%s/" % (m.group(1), m.group(2)))
        return url
    if href.startswith("http"):
        return href
    return urljoin(url, href)


def extract(doc: Any, url: str) -> list[dict]:
    """Every ranking-rail row this capture prices, read by class and shape alone."""
    pairs = []
    for el in doc.iter():
        if not isinstance(el.tag, str) or "itemPrice" not in _classes(el):
            continue
        found = _YEN_FIGURE.search(_text(el))
        if not found:
            continue

        anchor, up = el.getparent(), 0
        while anchor is not None and anchor.tag != "a" and up < 6:
            anchor, up = anchor.getparent(), up + 1
        if anchor is None or anchor.tag != "a":
            continue

        titles = [c for c in anchor.iter()
                  if isinstance(c.tag, str) and "v-card__title" in _classes(c)]
        if len(titles) != 1:
            continue

        target = _resolve_href(anchor.get("href"), url)
        pairs.append((_text(titles[0]), found.group(0), target))

    prices_per_target: dict[str, set] = {}
    for _, price, target in pairs:
        prices_per_target.setdefault(target, set()).add(price)

    rows = []
    for name, price, target in dict.fromkeys(pairs):
        if len(prices_per_target[target]) > 1:
            continue
        row = price_row(name, normalize_price(price, "JPY"), target, "JPY")
        if row:
            rows.append(row)
    return rows
