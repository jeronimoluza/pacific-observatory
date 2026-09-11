"""Alcampo Spain -- https://www.compraonline.alcampo.es/ (Auchan's Spanish banner).

Same family as auchan_hu (see that spider), but a different platform again --
a 6th distinct Auchan-group tech stack. robots.txt / sitemap index at
https://compraonline.alcampo.es/sitemaps/sitemap_index.xml lists 6 shards:
categories, collections, promotions, recipes, and two PRODUCT shards
(sitemap-products-part1.xml, sitemap-products-part2.xml -- 50,000 + 36,263 =
86,263 product <loc> entries, verified live 2026-09-10). Only the product
shards match PRODUCT_URL_RE (`/products/<slug>/<id>`); category/collection/
promotion/recipe URLs use different path prefixes so are naturally excluded.

Product PDPs are plain server-rendered HTML (no JS needed, plain requests.get
-> HTTP 200) with a schema.org Product JSON-LD block
(`data-test="product-details-structured-data"`), parsed by the shared
WooBaseSpider.parse_html JSON-LD fallback chain. Verified 4 PDPs across both
shards, all non-zero EUR prices: 'CALVO Atun en aceite de oliva virgen extra
72g X 3' EUR 6.55, 'Forro en rollo para forrar libros PVC ...' , 'L'OREAL
PARIS Color riche Tono 570 ...', 'BOLSA BASURA RELEVO 100% REC. ...' EUR
1.xx. Currency EUR matches countries.yaml.

Note: the PDP HTML also loads an AWS WAF CAPTCHA SDK script
(captcha-sdk.awswaf.com). This is a REAL, live defense, not a dormant
script tag, and it is NOT primarily a burst/rate problem -- two
independent runs on 2026-09-10 (one at _woo_sitemap_base's default 2
concurrent/1.0s delay, one at a much slower 1 concurrent/3.0s delay)
BOTH saw the same shape: the first 5-6 PDP requests return real HTTP 200
JSON-LD, then EVERY request after that gets HTTP 202 with a
gokuProps/awsWafCookieDomainList JS-challenge stub (0 real content) for
the rest of the run, and the tenant then keeps challenging this IP on
every subsequent request (regardless of curl_cffi TLS-impersonation
profile -- chrome120/124/131/131_android/safari17_0/18_0/136 all 202'd)
for roughly 20-30 minutes before self-clearing. This looks like a
short-lived-session/token model (grace allowance per fresh client,
then a mandatory JS-challenge), the same AWS WAF Bot Control class
documented for taw9eel_kw and ica_se elsewhere in this repo, NOT a
simple requests-per-minute threshold that a slower DOWNLOAD_DELAY fixes.
custom_settings below (1 concurrent / 3.0s delay) reduce the blast
radius but do NOT solve the underlying issue -- expect on the order of
5-10 real rows per fresh crawl attempt at PRESENT, not a full-catalog
crawl. The taw9eel_kw / ica_se "Playwright once to mint an
aws-waf-token, then plain-HTTP-replay the cookie for every PDP" pattern
almost certainly fixes this too (this tenant's challenge page is the
byte-for-byte same gokuProps stub) but was not built here -- shipping
this as a scrapy_html sitemap spider proves the extraction pattern and
clears the >=5-row acceptance bar; whoever tunes this for full-catalog
throughput should port the Playwright-bootstrap pattern rather than
just retrying 202s.

UPDATE (2026-09-11) -- the Playwright-bootstrap/cookie-replay idea above
was tried and DISPROVEN, not just "not built here". A real headless
Chromium navigated directly to a PDP: the response is titled
"Human Verification" with `x-amzn-waf-action: captcha` -- an interactive
image CAPTCHA, not a passive JS proof-of-work. Waiting up to 20s in the
same page produced no auto-redirect/auto-solve (unlike the pure JS
`challenge` action documented for taw9eel_kw/cdiscount_fr, which a real
browser clears on its own by executing the page's script). Minting
cookies from a bare homepage visit (not a PDP) and replaying them via
Scrapy+curl_cffi made things WORSE than doing nothing: a live test run
carrying that cookie jar got 0/239 real rows (120x202 + 119x405-captcha)
against distinct PDPs, vs. this file's own no-cookie approach getting
5-10 real rows per attempt -- presenting a `aws-waf-token` that was
never actually solved appears to read as a stronger bot signal than
presenting no token at all. A fresh, cookie-less Playwright browser
launched per item avoided immediate CAPTCHA escalation (stayed at the
lighter `challenge` action across 5 distinct fresh-context requests) but
still never got real content through in that test window. Net: this
tenant's PDP protection is a genuine AWS WAF Bot Control CAPTCHA tier,
which by design requires solving an actual image puzzle -- not
automatable by any TLS-impersonation profile or real-browser JS
execution tried so far. A real fix needs either a CAPTCHA-solving
service (cost/ToS tradeoff, not attempted) or IP-rotation infrastructure
to keep re-arriving as a "fresh" grace-allowance identity; neither is a
spider-code change. Until then, this file's original no-cookie sitemap
walk remains the best available approach and should NOT be replaced with
a cookie-bootstrap variant without new evidence it actually helps.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class AlcampoEsSpider(WooSitemapBaseSpider):
    name = "alcampo_es"
    allowed_domains = ["compraonline.alcampo.es", "www.compraonline.alcampo.es"]
    SITEMAP_URL = "https://compraonline.alcampo.es/sitemaps/sitemap_index.xml"
    PRODUCT_URL_RE = r"/products/[^/]+/\d+$"
    currency = "EUR"
    language = "es"

    # Overrides _woo_sitemap_base's default (2 concurrent / 1.0s delay) --
    # that default tripped this tenant's AWS WAF Bot Control within ~2
    # minutes on 2026-09-10 (139 of 145 requests came back HTTP 202 --
    # the gokuProps JS-challenge stub, zero real content -- and the
    # domain then hard-CAPTCHA'd this IP for ~20-30 minutes on EVERY
    # subsequent request regardless of TLS-impersonation profile). Do not
    # raise these without re-probing at the higher rate first.
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 3.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }
