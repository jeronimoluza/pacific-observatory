"""Per-source extractor for archived frisco_pl (frisco.pl) captures.

frisco_pl is a Polish online grocery accounting for 106,460 misses. Every
capture in the 30-design-page sample is a single-product detail page
(``/pid,<id>/n,<slug>/stn,product``) -- confirmed by exactly one ``h1``
naming the item on all thirty -- yet the same page also renders a large
"you may also like" carousel of unrelated products below the fold, built out
of ``<article class="product-box-layout">`` tiles repeated up to 76 times.
Those tiles carry their own ``product-box-layout__price-*`` classes and were
the first candidate checked; picking one by matching the page's own ``pid``
back into a tile's link only worked for 20 of 30 captures; on the other 10
the page's own product is never rendered as one of its own carousel tiles at
all. That class family is not used here.

The class that is present on the page's own product on all 30 captures is
``new-product-page__prices_price``, appearing exactly once regardless of
whether the carousel below it holds four tiles or seventy-six. Where an
independent check was possible -- a ``schema.org/Offer`` microdata block also
present on some captures with its own ``itemProp="price"`` meta tag, which is
why the generic microdata tier already tried and failed to read this page --
the two agree exactly (33.99 on the one capture carrying both), which is why
the class is trusted here without needing the ``pid`` match this tier
originally reached for.

The Polish per-kg/per-litre reference price -- the same "cena za kg" trap
seen on edeka24_de -- sits on 26 of 30 captures as a sibling class,
``new-product-page__prices_unit-price``, one BEM segment over from the
charged price and never sharing its name. On ``frisco_pl__0be0b106edd40c30``
(FRISCO FRESH Mięso z udźca kurczaka, 440-660g) the shelf price is 15,99 zł
while the sibling unit price reads 29,07 zł/kg -- reading the wrong class
would have overstated this observation nearly twofold. The two classes are
matched by their exact, distinct full names, not by a shared prefix, so this
is a structural guarantee rather than one that happens to hold on this
sample.

Two shapes inside ``new-product-page__prices_price`` are read, and one is
deliberately not:

* A plain figure, or a markdown with the discounted price as the first
  ``<span class="price ...">`` child and the pre-discount price nested one
  level deeper inside a ``new-product-page__prices_secondary-price`` div --
  seen on 3 of the 22 priced design captures. Reading only the *direct*
  ``price_num``/``price_decimals`` children of that first span (never
  ``.iter()``, which would also pick up the nested secondary figure) is what
  keeps the struck-through original price out.
* A quantity-gated multi-buy deal (``product-box_price ... multibuy``) does
  not fall under the plain shape above -- its outer wrapper is a bare,
  unclassed ``<div>`` rather than a ``<span class="price ...">`` -- but it is
  still read, from its *second* nested price figure. Every one of six such
  captures checked (one in design, five held out) carries exactly two
  ``<span class="price ...">`` figures in the same order: the bulk deal
  first ("2 szt. za: 39,99 zł/szt.", "4 szt. za: 4,39 zł/szt." ...) and the
  plain, unconditional "1 szt. za:" price second, always the larger of the
  two. Reading that second figure is the same choice elvi_lv already makes
  for its "two-plus" variant -- the price one unit costs, never the
  quantity-discounted one -- and a wrapper carrying anything other than
  exactly two such figures abstains rather than guess which one that is.
* 7 of 30 design captures show ``0 gr`` -- confirmed against this tier's own
  independent microdata check to be ``schema.org/Discontinued`` stock, not a
  markup gap -- and are correctly read as no observation, since
  ``price_row`` rejects a non-positive price outright.

The product name comes from ``h1`` where one is present. Held out, older
captures (2019-2024, most of the corpus by volume) render no ``h1`` at all --
confirmed on 35 such captures -- but ``<title>`` always still reads
``<name> - Frisco.pl`` there, so the name falls back to the title with that
literal suffix stripped; a generic, non-product title (the one seen when
neither shape is present, ``Frisco.pl - supermarket online``) does not carry
the suffix and is correctly left unread.

A further, older 2018 template was checked and rejected: it prices the page's
own product under a different class altogether (``div.cart-box_price`` >
``span.main-price``), but every one of ten 2018 captures sampled read
``0,00 zł`` against an explicit "produkt wycofany" (product withdrawn)
notice, and 2018 is 1.1% of the corpus by volume (271 of 23,660 misses
sampled) -- adding a second price class for an era that produced zero
recoverable rows in measurement was not worth the added surface.
"""

from __future__ import annotations

from typing import Any

from .archived import normalize_price, price_row

_PRICE_WRAPPER = "new-product-page__prices_price"


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _direct_child_text(el: Any, cls: str) -> str | None:
    for child in el.iterchildren():
        if isinstance(child.tag, str) and cls in _classes(child):
            return _text(child)
    return None


def _price_span_text(span: Any) -> str | None:
    num = _direct_child_text(span, "price_num")
    if num is None:
        return None
    dec = _direct_child_text(span, "price_decimals")
    return f"{num},{dec}" if dec else num


def _multibuy_unit_price(wrapper: Any) -> str | None:
    """The plain, unconditional price inside a quantity-gated multi-buy deal.

    Exactly two ``<span class="price ...">`` figures appear in every such
    wrapper checked, always in the same order: the bulk deal first, the
    regular "1 szt. za:" price second. A wrapper carrying any other count
    abstains instead of guessing which figure is which.
    """
    multibuy = None
    for child in wrapper.iter():
        if isinstance(child.tag, str) and "multibuy" in _classes(child):
            multibuy = child
            break
    if multibuy is None:
        return None
    spans = [
        c for c in multibuy.iter()
        if isinstance(c.tag, str) and c.tag == "span" and "price" in _classes(c)
    ]
    if len(spans) != 2:
        return None
    return _price_span_text(spans[-1])


def _shelf_price(doc: Any) -> str | None:
    """The figure this page's own product is sold at, or nothing.

    Scopes to the one ``new-product-page__prices_price`` element and, inside
    it, to the first direct ``<span class="price ...">`` child. Reading only
    that span's direct ``price_num``/``price_decimals`` children (not every
    descendant) is what keeps a nested pre-discount ``secondary-price``
    figure from being counted. A multi-buy deal's outer wrapper is a bare
    ``<div>`` instead, so it falls through to ``_multibuy_unit_price``.
    """
    wrapper = None
    for el in doc.iter():
        if isinstance(el.tag, str) and _PRICE_WRAPPER in _classes(el):
            wrapper = el
            break
    if wrapper is None:
        return None
    span = None
    for child in wrapper.iterchildren():
        if isinstance(child.tag, str) and child.tag == "span" and "price" in _classes(child):
            span = child
            break
    if span is not None:
        raw = _price_span_text(span)
        return normalize_price(raw, "PLN") if raw else None
    raw = _multibuy_unit_price(wrapper)
    return normalize_price(raw, "PLN") if raw else None


_TITLE_SUFFIX = " - Frisco.pl"


def _name(doc: Any) -> str | None:
    """The product's own name, from ``h1`` or, failing that, the title.

    Older captures render no ``h1`` at all, but their ``<title>`` still reads
    ``<name> - Frisco.pl``; stripping that literal suffix recovers the name
    without risking the generic, suffix-less title a non-product page carries.
    """
    h1 = doc.find(".//h1")
    if h1 is not None:
        name = _text(h1)
        if name:
            return name
    title = doc.find(".//title")
    text = _text(title) if title is not None else ""
    if text.endswith(_TITLE_SUFFIX):
        return text[: -len(_TITLE_SUFFIX)]
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The price this frisco_pl product page's own price widget carries."""
    price = _shelf_price(doc)
    name = _name(doc)
    return price_row(name.strip() if name else None, price, url, "PLN")
