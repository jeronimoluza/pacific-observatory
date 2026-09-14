"""WooCommerce storefronts whose price only exists as rendered theme markup.

WooCommerce writes the price into a stable, plugin-owned wrapper that survives
every theme, and names the currency inside it::

    <p class="price">
      <span class="woocommerce-Price-amount amount">
        <bdi>114 000<span class="woocommerce-Price-currencySymbol">XPF</span></bdi>
      </span>
      <small class="woocommerce-price-suffix">TTC</small>
    </p>

The symbol span sits *inside* the amount, so the element's whole text reads
"114 000XPF" and a plain number regex over it picks up nothing useful. The
symbol's own text is removed before the figure is read rather than trimmed by
position, because themes put it on either side.

**Picking the page's own product is the whole problem here.** A full product
page on these shops renders eighteen amounts: a mini-cart total, the product's
own price, and a rail of related-product tiles each with its own. Taking the
first would bank the cart total, and taking any later one would bank a
neighbouring product's price against this page's URL. Two surfaces identify the
page's own product, tried in order:

* ``div.single-price-wrapper[data-product_id]`` -- what the Elementor-based
  themes wrap the single product's price in. Present exactly once on every
  sampled full page, while the cart total and the related tiles are outside it.
* an element classed ``product_title`` -- the classic WooCommerce single-product
  title, after which the first amount is the product's own.

A shop whose captures carry neither abstains. Likewise the name: the
``product_title`` element when there is one, otherwise the document title with
its trailing " - <shop>" segment removed, because the Elementor themes reuse
``h1`` for section banners ("MOBILIER D'EXTERIEUR") rather than for the
product.

A sale price renders as two amounts inside one ``<p class="price">``, the
original wrapped in ``<del>`` and the current in ``<ins>``. Any amount with a
``del`` ancestor is skipped so the struck-through figure is never banked.

The currency symbol is mapped only where it is unambiguous; a shop printing a
bare "$" abstains rather than guessing between a dozen dollars.
"""

from __future__ import annotations

import re
from typing import Any

from archived import normalize_price, price_row

# Only symbols with one plausible reading. A bare "$" or "kr" is deliberately
# absent: guessing the country from it is how a Namibian price becomes a US one.
_SYMBOLS = {
    "XPF": "XPF", "CFP": "XPF",
    "NAD": "NAD", "N$": "NAD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "PKR": "PKR", "RS": "PKR", "₨": "PKR",
    "MYR": "MYR", "RM": "MYR",
    "ZAR": "ZAR",
}
_NUM = re.compile(r"\d[\d\s.,  ]*\d|\d")
_TITLE_TAIL = re.compile(r"\s*[|–—-]\s*[^|–—-]+$")


def _classes(el: Any) -> set[str]:
    return set((el.get("class") or "").split())


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _has_del_ancestor(el: Any, stop: Any = None) -> bool:
    node = el.getparent()
    while node is not None and node is not stop:
        if node.tag == "del":
            return True
        node = node.getparent()
    return False


def _amount_row(amount: Any, name: str, url: str) -> dict | None:
    symbol = ""
    for child in amount.iter():
        if "woocommerce-Price-currencySymbol" in _classes(child):
            symbol = _text(child)
            break
    currency = _SYMBOLS.get(symbol) or _SYMBOLS.get(symbol.upper())
    if not currency:
        return None
    figure = _text(amount)
    if symbol:
        figure = figure.replace(symbol, " ")
    m = _NUM.search(figure)
    if not m:
        return None
    raw = re.sub(r"[\s  ]", "", m.group(0))
    return price_row(name, normalize_price(raw, currency), url, currency)


def _amounts_under(root: Any) -> list:
    return [el for el in root.iter() if "woocommerce-Price-amount" in _classes(el)]


def _name(doc: Any) -> str:
    for el in doc.iter():
        if "product_title" in _classes(el):
            text = _text(el)
            if text:
                return text
    for el in doc.iter("title"):
        text = _text(el)
        if text:
            return _TITLE_TAIL.sub("", text).strip() or text
    return ""


def extract(doc: Any, url: str) -> dict | None:
    """The charged price on an archived WooCommerce product page, or nothing."""
    name = _name(doc)
    if not name:
        return None

    wrappers = [el for el in doc.iter() if "single-price-wrapper" in _classes(el)]
    if len(wrappers) == 1:
        for amount in _amounts_under(wrappers[0]):
            if _has_del_ancestor(amount, wrappers[0]):
                continue
            row = _amount_row(amount, name, url)
            if row:
                return row

    title_el = None
    for el in doc.iter():
        if "product_title" in _classes(el):
            title_el = el
            break
    if title_el is None:
        return None
    seen = False
    for el in doc.iter():
        if el is title_el:
            seen = True
            continue
        if not seen or "woocommerce-Price-amount" not in _classes(el):
            continue
        if _has_del_ancestor(el):
            continue
        row = _amount_row(el, name, url)
        if row:
            return row
    return None
