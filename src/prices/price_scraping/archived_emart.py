"""Per-source extractor for emart_kr archived pages.

emart.ssg.com carries no JSON-LD, no microdata and no product OpenGraph tag in
the era this corpus spans, so every portable tier abstains and all 91,211
captures bank as misses. Its own markup is stable across them, but it prints
four won figures per page and only one is the price the page charges.

The one to read is 최적가 ("best price"), in ``.cdtl_optprice``. The three to
refuse all live in ``.cdtl_card_price`` / ``.cdtl_card_dl`` under class
``cdtl_price``, whose name makes them look like the obvious choice: they are
bank-card conditional prices, each labelled with the issuer and the spend
threshold that unlocks it ("수협 7만원 이상 결제시 8%할인" -- Suhyup card, 8%
off over KRW 70,000). Measured on one capture: 최적가 59,800 against
``cdtl_price`` figures of 55,016 and 56,810, which are exactly 0.92x and 0.95x
of it. Banking those would write a discount conditional on holding a specific
Korean credit card into a national price series.

``em.point`` is a loyalty-point award, also in won, and is likewise not a
price.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row

# 최적가, the page's own price. The label sits in the same element as the
# figure, so it is stripped rather than matched around.
_OPT_PRICE_CLASS = "cdtl_optprice"
_CARD_CLASSES = frozenset({"cdtl_card_price", "cdtl_card_dl"})
_WON = re.compile(r"([\d,]{2,})\s*원")
_TITLE_TAIL = " - 이마트몰"


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _under_card_block(el: Any) -> bool:
    node = el.getparent()
    while node is not None:
        if _CARD_CLASSES & set(_classes(node)):
            return True
        node = node.getparent()
    return False


def extract(doc: Any, url: str) -> dict | None:
    """The won figure emart charges for this page's product, or nothing.

    The name comes from ``<title>``, which is always "<name> - 이마트몰, 당신과
    가장 가까운 이마트". The ``h1`` is present but empty on every capture
    inspected, so the title is the only name source that works at all; the
    scoring pass that first looked at this source read cov 100% / prec 100%
    but 0.00 rows per capture for exactly that reason.
    """
    price_el = None
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        if _OPT_PRICE_CLASS in _classes(el) and not _under_card_block(el):
            price_el = el
            break
    if price_el is None:
        return None
    found = _WON.search(_text(price_el))
    if not found:
        return None

    title_el = doc.find(".//title")
    title = _text(title_el) if title_el is not None else ""
    name = title.split(_TITLE_TAIL, 1)[0].strip()
    return price_row(name or None, normalize_price(found.group(1), "KRW"),
                     url, "KRW")
