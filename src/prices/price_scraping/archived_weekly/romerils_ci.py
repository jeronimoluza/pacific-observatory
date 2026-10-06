"""Per-source extractor for archived romerils_ci (romerils.com) captures.

Single-product pages under ``/product/<slug>/`` (2020-2025) are WooCommerce
rendered through Elementor templates. The product's own price sits in a
``woocommerce-product-price`` widget, often twice (mobile and desktop copies),
next to a related-products carousel that reuses the very same markup::

    <h1 class="product_title entry-title ...">Venice Sofa Bed Cyan</h1>
    <p class="price product-page-price price-on-sale">
      <del><span class="woocommerce-Price-amount amount">&pound;599.00</span></del>
      <ins><span class="woocommerce-Price-amount amount">&pound;479.00</span></ins>
    </p>

Related items live inside loop containers (``elementor-post``/``swiper-slide``
grid items, Flatsome ``product-small`` boxes, ``ul.products``), so every
``.price`` with such an ancestor is ignored. Of what remains, the struck-through
``<del>`` figure and screen-reader text are dropped and the single remaining
amount is the current price; all main-price copies must agree.

Abstains on: price ranges (variable products), empty price blocks (made-to-
measure carpets, price-on-application), any extra wording around the figure
(``From``, ``per m2``), copies that disagree, and pages without a
``product_title`` heading.
"""
from __future__ import annotations

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "GBP"
_LOOP = {"elementor-post", "swiper-slide", "product-small", "product-inner",
         "woocommerce-LoopProduct-link", "e-loop-item", "products", "ecs-post-loop"}


def _classes(el) -> set:
    return set((el.get("class") or "").split())


def _in_loop(el) -> bool:
    for a in el.iterancestors():
        cls = _classes(a)
        if cls & _LOOP or (a.tag == "li" and "product" in cls):
            return True
    return False


def _price_of(p) -> str | None:
    p = lxml.html.fromstring(lxml.html.tostring(p))
    for junk in p.xpath('.//del | .//*[contains(concat(" ", normalize-space(@class), " "), " screen-reader-text ")]'):
        junk.drop_tree()
    amounts = p.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " woocommerce-Price-amount ")]')
    if len(amounts) != 1:
        return None
    raw = " ".join(amounts[0].text_content().split())
    amounts[0].drop_tree()
    if " ".join(p.text_content().split()):
        return None
    return normalize_price(raw, _CURRENCY)


def extract(html: str, url: str) -> list[dict]:
    doc = lxml.html.fromstring(html)
    titles = doc.xpath('//h1[contains(concat(" ", normalize-space(@class), " "), " product_title ")]')
    if not titles:
        return []
    name = " ".join(titles[0].text_content().split())
    mains = [p for p in doc.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " price ")]')
             if not _in_loop(p) and p.tag in ("p", "span")]
    prices = {_price_of(p) for p in mains}
    if len(prices) != 1:
        return []
    row = price_row(name, prices.pop(), url, _CURRENCY)
    return [row] if row else []
