"""Per-source extractor for archived systembolaget_se (systembolaget.se) captures.

systembolaget_se resolved 302,432 captures and parsed none: the site carries no
JSON-LD, no microdata and no product OpenGraph tag in any era. It does embed a
full product record on every product page, in one of two places depending on
when the capture was taken, and neither is where the portable tiers look.

**2020-2022** -- server-rendered React, the record hung off a container's
``data-props`` attribute as HTML-escaped JSON::

    <div data-react-component="ProductDetailPageContainer"
         data-props='{"product":{"productNameBold":"Aldea",
                      "productNameThin":"White","priceInclVat":50.00,
                      "comparisonPrice":66.67,"volume":750.0, ...}}'>

**2023 onward** -- Next.js, the record in the SWR cache under
``props.pageProps.fallback``, keyed by a serialised request tuple rather than a
plain name, which is why the shared ``__NEXT_DATA__`` tier abstains::

    '@"api","ecommerce","product","3128415",': {"priceInclVat": 28.9, ...}

Several ``data-props`` containers sit on the same page (a layout provider, a
header) and the SWR cache also holds ``"cms"`` records for site chrome. Rather
than matching container names or key shapes across two redesigns, both paths
use the same discriminator: a record carrying a numeric ``priceInclVat`` is a
product record, and nothing else on the page has that field.

``priceInclVat`` is the shelf price. The two figures beside it are deliberately
not read:

* ``comparisonPrice`` is the per-litre reference price Swedish law requires.
  On the 2021 record above it is 66.67 against a 50.00 shelf price for a 750 ml
  bottle, and on a 250 ml capture 79.60 against 20.90 -- reading it would
  overstate an observation up to fourfold. It is *larger* than the real price,
  so no plausibility bound would catch the substitution.
* ``priceInclVatExclRecycleFee`` excludes the container deposit. The charged
  price includes it, so the inclusive figure is the comparable one.

The name is the site's own two-part split -- a bold lead and a thin tail that
render as one line -- rejoined with a space. Sweden prices in SEK throughout.
"""

from __future__ import annotations

import json
from typing import Any

from archived import price_row

_CURRENCY = "SEK"


def _loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _records(doc: Any) -> list:
    """Every JSON object on the page that might hold the product record."""
    out = []
    for el in doc.iter():
        if el.tag == "script" and el.get("id") == "__NEXT_DATA__":
            data = _loads(el.text_content())
            fallback = (((data or {}).get("props") or {}).get("pageProps") or {}).get("fallback")
            if isinstance(fallback, dict):
                out.extend(v for v in fallback.values() if isinstance(v, dict))
        props = el.get("data-props")
        if props:
            # lxml has already un-escaped the attribute value.
            data = _loads(props)
            if isinstance(data, dict):
                out.append(data)
                product = data.get("product")
                if isinstance(product, dict):
                    out.append(product)
    return out


def extract(doc: Any, url: str) -> dict | None:
    """The shelf price on an archived systembolaget product page, or nothing."""
    for rec in _records(doc):
        price = rec.get("priceInclVat")
        if not isinstance(price, (int, float)):
            continue
        name = " ".join(
            part for part in (rec.get("productNameBold"), rec.get("productNameThin"))
            if isinstance(part, str) and part.strip()
        ).strip()
        row = price_row(name or None, ("%.4f" % price).rstrip("0").rstrip("."),
                        url, _CURRENCY)
        if row:
            return row
    return None
