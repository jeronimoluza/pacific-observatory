"""Per-source extractor for archived supermax_pr captures.

SuperMax is a Puerto Rican supermarket chain: 9,800 miss records over
2018-2025, product pages under
``/<store>/<department>/<category>/<id>/<slug>``.

The charged price is an ``h2.product-price`` and appears once. A ``<small>``
immediately after it carries the pre-discount figure as plain text::

    <h2 class="product-price">$5.99</h2> <small> Regular $8.69

The regular price is not in a class of its own, so it cannot be excluded by
name -- it is excluded by reading only the ``product-price`` element's own
text and never its following siblings. On the sampled capture the difference
is 45%, which is the size of error this avoids.

Puerto Rico uses the US dollar, and the markup quotes "$" with no other
currency present.

The name comes from ``og:title``, which prefixes "SuperMaxOnline - "; there is
no ``h1``.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "USD"
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_PREFIX = "SuperMaxOnline - "
_CLS = 'contains(concat(" ", normalize-space(@class), " "), " product-price ")'


def _name(doc: Any) -> str | None:
    for el in doc.xpath('//meta[@property="og:title"]/@content'):
        txt = " ".join(str(el).split())
        if txt.startswith(_PREFIX):
            txt = txt[len(_PREFIX):]
        if txt:
            return txt.strip()
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The charged price on an archived supermax product page, or nothing."""
    for el in doc.xpath("//*[%s]" % _CLS):
        m = _NUM.search((el.text_content() or "").replace(",", ""))
        if m:
            return _row(_name(doc), m.group(0), url, _CURRENCY)
    return None
