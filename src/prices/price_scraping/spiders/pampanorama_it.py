"""
Pam Panorama (Italy) -- https://www.pampanorama.it/.

Bespoke React SPA (create-react-app style, webpack chunk hashes). The
`/prodotti/<slug>.html` pages themselves are a client-rendered shell with NO
server-rendered price data (byte-identical ~5.2KB HTML on every URL tried,
confirmed 2026-09-10) -- the site's own JS calls a CMS-style JSON API at
`https://coeus.ppapi.it/api/v2_2/post/query` (found via `main.*.chunk.js`'s
`api.endpoint` config string; confirmed live via a headless-Chromium network
trace on 2026-09-10, no auth/cookies required).

`POST /api/v2_2/post/query?noCache=0&typeUuid=product` with form-encoded
`fields[]=id&fields[]=name&fields[]=slug&metadatas[]=price&metadatas[]=
weight_unit&metadatas[]=category&limit=<n>&offset=<n>` enumerates the FULL
product catalog (not filtered by `fieldQueries[slug]`, which the single-PDP
page uses to fetch one post) -- confirmed live: offset=0 vs offset=200 (limit
200 each) returned 200/200 distinct ids (2250-2460 vs 2461-2666), zero
overlap. Catalog size measured by walking offset in steps of 200/2000 until
an empty page: exactly 6312 `typeUuid=product` posts total, consistent with
the 6135-6165 `/prodotti/*.html` URLs in `sitemap.xml` (the pre-probe's "171
product URLs" undercounted badly -- that number came from the Playwright
trace's single-PDP capture, not the enumerable bulk endpoint).

IMPORTANT caveat, probed and confirmed rather than assumed: `metadatas.price`
is EMPTY for the large majority of posts -- this is a brand/nutrition
content hub first, e-commerce second. A full scan of all 6312 products
(2026-09-10) found exactly 262 with a non-empty price string (~4.2%),
concentrated in wine, fresh meat/fish, deli, and produce. Prices are mixed
Italian-locale formats: plain point-decimal ("9.9"), comma-decimal ("4,9"),
and per-weight annotations for loose produce/meat ("0.99€/HG", "0,99 al kg",
"all'etto 3.99" = per 100g). `_parse_price` takes the first digit run
(comma treated as decimal point) and drops anything with no digits at all --
it does NOT attempt to normalize per-kg vs per-item pricing, since the
site displays loose/bulk items exactly this way at retail. Zero/blank
prices are dropped, matching the project convention that a missing price is
not a price.

Two other Italian grocers already ship in this tree (carrefour_it,
bennet_it) plus cortilia_it; Pam Panorama is a fully independent tenant/
platform (bespoke CMS, not WooCommerce/SAP-Hybris), so this is additive
assortment, not a duplicate.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://coeus.ppapi.it/api/v2_2/post/query"
_PAGE_SIZE = 200
MAX_OFFSET = 8000  # safety cap; catalog measured at 6312 on 2026-09-10
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _parse_price(raw) -> str | None:
    if not raw:
        return None
    m = _NUM_RE.search(str(raw))
    if not m:
        return None
    val = m.group(0).replace(",", ".")
    try:
        f = float(val)
    except ValueError:
        return None
    if f <= 0:
        return None
    return str(f)


class PampanoramaItSpider(scrapy.Spider):
    name = "pampanorama_it"
    allowed_domains = ["coeus.ppapi.it"]
    currency = "EUR"
    language = "it"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _form(self, offset: int) -> dict:
        return {
            "typeUuid": "product",
            "fields[0]": "id",
            "fields[1]": "uuid",
            "fields[2]": "name",
            "fields[3]": "slug",
            "metadatas[0]": "price",
            "metadatas[1]": "weight_unit",
            "metadatas[2]": "category",
            "limit": str(_PAGE_SIZE),
            "offset": str(offset),
            "CACHE_KEY": "",
        }

    async def start(self):
        yield scrapy.FormRequest(
            f"{_API_URL}?noCache=0&typeUuid=product",
            formdata=self._form(0),
            callback=self.parse_page,
            meta={"offset": 0},
            headers={"Referer": "https://www.pampanorama.it/"},
        )

    def parse_page(self, response):
        offset = response.meta["offset"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("pampanorama_it: bad JSON at offset %d", offset)
            return
        posts = (payload.get("data") or {}).get("posts") or []
        logger.info("pampanorama_it: offset %d -> %d posts", offset, len(posts))
        for post in posts:
            item = self._item(post)
            if item:
                yield item

        if len(posts) == _PAGE_SIZE and offset + _PAGE_SIZE < MAX_OFFSET:
            nxt = offset + _PAGE_SIZE
            yield scrapy.FormRequest(
                f"{_API_URL}?noCache=0&typeUuid=product",
                formdata=self._form(nxt),
                callback=self.parse_page,
                meta={"offset": nxt},
                headers={"Referer": "https://www.pampanorama.it/"},
            )

    def _item(self, post: dict):
        name = (post.get("name") or "").strip()
        product_id = str(post.get("id") or post.get("uuid") or "")
        meta = post.get("metadatas") or {}
        price = _parse_price(meta.get("price"))
        if not name or not product_id or not price:
            return None
        slug = post.get("slug") or ""
        url = f"https://www.pampanorama.it/prodotti/{slug}.html" if slug else "https://www.pampanorama.it/"
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": meta.get("category"),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
