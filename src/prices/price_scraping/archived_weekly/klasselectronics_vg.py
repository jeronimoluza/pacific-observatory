"""Per-source extractor for archived klasselectronics_vg (klass-electronics.com) captures.

One USD catalog for Tortola (BVI) and St Maarten. Single-product pages under
``/product/<slug>/`` (2026 crawls) are WooCommerce rendered through an
Elementor single-product template (``elementor-location-single``) on the Hello
theme. The product's own price is a lone amount in an Elementor icon-list
widget; older items also carry a one-row ``variations_form`` whose
``display_price`` repeats it (its attributes are placeholder ``Black``/``PS4``
on gift cards and games, so they are not variant names)::

    <h1 class="product_title entry-title elementor-heading-title ...">Switch Carnival Games</h1>
    <span class="elementor-icon-list-text"><span class="woocommerce-Price-amount amount">
      <span class="woocommerce-Price-currencySymbol">$</span>49.00</span></span>
    <form class="variations_form cart" data-product_variations="[{... &quot;display_price&quot;:49 ...}]">

A related-products carousel below reuses ``h1.product_title`` and the same
amount markup inside ``e-loop-item``/``swiper-slide`` loop containers, and the
header mini-cart shows a ``$0`` total (``elementor-menu-cart``); both are
ignored. Rows come only from the main heading plus the main amount; all main
copies and every variation ``display_price`` must agree on one figure.

Eras covered: 2026 WooCommerce/Elementor product pages. Yields nothing for
the 2013-2017 legacy shop, 2018-19 Shopify pages ($0.00 placeholders), the
2020-21 Magento-style "call for price" site, the late-2026 Astra-theme pages
(empty ``p.price``), category/brand/tag archives, and product pages whose
template renders no price (no cart form).

Abstains on: struck-through ``<del>`` figures, any extra wording around the
figure (ranges, ``From``), main copies or variations that disagree, zero
prices, and pages without a single main ``product_title`` heading.
"""
from __future__ import annotations

import json
import re

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "USD"
_SKIP = {"e-loop-item", "elementor-loop-container", "swiper-slide", "swiper-wrapper",
         "products", "related", "upsells", "elementor-menu-cart__wrapper",
         "widget_shopping_cart_content", "elementor-menu-cart__container"}
_AMOUNT = '//*[contains(concat(" ", normalize-space(@class), " "), " woocommerce-Price-amount ")]'


def _classes(el) -> set:
    return set((el.get("class") or "").split())


def _skipped(el) -> bool:
    return any(_classes(a) & _SKIP or a.tag == "del" for a in el.iterancestors())


def _amount_price(amt) -> str | None:
    holder = amt.getparent()
    if " ".join(holder.text_content().split()) != " ".join(amt.text_content().split()):
        return None
    return normalize_price(" ".join(amt.text_content().split()), _CURRENCY)


def _variation_prices(doc) -> set | None:
    out = set()
    for form in doc.xpath("//*[@data-product_variations]"):
        if _skipped(form):
            continue
        try:
            variations = json.loads(form.get("data-product_variations") or "")
        except ValueError:
            return None
        if not isinstance(variations, list):
            return None
        for v in variations:
            dp = v.get("display_price") if isinstance(v, dict) else None
            if not isinstance(dp, (int, float)) or isinstance(dp, bool):
                return None
            out.add(normalize_price(str(dp), _CURRENCY))
    return out


def extract(html: str, url: str) -> list[dict]:
    html = re.sub(r"^\s*<\?xml[^>]*\?>", "", html)
    doc = lxml.html.fromstring(html)
    body = doc.xpath("//body")
    if not body or "single-product" not in _classes(body[0]):
        return []
    titles = [t for t in doc.xpath('//h1[contains(concat(" ", normalize-space(@class), " "), " product_title ")]')
              if not _skipped(t)]
    if len(titles) != 1:
        return []
    name = " ".join(titles[0].text_content().split())
    prices = {_amount_price(a) for a in doc.xpath(_AMOUNT) if not _skipped(a)}
    if len(prices) != 1:
        return []
    variations = _variation_prices(doc)
    if variations is None or (variations and variations != prices):
        return []
    row = price_row(name, prices.pop(), url, _CURRENCY)
    return [row] if row else []
