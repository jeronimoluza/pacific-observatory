import sys
sys.path.insert(0, "/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src")
from prices.cc_warc_fetcher import CommonCrawlScraper as S


class Stub:
    """Minimal stand-in so we can exercise the ladder without network/config."""
    _LDJSON_SPIDERS = S._LDJSON_SPIDERS
    _NEXTDATA_SPIDERS = S._NEXTDATA_SPIDERS
    spider_name = "test_shop"

    def __init__(self, hook=None, selectors=None):
        self.parse_html_fn = hook
        self.selectors = selectors or {}

    _generic_rows = S._generic_rows
    _parse_rows = S._parse_rows
    _extract_data_from_html = S._extract_data_from_html
    _extract_ldjson_fallback = S._extract_ldjson_fallback
    _extract_nextdata_fallback = S._extract_nextdata_fallback


LD = ('<script type="application/ld+json">'
      '{"@context":"https://schema.org","@type":"Product","name":"Widget",'
      '"offers":{"@type":"Offer","price":"12.50","priceCurrency":"EUR"}}</script>')
PAGE_LD = "<html><head>%s</head><body><h1>Widget</h1></body></html>" % LD
PAGE_BARE = "<html><head></head><body><h1>Widget</h1></body></html>"
PAGE_OLD = ("<html><head>%s</head><body>"
            "<span class='old-name'>Widget</span>"
            "<span class='old-price'>12.50</span></body></html>" % LD)
URL = "https://shop.example/p/1"


def show(label, rows):
    if not rows:
        print("%-52s MISS" % label)
        return False
    keep = {k: v for k, v in rows[0].items() if k in ("product_name", "price", "currency")}
    print("%-52s HIT  %s" % (label, keep))
    return True


print("== the bug: era-mismatched selectors on a page that HAS a standard block ==")
sel_wrong = {"product_name": ["span.new-name"], "price": ["span.new-price"]}
r1 = show("selectors do not match 2018 markup, page has block",
          Stub(selectors=sel_wrong)._parse_rows(PAGE_OLD, URL))

print("")
print("== half-match: name resolves, price class renamed ==")
sel_half = {"product_name": ["span.old-name"], "price": ["span.new-price"]}
r2 = show("selectors half-match, page has block",
          Stub(selectors=sel_half)._parse_rows(PAGE_OLD, URL))

print("")
print("== hook returns nothing on an old page ==")
r3 = show("hook yields [], page has block",
          Stub(hook=lambda h, u: [])._parse_rows(PAGE_LD, URL))

print("")
print("== no regression: things that already worked ==")
sel_ok = {"product_name": ["span.old-name"], "price": ["span.old-price"]}
r4 = show("selectors match -> selector row wins",
          Stub(selectors=sel_ok)._parse_rows(PAGE_OLD, URL))
r5 = show("hook works -> hook row wins",
          Stub(hook=lambda h, u: [{"product_name": "H", "price": "9.99"}])._parse_rows(PAGE_LD, URL))
r6 = show("no hook, no selectors, block present (old path)",
          Stub()._parse_rows(PAGE_LD, URL))
r7 = not Stub(selectors=sel_wrong)._parse_rows(PAGE_BARE, URL)
print("%-52s %s" % ("genuinely unparseable page still returns nothing", "OK" if r7 else "FAIL"))

ok = all([r1, r2, r3, r4, r5, r6, r7])
print("")
print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
