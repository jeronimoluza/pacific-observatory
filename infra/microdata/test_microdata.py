"""Invariants for the microdata tier, pinned to the defects that motivated it.

The scoping cases are the point. Both were measured on the archived miss
corpus with the naive "first itemprop=name under the Product" rule -- otto_de
named 86% of its rows `variationId`, ebay_uk took a breadcrumb 59% of the
time -- and both are what the nearest-ancestor-itemscope rule exists to stop.
"""
import sys

sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")

from prices.price_scraping.archived_microdata import (  # noqa: E402
    rows_from_microdata,
)

P = 'itemscope itemtype="http://schema.org/Product"'
OFFER = 'itemscope itemtype="http://schema.org/Offer"'
URL = "http://shop.example/p/1"


def one(html, url=URL):
    rows = rows_from_microdata(html, url)
    return rows[0] if rows else None


CASES = []


def case(name, html, check):
    CASES.append((name, html, check))


case(
    "plain product",
    '<div %s><span itemprop="name">Arroz 1kg</span>'
    '<span itemprop="price">2500</span>'
    '<meta itemprop="priceCurrency" content="CLP"></div>' % P,
    lambda r: r and r["product_name"] == "Arroz 1kg" and r["price"] == "2500.0",
)

case(
    "price on nested Offer is still this product's",
    '<div %s><span itemprop="name">Aceite</span>'
    '<div %s><span itemprop="price">3990</span></div></div>' % (P, OFFER),
    lambda r: r and r["price"] == "3990.0",
)

# --- the two measured name defects -------------------------------------------

case(
    "breadcrumb name is not the product name (ebay_uk, was 59%)",
    '<div %s>'
    '<div itemscope itemtype="http://schema.org/BreadcrumbList">'
    '<span itemprop="name">Sound &amp; Vision</span></div>'
    '<h1 itemprop="name">Amity Bike Co Zenta BMX</h1>'
    '<span itemprop="price">120</span></div>' % P,
    lambda r: r and r["product_name"] == "Amity Bike Co Zenta BMX",
)

case(
    "PropertyValue name is not the product name (otto_de, was 86%)",
    '<div %s>'
    '<div itemscope itemtype="http://schema.org/PropertyValue">'
    '<meta itemprop="name" content="variationId"></div>'
    '<h1 itemprop="name">Phoenix Datenschutzschrank</h1>'
    '<span itemprop="price">499</span></div>' % P,
    lambda r: r and r["product_name"] == "Phoenix Datenschutzschrank",
)

case(
    "a product with only a nested name yields nothing, never a wrong name",
    '<div %s>'
    '<div itemscope itemtype="http://schema.org/Brand">'
    '<span itemprop="name">Nestle</span></div>'
    '<span itemprop="price">100</span></div>' % P,
    lambda r: r is None,
)

# --- price shape --------------------------------------------------------------

case(
    "dot-thousands in a zero-decimal currency is not a decimal point",
    '<div %s><span itemprop="name">Cafe</span>'
    '<span itemprop="price">12.500</span>'
    '<meta itemprop="priceCurrency" content="CLP"></div>' % P,
    lambda r: r and r["price"] == "12500.0",
)

case(
    "the same shape in a two-decimal currency stays a decimal point",
    '<div %s><span itemprop="name">Cafe</span>'
    '<span itemprop="price">12.500</span>'
    '<meta itemprop="priceCurrency" content="EUR"></div>' % P,
    lambda r: r and r["price"] == "12.5",
)

case(
    "zero price is not an observation",
    '<div %s><span itemprop="name">Cafe</span>'
    '<span itemprop="price">0</span></div>' % P,
    lambda r: r is None,
)

case(
    "content attribute beats element text",
    '<div %s><span itemprop="name">Te</span>'
    '<span itemprop="price" content="1999">$19.99 con descuento</span></div>' % P,
    lambda r: r and r["price"] == "1999.0",
)

# --- structure ----------------------------------------------------------------

case(
    "a recommendation rail does not become a price point",
    '<div %s><span itemprop="name">Main Item</span>'
    '<link itemprop="url" href="%s">'
    '<span itemprop="price">10</span></div>'
    '<div %s><span itemprop="name">Also Bought</span>'
    '<link itemprop="url" href="http://shop.example/p/999">'
    '<span itemprop="price">20</span></div>' % (P, URL, P),
    lambda r: r and r["product_name"] == "Main Item",
)

case(
    "a page with no microdata costs nothing and yields nothing",
    "<html><body><p>no markup here</p></body></html>",
    lambda r: r is None,
)

case(
    "a non-Product itemscope is not a product",
    '<div itemscope itemtype="http://schema.org/Organization">'
    '<span itemprop="name">Acme</span>'
    '<span itemprop="price">50</span></div>',
    lambda r: r is None,
)

case(
    "malformed html does not raise",
    '<div %s><span itemprop="name">Roto<span itemprop="price">7' % P,
    lambda r: r is None or r["price"] == "7.0",
)


def main():
    failed = 0
    for name, html, check in CASES:
        try:
            row = one(html)
            ok = check(row)
        except Exception as exc:  # a raising tier is a failing tier
            row, ok = "raised: %r" % exc, False
        if not ok:
            failed += 1
            print("FAIL  %s\n        got %r" % (name, row))
    print("%d cases, %d failed" % (len(CASES), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
