"""Per-source extractor for archived aanbodcuracao_cw (aanbodcuracao.com).

The 2024-2025 captures are an Osclass classifieds site ("beta" theme) that
prints ad prices as text with no structured markup. Search, category, region
and home pages (``index.php?page=search...``, ``index.php``) list ads as cards;
each card prints its price twice, once per view mode::

    <div class="simple-prod o1 ">
      <div class="img-wrap"><a class="img" href="...page=item&id=493">...</div>
      <div class="data">
        <div class="price isGrid"><span>485.00 ANG</span></div>
        <a class="title" href="...page=item&id=493">Tekoop Makita Weed Eater DUR181 ...</a>
        <div class="description isList">Makita Weed Eater DUR181 di Bateria ...</div>
        <div class="price isList mbCl"><span>485.00 ANG</span></div>

A card is kept only when both copies read exactly ``<number> ANG`` and agree.
Each ad is read once (by its ``id``), even if it also appears as a premium card.

ANG (Netherlands Antillean guilder) is recorded, never read from the page.

Abstains on: "Bespreek met verkoper" (price on request) and "Gratis" cards
(free is not a price of 0); any card whose price is not written as ``x ANG``;
any card whose description mentions another currency (e.g. "50 euro p.p" on
an ANG-priced dive ad, or "XCG 80.00" for the 2025 Caribbean guilder),
since the figure's currency is then in doubt; and item / "send to a friend"
pages (``#listing``), whose own ad block is empty in the archive and whose
cards are other ads. User profiles, info pages and empty search results carry
no cards and yield nothing.
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "ANG"
_ANG = re.compile(r"^(\d[\d,]*(?:\.\d+)?)\s*ANG$")
# XCG, the Caribbean guilder that replaced ANG in 2025, counts as foreign too.
_FOREIGN = re.compile(r"\$|€|\bUSD\b|\bEUR\b|\beuros?\b|\bdollars?\b|\bXCG\b|\bCg\b", re.I)
_ITEM_ID = re.compile(r"[?&]id=(\d+)")
_CARD = '//div[contains(concat(" ", normalize-space(@class), " "), " simple-prod ")]'
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _price(card: Any) -> str | None:
    texts = {_text(el) for el in card.xpath('.//div[contains(@class, "price")]')}
    if len(texts) != 1:
        return None
    m = _ANG.match(texts.pop())
    return normalize_price(m.group(1), _CURRENCY) if m else None


def _cards(doc: Any, url: str) -> list[dict]:
    rows, seen = [], set()
    for card in doc.xpath(_CARD):
        titles = card.xpath('.//a[@class="title"]')
        if len(titles) != 1:
            continue
        m = _ITEM_ID.search(titles[0].get("href") or "")
        key = m.group(1) if m else _text(titles[0])
        if key in seen:
            continue
        seen.add(key)
        if _FOREIGN.search(" ".join(_text(d) for d in card.xpath('.//div[contains(@class, "description")]'))):
            continue
        row = price_row(_text(titles[0]), _price(card), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def extract(html: str, url: str) -> list[dict]:
    """Own ad prices on an archived aanbodcuracao_cw listing page."""
    doc = lxml.html.fromstring(_XML_DECL.sub("", html, count=1))
    if doc.xpath('//div[@id="listing"]'):
        return []
    return _cards(doc, url)
