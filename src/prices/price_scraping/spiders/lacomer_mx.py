"""La Comer / Comercial Mexicana (Mexico) -- https://www.lacomer.com.mx/.

Full-line supermarket group (La Comer, Comercial Mexicana banners) covering
groceries, fresh produce, dairy, meat, and household goods. The storefront
itself is a legacy AngularJS 1.x SPA (client-side ui-router, hash routes
like `#!/detarticulo/...` -- confirmed via the site's own sitemap.xml,
which lists only `#!/pasillos/...` fragment URLs, i.e. there is no
server-rendered product page for any product on this domain).

Product search/listing is delegated to a third-party search vendor
(Amarello/"Buscador"), whose base path is exposed as an Angular constant
in /lacomer/js/ng-config.js:

    _AMARELLO_DOMAIN_PATH = "https://lacomer.buscador.amarello.com.mx/"

and whose endpoint names are wired in main.min.js:

    GET {AMARELLO_BASE}/searchArtPrior
        ?s=<term>&succId=<store id>&col=<collection>&p=<page>&npagel=<page size>

Passing an empty search term (s="") returns the WHOLE catalog rather than a
filtered result, which turns this into a whole-catalog walker exactly like
the VTEX flat endpoint: npagel=200 confirmed to work (500 at npagel=500),
total=28,334 distinct EANs at succId=363 (the store id embedded in the
homepage's dynatrace config as the default web/national catalog store).
Pagination advances the *cursor* correctly, but a handful of "patrocinados"
(sponsored) rows are re-injected near the top of each page -- dedupe on
`artEan`, not on row count, same as every other endpoint in this codebase.

No auth, no Referer/XRW headers required; confirmed with a cold curl_cffi
chrome124 client.

CAVEAT (documented, not a bug): because there is no server-rendered
product page anywhere on this domain, the `url` field below is a
best-effort deep link built from the ui-router route signature
(`/detarticulo/:artEan/:padreId/:pasId/:noPagina/:origen/:folleto/:agruId/:agruVirtual`
in main.min.js). It resolves to HTTP 200 (the SPA shell, which loads for
every route) but will NOT show the product name in the raw HTML -- the
page hydrates client-side only. This is a structural property of the
storefront, not a spider defect.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://lacomer.buscador.amarello.com.mx/searchArtPrior"
STORE_ID = "363"
COLLECTION = "lacomer_2"
PAGE_SIZE = 200
MAX_PAGES = 200  # safety cap: 200 * 200 = 40,000 rows, above the observed 28,334 total


class LacomerMxSpider(scrapy.Spider):
    name = "lacomer_mx"
    allowed_domains = ["lacomer.com.mx", "amarello.com.mx"]
    currency = "MXN"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_eans: set[str] = set()

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        qs = urlencode(
            {
                "s": "",
                "succId": STORE_ID,
                "col": COLLECTION,
                "p": page,
                "npagel": PAGE_SIZE,
            }
        )
        return scrapy.Request(
            f"{BASE_URL}?{qs}",
            callback=self.parse_page,
            errback=self.errback,
            meta={"page": page},
            dont_filter=True,
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON at {response.url}")
            return

        page = response.meta["page"]
        rows = data.get("res") or []
        new_count = 0
        for row in rows:
            item = self._to_item(row)
            if item is None:
                continue
            if item["product_id"] in self.seen_eans:
                continue
            self.seen_eans.add(item["product_id"])
            new_count += 1
            yield item

        logger.info(
            f"{self.name}: page={page} rows={len(rows)} new={new_count} "
            f"distinct_so_far={len(self.seen_eans)} total={data.get('total')}"
        )

        if rows and page < MAX_PAGES:
            yield self._page_request(page + 1)

    def _to_item(self, row):
        ean = row.get("artEan")
        price = row.get("artPrven")
        if not ean or price is None:
            return None
        name = (row.get("artDesCom") or row.get("artDes") or "").strip()[:500]
        if not name:
            return None
        category_parts = [p for p in (row.get("agruDesPadre"), row.get("agruDes")) if p]
        category = " > ".join(category_parts) or None
        agru_padre = row.get("agruIdPadre") or 0
        agru_id = row.get("agruId") or 0
        url = (
            f"https://www.lacomer.com.mx/lacomer/#!/detarticulo/{ean}/"
            f"{agru_padre}/{agru_id}/1/0/0/{agru_id}/0"
        )
        inve_cant = row.get("inveCant")
        available = (
            bool(inve_cant) if inve_cant is not None else row.get("artStat") == "ALTA"
        )
        return {
            "product_id": str(ean),
            "product_name": name,
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": available,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
