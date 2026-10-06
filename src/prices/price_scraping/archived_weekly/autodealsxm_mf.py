"""Per-source extractor for archived autodealsxm_mf (autodealsxm.com) captures.

The store is a WordPress/Divi site with no cart: category pages (2021 slugs
like ``/cuiseur-vapeur/``, 2022-2024 ``/produits/<rayon>/<sous-rayon>/``) lay out
products as an image module followed by a text module holding the name and the
price as two centred paragraphs::

    <div class="et_pb_text_inner"><p style="text-align: center;">Cuiseur vapeur
      Brentwood TS-1005</p>
    <p style="text-align: center;"><strong>29€</strong></p></div>

Only that text module is read. The image filename and alt text often carry a
price too (``LG-32LJ570-429€.jpg`` above a ``299€`` text module) -- a stale
earlier price -- so images are never read. For the same reason the 2021 WordPress
attachment pages (``/planche-a-decouper-cuisinart-cpb-15sr-20e/``), whose only
price is the uploaded image's title, are abstained on.

Abstains on any text module that is not exactly a name paragraph followed by a
paragraph that is a bare euro amount -- e.g. ``(En commande) 199€``, ``€`` with
no figure, or split figures like ``<strong>1</strong><strong>99€</strong>``.
Robots, contact, image URLs and pages built from other module types yield nothing.
"""
from __future__ import annotations

import re

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "EUR"
_AMOUNT = re.compile(r"^(\d+(?:[.,]\d{2})?)\s*€$")


def _text(el) -> str:
    return " ".join((el.text_content() or "").split())


def extract(html: str, url: str) -> list[dict]:
    doc = lxml.html.fromstring(html)
    rows = []
    for box in doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " et_pb_text_inner ")]'):
        kids = [el for el in box if _text(el)]
        if len(kids) != 2 or any(el.tag != "p" for el in kids):
            continue
        name, raw = _text(kids[0]), _text(kids[1])
        m = _AMOUNT.match(raw)
        if not m or not re.search(r"[^\W\d_]", name):
            continue
        row = price_row(name, normalize_price(m.group(1), _CURRENCY), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
