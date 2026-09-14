"""Shopify storefronts whose only price surface is the analytics meta block.

A Shopify theme that emits JSON-LD is already read by the shared tier. Some
themes emit none, and on those the only machine-readable price left is the
block Shopify's own analytics snippet writes::

    window.ShopifyAnalytics.meta.currency = 'PKR';
    var meta = {"product":{"id":8232304083217,"vendor":"Al Khaleej",
        "variants":[{"id":44726425026833,"price":61800,
                     "name":"ACNEFON FACE WASH","public_title":null}]},
        "page":{"pageType":"product"}};

Two properties of that block matter and both are Shopify platform guarantees
rather than theme choices:

* ``price`` is in the currency's **minor unit**. 61800 is PKR 618.00, not
  618 hundred. Banking it raw would inflate every observation on the source
  a hundredfold, so the figure is divided by 100 unless the currency has no
  minor unit at all (JPY, KRW, XPF, ...), where Shopify already reports whole
  units. Cross-checked against a storefront that ships both surfaces: mrdiy_my
  carries ``shopify: 1050`` beside a JSON-LD ``10.50`` MYR, and al_ikhsan_my
  ``9030`` beside ``90.30``.
* ``page.pageType`` says whether this is a product page. Collection and search
  pages carry the same meta shape with a different type, and reading those
  would bank the first variant of an arbitrary tile against a listing URL, so
  anything but ``product`` abstains.

The currency comes from the storefront's own ``ShopifyAnalytics.meta.currency``
rather than from the country: several of these shops price in USD while
serving a non-USD market, and the assignment is emitted on every capture that
carries the meta block at all.

The first variant is the one read. Where a product has several, they are
size or colour options of the same item and the block lists them in the
theme's display order, so the first is the one the page renders as its price.
"""

from __future__ import annotations

import json
import re
from typing import Any

from archived import ZERO_DECIMAL_CURRENCIES, price_row

_META = re.compile(r"var\s+meta\s*=\s*(\{.*?\});\s*$", re.M | re.S)
_CURRENCY = re.compile(r"ShopifyAnalytics\.meta\.currency\s*=\s*['\"]([A-Z]{3})['\"]")


def _script_text(doc: Any) -> str:
    return "\n".join((el.text_content() or "") for el in doc.iter("script"))


def extract(doc: Any, url: str) -> dict | None:
    """The price in this storefront's Shopify analytics meta block, or nothing."""
    blob = _script_text(doc)
    cm = _CURRENCY.search(blob)
    if not cm:
        return None
    currency = cm.group(1)
    for m in _META.finditer(blob):
        try:
            meta = json.loads(m.group(1))
        except ValueError:
            continue
        if not isinstance(meta, dict):
            continue
        page = meta.get("page")
        if isinstance(page, dict) and page.get("pageType") != "product":
            continue
        product = meta.get("product")
        if not isinstance(product, dict):
            continue
        variants = product.get("variants")
        if not isinstance(variants, list) or not variants:
            continue
        first = variants[0]
        if not isinstance(first, dict):
            continue
        minor = first.get("price")
        if not isinstance(minor, (int, float)):
            continue
        if currency.upper() in ZERO_DECIMAL_CURRENCIES:
            price = "%d" % int(minor)
        else:
            price = "%.2f" % (minor / 100.0)
        name = first.get("name") or product.get("title")
        row = price_row(name if isinstance(name, str) else None, price, url, currency)
        if row:
            return row
    return None
