"""
Spider for Cdiscount -- https://www.cdiscount.com/, France's largest
general-merchandise online marketplace.

Briefed endpoint (bffmobilesite.cdiscount.com/carousel/navigation-history)
is exactly the "widget, not enumeration route" case the wave-3 addendum
warns about: it 405s on GET, then 400s on POST demanding a
`UniqueVisitContext` cookie AND an `X-CDS-Context-UniqueVisitId` header --
a personalization carousel, not a catalog route. Probing the BFF host's
other paths blind (`/search`, `/catalog/*`, `/product/*`) found nothing
usable without reverse-engineering the mobile app's private request
shapes, so this does NOT ship as a `scrapy_api` spider against that host.

The real enumerable surface is the web site's own keyword-search page,
https://www.cdiscount.com/search/<catId>/<keyword>.html?page=<n> -- but
reaching it needs a real browser: EVERY plain `curl` and `curl_cffi`
request to www.cdiscount.com (5 TLS-impersonation profiles tried:
chrome120/124/131/133a/safari17_0) gets an identical 14,057-byte
`__blnChallengeStore` (Baleen anti-bot vendor) + Cloudflare JS-challenge
shell, HTTP 200 -- a real JS-execution wall, not a TLS-fingerprint gate
(confirmed: byte-identical response body across every profile). A real
headless Chromium clears it in ~6s and the resulting cookie jar (chiefly
`visit_baleen_*`, `VisitContextCookie`, `UniqueVisitContext`,
`cf_clearance`, `__cf_bm`) replays cleanly on a plain `curl_cffi` /
Scrapy request afterward -- confirmed live 2026-09-10 by re-fetching the
same search URL with harvested cookies and no further TLS impersonation
tricks, getting the identical 200 + full listing HTML a real browser saw.
This is the exact "Playwright to discover, plain HTTP to scrape" pattern
already shipped in this repo for taw9eel_kw.py (AWS WAF `aws-waf-token`
case) -- same shape, different vendor (Baleen/Cloudflare here vs AWS WAF
there). Playwright runs exactly ONCE per crawl, in `start()`, to mint the
cookie jar; every search-results page after that is a bare
`scrapy.Request` carrying that cookie jar. No Playwright request is made
per-item or per-page.

Listing pages are styled-components React SSR (no `__NEXT_DATA__`/JSON
blob to read -- checked and absent) but the product grid IS present in
the raw HTML behind stable `data-e2e` attributes rather than the
hashed `sc-xxxxx` classes: each card is `<a href="...f-<catid>-<sku>
.html#..."><article data-e2e="offer-item">...<h2 data-e2e="lplr-title">
name</h2>...<div data-e2e="lplr-price">...<span>NN,NN €</span></div>`.

Enumerability confirmed live 2026-09-10 on keyword "chaussures"
(catId=10): page 1 (no query) vs `?page=2` -- 47 distinct product cards
extracted per page via regex, ZERO url overlap between the two sets
(comm -12 on the sorted url lists = 0). The site reports "248 406
produits" for this one keyword alone; Cdiscount overall is a
many-million-SKU marketplace. `?p=2` / `?pageNumber=2` are NOT the real
param (both silently re-serve page 1) -- only `?page=N` advances.

Category comes from the product's OWN url path segments before the
`/f-<catid>-<sku>.html` suffix (e.g. "chaussures/basket/..." ->
"chaussures > basket") -- more accurate than the search keyword itself,
since a keyword like "chaussures" pulls genuinely cross-category hits
(a shoe rack under "maison/meubles-mobilier" turned up in the "chaussures"
results, confirmed live). Price is "NN,NN €" (comma decimal, space then
euro sign); comma->dot normalized, symbol stripped. Currency hardcoded
EUR (France).

10 keyword seeds chosen to span the marketplace's own top-nav
departments (verified live each returns a real, differently-sized result
count 2026-09-10: chaussures=248406, informatique=23750, epicerie=10268,
jouets=32484, aspirateur=14162 among those spot-checked) -- this is a
discovery seed list for a general marketplace, not an attempt at
exhaustive coverage; coicop_classification stays `classifier` and
coicop_codes is left unset accordingly (channel: marketplace, matches
Cdiscount's own model -- every priced card observed is fulfilled by a
named third-party marketplace offer, same convention as auchan_fr in
this same batch).

CAVEAT: the Baleen challenge cookie the addendum's own probe methodology
observed carries a 900s (15 min) `maxAge` on its own cookie header. A
crawl seeded across 10 keywords x many pages could in principle outlast
that window on a slow run; this spider does not re-bootstrap mid-crawl
(same limitation taw9eel_kw accepted). MAX_PAGES_PER_KEYWORD is kept
modest (15) to keep a full run well inside that budget; a future
maintainer who wants deeper pagination should re-bootstrap periodically
rather than raise the cap alone.
"""

from __future__ import annotations

import html as ihtml
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HOME = "https://www.cdiscount.com/"

# Discovery seed keywords spanning several top-nav departments (verified
# live 2026-09-10, each a real, distinctly-sized result set).
_KEYWORDS = [
    "chaussures",
    "epicerie",
    "informatique",
    "jouets",
    "aspirateur",
    "meuble",
    "bricolage",
    "puericulture",
    "sport",
    "vins",
]
MAX_PAGES_PER_KEYWORD = 15

_CARD_RE = re.compile(
    r'<a href="(//www\.cdiscount\.com/([^"]+)\.html[^"]*)"[^>]*>.*?'
    r'<h2[^>]*data-e2e="lplr-title"[^>]*>(.*?)</h2>.*?'
    r'data-e2e="lplr-price"[^>]*>.*?<span[^>]*>([\d,]+)\s*€</span>',
    re.S,
)
_SKU_RE = re.compile(r"/f-\d+-([a-z0-9]+)$", re.I)


def _clean_price(raw: str) -> str | None:
    try:
        return str(float(raw.replace(",", ".")))
    except ValueError:
        return None


class CdiscountFrSpider(scrapy.Spider):
    name = "cdiscount_fr"
    allowed_domains = ["cdiscount.com", "www.cdiscount.com"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": _DESKTOP_UA,
    }

    async def start(self):
        cookies = await self._bootstrap()
        if not cookies.get("cf_clearance") and not cookies.get("visit_baleen_ACM-655d43"):
            logger.warning(
                "cdiscount_fr: no Baleen/Cloudflare clearance cookie minted -- "
                "subsequent requests will likely be re-challenged"
            )
        self._cookies = cookies
        for kw in _KEYWORDS:
            yield scrapy.Request(
                f"https://www.cdiscount.com/search/10/{kw}.html",
                cookies=self._cookies,
                callback=self.parse_listing,
                meta={"keyword": kw, "page": 1},
                dont_filter=True,
            )

    async def _bootstrap(self):
        """Run a real headless Chromium once to clear the Baleen/Cloudflare
        JS challenge and harvest the resulting cookie jar. Uses playwright's
        async API so it runs inside Scrapy's own asyncio reactor loop rather
        than spinning a second, conflicting event loop."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=_DESKTOP_UA, locale="fr-FR")
                await page.goto(_HOME, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(6000)
                cookies = await page.context.cookies()
            finally:
                await browser.close()
        return {c["name"]: c["value"] for c in cookies if "cdiscount" in c["domain"]}

    def parse_listing(self, response):
        if response.status != 200:
            logger.warning(f"cdiscount_fr: status={response.status} at {response.url}")
            return

        body = response.text
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        n = 0
        for m in _CARD_RE.finditer(body):
            href, path, name_html, price_raw = m.groups()
            price = _clean_price(price_raw)
            name = ihtml.unescape(re.sub(r"<[^>]+>", "", name_html)).strip()
            if not price or not name:
                continue

            url = "https:" + href.split("#", 1)[0]
            # path looks like "<cat>/<subcat>/<slug>/f-<catid>-<sku>"
            product_id = None
            if "/f-" in path:
                id_m = _SKU_RE.search("/f-" + path.rsplit("/f-", 1)[-1])
                if id_m:
                    product_id = id_m.group(1)
            category = None
            if "/f-" in path:
                cat_segments = path.rsplit("/f-", 1)[0].split("/")[:-1]
                if cat_segments:
                    category = " > ".join(cat_segments)

            n += 1
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"cdiscount_fr: keyword={keyword} page={page} rows={n}")

        if n and page < MAX_PAGES_PER_KEYWORD:
            yield scrapy.Request(
                f"https://www.cdiscount.com/search/10/{keyword}.html?page={page + 1}",
                cookies=self._cookies,
                callback=self.parse_listing,
                meta={"keyword": keyword, "page": page + 1},
                dont_filter=True,
            )
