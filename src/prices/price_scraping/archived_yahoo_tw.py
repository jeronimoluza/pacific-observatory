"""Per-source extractor for yahoo_shopping_tw archived pages.

tw.buy.yahoo.com emits no portable surface in the era this corpus spans, so
all 173,217 captures bank as misses. It has two templates and they disagree
about what a class called ``price`` means, so both are handled explicitly
rather than through one selector that happens to hit something on each.

The 2019 template -- 60% of this source's misses -- prints exactly one figure,
in ``HeroInfo__mainPrice___<hash>``, and carries the product name in an
``h1``. The hash is a build artifact and changes whenever the site is rebuilt,
so the class is matched on its stem.

The older template (2014-2017, ~35%) prints two figures side by side, and the
one class ``price`` holds is the struck-through 建議售價, the suggested retail
price -- measured $2,680 against a charged $2,412, $30,900 against $23,900.
The charged figure is in ``.priceinfo``. Two further ``price`` elements on the
same page hold a cart total of zero and, under ``rprice``, an instalment
amount ("6期0利率 每期 402元起" -- 402 being exactly one sixth of 2,412).
Reading class ``price`` on this template would have banked a list price for
every row, which is the same defect already found and refused on
hepsiburada.com.tr.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row

_HERO_PRICE_STEM = "HeroInfo__mainPrice___"
_HERO_TITLE_STEM = "HeroInfo__title___"
_LEGACY_PRICE_CLASS = "priceinfo"
_MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
# "<name> - Yahoo!奇摩購物中心", "<name> | <breadcrumb> | Yahoo奇摩購物中心",
# and captures whose title was truncated mid-suffix ("... - Yahoo", "... - Y").
_TITLE_TAIL = re.compile(r"\s*[-|]\s*Yahoo.*$")


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _first_with_stem(doc: Any, stem: str) -> Any:
    for el in doc.iter():
        if isinstance(el.tag, str) and any(
                c.startswith(stem) for c in _classes(el)):
            return el
    return None


def _first_with_class(doc: Any, name: str) -> Any:
    for el in doc.iter():
        if isinstance(el.tag, str) and name in _classes(el):
            return el
    return None


def _name_from_title(doc: Any) -> str | None:
    el = doc.find(".//title")
    if el is None:
        return None
    return _TITLE_TAIL.sub("", _text(el)).split("|", 1)[0].strip() or None


def extract(doc: Any, url: str) -> dict | None:
    """The charged NT$ figure for this page's product, whichever template it is."""
    price_el = _first_with_stem(doc, _HERO_PRICE_STEM)
    name = None
    if price_el is not None:
        title_el = _first_with_stem(doc, _HERO_TITLE_STEM)
        if title_el is not None:
            name = _text(title_el) or None
    else:
        price_el = _first_with_class(doc, _LEGACY_PRICE_CLASS)
    if price_el is None:
        return None
    found = _MONEY.search(_text(price_el))
    if not found:
        return None
    if name is None:
        name = _name_from_title(doc)
    return price_row(name, normalize_price(found.group(1), "TWD"), url, "TWD")
