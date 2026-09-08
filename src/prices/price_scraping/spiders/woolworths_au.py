"""
Spider for Woolworths Australia -- https://www.woolworths.com.au/.

Confirmed live 2026-09-06. Akamai fronts the whole site: plain `requests`
(no TLS impersonation) 403s on BOTH the homepage and the API with an
"Access Denied" Akamai stub. curl_cffi impersonate="chrome124" clears the
homepage with a plain GET -- but the homepage itself is an AEM content
shell (Adobe Experience Manager, `__NEXT_DATA__`) with no product data;
the catalogue is hydrated client-side from a JSON POST endpoint,
`/apis/ui/browse/category`. That endpoint also 403s under plain TLS but
returns a clean 200 with curl_cffi + a warmed session cookie jar (GET the
homepage first, then POST with the same cookies) -- "Playwright/impersonate
to discover, plain HTTP-shaped request to scrape" via this repo's
scrapy-impersonate RandomBrowserMiddleware, which applies curl_cffi TLS
impersonation to every scrapy.Request automatically (no per-request
`meta['impersonate']` needed -- see settings.py's composite handler +
IMPERSONATE_BROWSERS). Scrapy's own COOKIES_ENABLED carries the homepage
warm-up cookies into the POST automatically.

Category NodeIds (`categoryId` in the POST body) come from the homepage's
embedded navigation JSON (`"NodeId":"1_XXXXXXX"` next to
`"Description":"..."` and `"UrlFriendlyName":"..."`) -- confirmed the API
keys off `categoryId`, NOT the `url`/`location` fields in the payload (a
wrong categoryId with a correct dairy-eggs-fridge url/location still
returned Fruit & Veg products in testing).

Response shape: `{"Bundles":[{"Products":[{...}]}], "TotalRecordCount":N}`
-- one product per bundle in the common case. Product dict carries
Stockcode, Name, Price (current shelf price), WasPrice, PackageSize,
Brand, UrlFriendlyName (slug for the PDP URL). Currency AUD (Woolworths
does not return an explicit currency field; AUD is Australia's currency
per countries.yaml and Woolworths only operates domestically).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.woolworths.com.au"
_API_URL = f"{_BASE}/apis/ui/browse/category"
_PAGE_SIZE = 36
MAX_PAGES = 60  # safety cap per department

# (categoryId, Description, UrlFriendlyName) -- from the homepage's
# embedded navigation JSON, verified live 2026-09-06.
_DEPARTMENTS = (
    ("1-E5BEE36E", "Fruit & Veg", "fruit-veg"),
    ("1_D5A2236", "Meat, Seafood & Deli", "meat-seafood-deli"),
    ("1_DEB537E", "Bakery", "bakery"),
    ("1_6E4F4E4", "Dairy, Eggs & Fridge", "dairy-eggs-fridge"),
    ("1_39FD49C", "Pantry", "pantry"),
    ("1_ACA2FC2", "Freezer", "freezer"),
    ("1_5AF3A0A", "Drinks", "drinks"),
    ("1_8E4DA6F", "Liquor", "liquor"),
    ("1_61D6FEB", "Pet", "pet"),
    ("1_717A94B", "Baby", "baby"),
    ("1_894D0A8", "Health & Beauty", "health-beauty"),
    ("1_2432B58", "Household", "household"),
)


def _api_payload(category_id: str, url_path: str, page_number: int) -> dict:
    return {
        "categoryId": category_id,
        "pageNumber": page_number,
        "pageSize": _PAGE_SIZE,
        "sortType": "TraderRelevance",
        "url": url_path,
        "location": url_path,
        "formatObject": "{}",
        "isSpecial": False,
        "isBundle": False,
        "isMobile": False,
        "filters": [],
        "token": "",
    }


class WoolworthsAuSpider(scrapy.Spider):
    name = "woolworths_au"
    allowed_domains = ["woolworths.com.au"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "COOKIES_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/shop/browse/fruit-veg",
            callback=self.after_warmup,
            dont_filter=True,
        )

    def after_warmup(self, response):
        logger.info("woolworths_au: warmup %s status=%s", response.url, response.status)
        for category_id, description, slug in _DEPARTMENTS:
            url_path = f"/shop/browse/{slug}"
            yield scrapy.Request(
                _API_URL,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"{_BASE}{url_path}",
                    "Origin": _BASE,
                },
                body=json.dumps(_api_payload(category_id, url_path, 1)),
                callback=self.parse_category,
                meta={
                    "category_id": category_id,
                    "description": description,
                    "url_path": url_path,
                    "page_number": 1,
                },
                dont_filter=True,
            )

    def parse_category(self, response):
        category_id = response.meta["category_id"]
        description = response.meta["description"]
        url_path = response.meta["url_path"]
        page_number = response.meta["page_number"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning("woolworths_au: non-JSON response for %s page %s", description, page_number)
            return

        bundles = data.get("Bundles") or []
        total = data.get("TotalRecordCount", 0)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n_yielded = 0

        for bundle in bundles:
            for product in bundle.get("Products") or []:
                name = (product.get("Name") or "").strip()
                price = product.get("Price")
                stockcode = product.get("Stockcode")
                if not name or price in (None, "") or not stockcode:
                    continue
                slug = product.get("UrlFriendlyName") or ""
                product_url = f"{_BASE}/shop/productdetails/{stockcode}/{slug}"
                yield {
                    "product_id": stockcode,
                    "product_name": name[:500],
                    "category": description,
                    "price": price,
                    "currency": self.currency,
                    "available": bool(product.get("IsAvailable", True)),
                    "url": product_url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
                n_yielded += 1

        logger.info(
            "woolworths_au: %s page=%s yielded=%s total=%s",
            description, page_number, n_yielded, total,
        )

        fetched_so_far = page_number * _PAGE_SIZE
        if n_yielded > 0 and fetched_so_far < total and page_number < MAX_PAGES:
            next_page = page_number + 1
            yield scrapy.Request(
                _API_URL,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"{_BASE}{url_path}",
                    "Origin": _BASE,
                },
                body=json.dumps(_api_payload(category_id, url_path, next_page)),
                callback=self.parse_category,
                meta={
                    "category_id": category_id,
                    "description": description,
                    "url_path": url_path,
                    "page_number": next_page,
                },
                dont_filter=True,
            )
