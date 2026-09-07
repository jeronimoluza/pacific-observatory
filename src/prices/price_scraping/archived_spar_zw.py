"""Per-source extractor for archived spar_zw (spar.co.zw) captures.

spar_zw resolved 40,230 captures across 2019-2025 and parsed none of them. The
captures are single-product pages under ``/products/<id>/<slug>`` and they do
carry a price -- it is simply written as plain text in a class no generic tier
reaches::

    <h3 class="title">BALANCE PINOT GRIGIO 750ML</h3>
    <p><strong>TOPS</strong> / WINE WHITE</p>
    <p class="price"> USD&#36;7.80 </p>

The figure is quoted in US dollars rather than in Zimbabwe's own currency,
which is what the storefront itself prices in, so USD is recorded rather than
inferred from the country.

The dollar sign arrives HTML-escaped (``&#36;``); lxml decodes it on access, so
the figure is taken from the decoded text and the currency word and symbol are
stripped by matching the number rather than by trimming a fixed prefix.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "USD"
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _first(doc: Any, xpath: str) -> str | None:
    for el in doc.xpath(xpath):
        txt = " ".join((el.text_content() or "").split())
        if txt:
            return txt
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The price on an archived spar_zw product page, or nothing."""
    raw = _first(doc, '//*[contains(concat(" ", normalize-space(@class), " "), " price ")]')
    if not raw:
        return None
    m = _NUM.search(raw.replace(",", ""))
    if not m:
        return None
    name = _first(doc, '//*[contains(concat(" ", normalize-space(@class), " "), " title ")]')
    return _row(name, m.group(0), url, _CURRENCY)
