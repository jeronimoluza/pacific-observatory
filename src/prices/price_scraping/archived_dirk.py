"""Per-source extractor for archived dirk_nl (dirk.nl) captures.

dirk_nl resolved 138,015 captures and parsed none. From the 2024 redesign the
product page is server-rendered and does carry its price -- but split across
two sibling spans, with the decimal point supplied by CSS rather than by any
text node::

    <div class="price">
      <span class="hasEuros price-large">4</span>
      <span class="price-small">99</span>
    </div>

    .price-container .price .price-large.hasEuros:after { content: "." }

That is why every portable tier abstains and why a currency regex over the
rendered text finds nothing: there is no "4.99" anywhere in the document. The
euros and cents are rejoined here, and the ``hasEuros`` marker class is what
says the large span is a euro count rather than a whole-euro price with no
minor part.

The page also ships a JSON-LD ``Product`` block from 2022 onward, which is why
this source looks like it should already parse -- but that block carries no
``offers`` at all, so the shared tier correctly declines it. The name is taken
from the page's ``h1``, which names the page's own product; the split-price
markup is not repeated for the related-products rail below it in any sampled
capture, and more than one occurrence abstains rather than guessing which tile
belongs to the page.

Pre-2024 captures carry neither the split spans nor any other price surface
and simply abstain. The Netherlands prices in euro throughout.
"""

from __future__ import annotations

from typing import Any

from archived import price_row

_CURRENCY = "EUR"


def _classes(el: Any) -> set[str]:
    return set((el.get("class") or "").split())


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def extract(doc: Any, url: str) -> dict | None:
    """The rejoined split price on an archived dirk product page, or nothing."""
    larges = [el for el in doc.iter("span") if "price-large" in _classes(el)]
    if len(larges) != 1:
        return None
    large = larges[0]
    euros = _text(large)
    if not euros.isdigit():
        return None
    cents = ""
    for sib in large.itersiblings("span"):
        if "price-small" in _classes(sib):
            cents = _text(sib)
            break
    if not cents.isdigit():
        return None
    name = ""
    for h1 in doc.iter("h1"):
        name = _text(h1)
        if name:
            break
    return price_row(name or None, "%s.%s" % (euros, cents), url, _CURRENCY)
