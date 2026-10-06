"""Per-source extractor for archived waltons_im (waltons.im) captures.

Single-product pages under ``/product/<slug>/`` (2020-2024) are WooCommerce
rendered through an Elementor template (OceanWP theme from late 2021). The
product's own price appears once in the Elementor ``woocommerce-product-price``
widget and, from 2021, a second time in an OceanWP ``div.product_price`` copy;
below it a related/upsell grid reuses the same ``.price`` markup::

    <h1 class="product_title entry-title ...">SONOS RAY SOUNDBAR, BLACK</h1>
    <p class="price">
      <del aria-hidden="true"><span class="woocommerce-Price-amount amount">&pound;279.00</span></del>
      <ins><span class="woocommerce-Price-amount amount">&pound;264.00</span></ins>
    </p>

Grid items sit inside loop containers (``ul.products``, ``li.product``,
``woocommerce-LoopProduct-link``, ``product-inner``), so every ``.price`` with
such an ancestor is ignored. Of what remains, the struck-through ``<del>``
figure and screen-reader text are dropped and the single remaining amount is
the current price; all main-price copies must agree.

Abstains on: price ranges (variable products), empty price blocks, any extra
wording around the figure (``From``, ``per``), copies that disagree, and pages
without a ``product_title`` heading (e.g. Cloudflare/blank captures).
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
