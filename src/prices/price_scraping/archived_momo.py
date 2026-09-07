"""Per-source extractor for archived momo_tw (momoshop.com.tw) captures.

momo_tw is one of the largest Taiwanese online retailers and accounts for
343,320 misses -- every one of them lacking JSON-LD, microdata or a product
OpenGraph tag. The 30-capture design set holds two eras of a product-detail
template, both keyed on the class ``special``, and both agree on one thing:
the figure it carries is what a buyer pays right now, never a shipping fee,
a loyalty-point rebate or an instalment plan. Those live nearby -- 運費
(postage), 紅利 (points), 分期 (instalments) and 滿額 (bundle thresholds) all
appear on the same page, sometimes a dozen times over -- but none of them is
ever classed ``special``, so scoping to the class rather than to any of that
vocabulary is what keeps them out.

The two eras differ in where the number sits relative to the class, not in
what the class means:

* The newer template (all 20 product pages in the 2018-04 design sample, and
  two of five product pages sampled separately from 2015-16) puts the class on
  the ``<li>`` itself, labelled 促銷價 (promotional price) or 折扣後價格 (price
  after discount) depending on whether a markdown is active, with the figure
  isolated in a bare, unclassed child ``<span>`` -- ``促銷價<span>580</span>
  元``. Held out, one capture also carried a second ``<span class=
  "aferPromobtn">`` badge ("order and get a further discount") after the price
  -- of 64 span children found under ``<li class="special">`` across every
  cache checked, 63 carried no class at all and only that one did, so the
  price is read from the *classless* span rather than assuming there is
  exactly one span to begin with.
* The older template (three of five captures sampled from 2013-2015) instead
  puts the class on a ``<th>`` that is only ever the row *label* 促銷價, empty
  of any figure; the price is a sibling ``<td>``'s single ``<b>`` tag one row
  below the struck-through 市價 (list price), which is never read. Matching a
  ``<th>`` and reading its very next sibling keeps this era from ever picking
  up that list price, which sits in the row above under a plain, unclassed
  ``<th>``.

A page carrying neither shape, or a ``special`` element that does not resolve
to exactly one distinct figure, abstains -- observed only on the site's own
"product no longer available" redirect stub (``Notice.jsp?msg1=FA0064``),
which appears with no title and no ``special`` element at all in ten of the
thirty design captures and five of fifteen sampled separately from 2013-2016.

Neither era's markup contains ``NT$`` next to a ``special``-classed figure in
any of the 45 captures checked; the site does print that prefix elsewhere
(the category filter widget's "price range (NT$)" label), which is exactly
the kind of near-miss this tier does not go looking for.

The product name comes from ``h1``, present with exactly one occurrence
carrying the item's own name on every product page in both caches; a second,
site-wide ``h1`` naming the site's parent company follows it and is never the
first match.
"""

from __future__ import annotations

from typing import Any

from .archived import normalize_price, price_row

_SPECIAL = "special"


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _special_price(doc: Any) -> str | None:
    """The one figure the page's own ``special`` element carries, or nothing.

    The newer template's ``<li class="special">`` wraps its figure in exactly
    one classless child ``<span>``, ignoring any further, classed badge
    ``<span>`` beside it; the older template's ``<th class="special">`` is a
    bare label whose figure is its sibling ``<td>``'s one ``<b>`` tag. Either
    shape failing to resolve to exactly one candidate -- absent, or more than
    one distinct figure across however many ``special`` elements a page turns
    out to carry -- abstains rather than guess which one is real.
    """
    candidates = []
    for el in doc.iter():
        if not isinstance(el.tag, str) or _SPECIAL not in _classes(el):
            continue
        if el.tag == "li":
            spans = [
                c for c in el.iterchildren()
                if isinstance(c.tag, str) and c.tag == "span" and not _classes(c)
            ]
            if len(spans) == 1:
                candidates.append(_text(spans[0]))
        elif el.tag == "th":
            td = el.getnext()
            if td is not None and isinstance(td.tag, str) and td.tag == "td":
                bolds = list(td.iter("b"))
                if len(bolds) == 1:
                    candidates.append(_text(bolds[0]))
    prices = set(candidates)
    if len(prices) != 1:
        return None
    return normalize_price(prices.pop(), "TWD")


def extract(doc: Any, url: str) -> dict | None:
    """The price a momo_tw product page's own ``special`` element carries."""
    price = _special_price(doc)
    h1 = doc.find(".//h1")
    name = _text(h1) if h1 is not None else ""
    return price_row(name.strip() or None, price, url, "TWD")
