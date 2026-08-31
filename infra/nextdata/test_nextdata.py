"""Invariants for the __NEXT_DATA__ tier and the two extractors added with it.

Each case is pinned to a defect that was actually measured on the archived
miss corpus while this code was being written, not to a hypothetical. The
minor-units and generic-key cases are the point: both scored perfectly clean
before anyone read the samples.
"""
import json
import sys

sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")

import lxml.html  # noqa: E402

from prices.price_scraping.archived_emart import extract as emart  # noqa: E402
from prices.price_scraping.archived_nextdata import (  # noqa: E402
    rows_from_nextdata,
)
from prices.price_scraping.archived_yahoo_tw import (  # noqa: E402
    extract as yahoo_tw,
)

URL = "http://shop.example/p/1"
CASES = []


def case(name, fn, check):
    CASES.append((name, fn, check))


def blob(payload, body=""):
    return ('<html><body>%s<script id="__NEXT_DATA__" type="application/json">'
            "%s</script></body></html>" % (body, json.dumps(payload)))


def nd(payload, body=""):
    rows = rows_from_nextdata(blob(payload, body), URL)
    return rows[0] if rows else None


case(
    "product anywhere in the tree is found",
    lambda: nd({"props": {"pageProps": {"product": {
        "name": "Arroz 1kg", "price": 2500}}}}),
    lambda r: r and r["product_name"] == "Arroz 1kg" and r["price"] == "2500.0",
)

# prisma.fi publishes finalPrice 2000 for a book the page renders as 20,00 EUR.
# Banking the payload as written is a 100x error on every row of that shape.
case(
    "minor units are rescaled to what the page renders",
    lambda: nd({"props": {"pageProps": {"product": {
        "productName": "Hulluuden historia", "finalPrice": 2000}}}},
        body="<span>20,00 &euro;</span>"),
    lambda r: r and r["price"] == "20.0",
)

# The same payload with no rendered price has nothing to argue for rescaling,
# and liverpool.com.mx is exactly that: the payload is the only evidence there
# is, because the page never renders the price at all.
case(
    "with no rendered price the payload stands as written",
    lambda: nd({"query": {"data": {"mainContent": {"records": [
        {"allMeta": {"title": "Chal Pineda Covalin",
                     "minimumPromoPrice": "7939"}}]}}}}),
    lambda r: r and r["price"] == "7939.0",
)

# `value` and `amount` are what a payload calls anything at all: an earlier
# revision banked "Size (g)" at 100.0 and "Alto" at 40.0 as prices.
case(
    "a specification attribute is not a price",
    lambda: nd({"props": {"pageProps": {"specs": [
        {"name": "Size (g)", "value": 100}]}}}),
    lambda r: r is None,
)

# agrofy.com.ar carries 11 unrelated cars under merchantRelatedProducts.
# Attributing them to this URL writes a series that moves when the rail does.
case(
    "a recommendation rail is not this page's product",
    lambda: nd({"props": {"pageProps": {
        "merchantRelatedProducts": {"Hits": [
            {"name": "Otro auto", "price": 33200000}]}}}}),
    lambda r: r is None,
)

case(
    "a config flag whose name is an identifier is not a product",
    lambda: nd({"props": {"global": {"shipping": {
        "name": "scheduledEnabled", "price": 1}}}}),
    lambda r: r is None,
)

# A one-decimal money token sliced by offset produced the string "..6" and
# raised straight out of the tier, which stops the driver rather than
# abstaining. Found by the fetch-driver test, not by any of the cases above.
case(
    "a one-decimal rendered price does not raise",
    lambda: nd({"props": {"pageProps": {"product": {
        "name": "Something", "price": 6.6}}}},
        body="<span>$6.6</span>"),
    lambda r: r and r["price"] == "6.6",
)

case(
    "a thousands-separated rendered price corroborates at scale 1",
    lambda: nd({"props": {"pageProps": {"product": {
        "name": "Bolsa", "price": 2412}}}},
        body="<span>$2,412</span>"),
    lambda r: r and r["price"] == "2412.0",
)

case(
    "no blob at all is not an error",
    lambda: rows_from_nextdata("<html><body>nothing</body></html>", URL),
    lambda r: r == [],
)

case(
    "unparseable blob is not an error",
    lambda: rows_from_nextdata(
        '<script id="__NEXT_DATA__">{not json</script>', URL),
    lambda r: r == [],
)


def doc(html):
    return lxml.html.fromstring(html)


# emart's cdtl_price is a bank-card conditional price -- 0.92x and 0.95x of the
# 최적가 the page actually charges, unlocked only by holding a given card.
case(
    "emart reads 최적가, not the card-conditional price",
    lambda: emart(doc(
        '<html><head><title>상품명 - 이마트몰, '
        '당신과</title></head><body>'
        '<div class="cdtl_optprice"><span class="cdtl_new_price">'
        '최적가 59,800 원</span></div>'
        '<div class="cdtl_card_price"><dl class="cdtl_dl"><dd>'
        '<span class="cdtl_price">55,016원</span></dd></dl></div>'
        "</body></html>"), URL),
    lambda r: r and r["price"] == "59800.0" and r["currency"] == "KRW"
    and r["product_name"] == "상품명",
)

case(
    "emart abstains when no 최적가 is present",
    lambda: emart(doc(
        '<html><body><div class="cdtl_card_price">'
        '<span class="cdtl_price">55,016원</span></div></body></html>'),
        URL),
    lambda r: r is None,
)

# The legacy yahoo_tw template prints 建議售價 (suggested retail) in class
# `price` and the charged figure in `.priceinfo`; reading `price` banks a list
# price on every row.
case(
    "yahoo_tw legacy reads the charged price, not 建議售價",
    lambda: yahoo_tw(doc(
        '<html><head><title>包包 - Yahoo!奇摩購物'
        '中心</title></head><body>'
        '<span class="price">$2,680</span>'
        '<div class="priceinfo">$2,412</div>'
        '<span class="num rprice">402</span></body></html>'), URL),
    lambda r: r and r["price"] == "2412.0" and r["currency"] == "TWD"
    and r["product_name"] == "包包",
)

case(
    "yahoo_tw 2019 reads mainPrice whatever the build hash is",
    lambda: yahoo_tw(doc(
        '<html><head><title>x - Yahoo</title></head><body>'
        '<h1 class="HeroInfo__title___ZZZZZ">垃圾桶</h1>'
        '<div class="HeroInfo__mainPrice___QQQQQ">$1,095</div>'
        "</body></html>"), URL),
    lambda r: r and r["price"] == "1095.0"
    and r["product_name"] == "垃圾桶",
)


def main():
    failed = 0
    for name, fn, check in CASES:
        try:
            got = fn()
            ok = check(got)
        except Exception as exc:  # a raising tier is a failing tier
            got, ok = "raised: %r" % exc, False
        if not ok:
            failed += 1
            print("FAIL  %s\n        got %r" % (name, got))
    print("%d cases, %d failed" % (len(CASES), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
