"""
Sayarat24 (Syria) -- https://syarat24.com/

Used- and new-car classifieds for Syria. The Next.js front end is backed
by a public, unauthenticated JSON listing API.

MEASURED 2026-09-12 (curl_cffi impersonate=chrome124, no auth/cookies):

    GET https://syarat24.com/api/listings?page=N
    -> {"listings": [{"id","status","year","trim","bodyType","fuelType",
                      "transmission","mileageKm","engineCC","color",
                      "condition","priceUSD","priceSYP","governorate",
                      "city","brand":{"name","nameAr",...},
                      "model":{"name","nameAr",...}, ...}],
        "pagination": {"page","perPage","total","totalPages"}}

ENUMERABILITY (MEASURED): pagination.total=63 over 3 pages at perPage=30;
page 1 vs page 2 listing-id sets disjoint, zero overlap.

CURRENCY: the API carries BOTH priceUSD and priceSYP. Every one of the 30
listings sampled on 2026-09-12 had priceUSD set and priceSYP null -- used
cars in Syria are quoted in dollars. This spider emits whichever field is
actually populated and stamps the matching ISO code per row, rather than
pinning one currency for the source; a row with neither is dropped.

COICOP: narrow source. All 63 rows of the verification run were
second-hand (condition USED_GOOD x62, USED_FAIR x1, zero new), so the
manifest declares the LEAF 07.1.1.2 "Second-hand motor cars" -- the
parent 07.1.1 has children and would fail coicop_codes.is_narrow().

PRODUCT NAME: the API has no free-text title, so the name is composed
from the fields the listing does carry -- "<year> <Brand> <Model> <trim>"
-- using the English brand/model names (nameAr is available and kept out
of the name deliberately, so the string stays one consistent shape).

Page family: API. The `url` emitted is the site's own listing permalink
(`/<brand-slug>/<model-slug>/<id>`, the shape the rendered listing grid
links to), which this spider never fetches.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://syarat24.com"
MAX_PAGES = 60  # safety cap


class Syarat24Spider(scrapy.Spider):
    name = "syarat24"
    allowed_domains = ["syarat24.com", "www.syarat24.com"]
    currency = "USD"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _page_url(self, page: int) -> str:
        return f"{BASE}/api/listings?page={page}"

    async def start(self):
        yield scrapy.Request(
            self._page_url(1), callback=self.parse_page, meta={"page": 1}
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        listings = payload.get("listings") or []
        page = response.meta["page"]
        logger.info(f"{self.name} page={page} count={len(listings)}")

        for listing in listings:
            item = self._item(listing)
            if item:
                yield item

        pag = payload.get("pagination") or {}
        total_pages = int(pag.get("totalPages") or 0)
        if page < min(total_pages, MAX_PAGES):
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt), callback=self.parse_page, meta={"page": nxt}
            )

    @staticmethod
    def _price(listing: dict):
        for field, code in (("priceUSD", "USD"), ("priceSYP", "SYP")):
            raw = listing.get(field)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value, code
        return None, None

    def _item(self, listing: dict):
        value, code = self._price(listing)
        if value is None:
            return None

        brand_obj = listing.get("brand") or {}
        model_obj = listing.get("model") or {}
        brand = brand_obj.get("name") or ""
        model = model_obj.get("name") or ""
        year = listing.get("year")
        trim = listing.get("trim") or ""
        name = " ".join(
            str(part) for part in (year, brand, model, trim) if part
        ).strip()
        if not name:
            return None

        location = " / ".join(
            str(x) for x in (listing.get("governorate"), listing.get("city")) if x
        )
        brand_slug = brand_obj.get("slug")
        model_slug = model_obj.get("slug")
        listing_id = listing.get("id")
        url = (
            f"{BASE}/{brand_slug}/{model_slug}/{listing_id}"
            if brand_slug and model_slug
            else ""
        )
        return {
            "product_id": str(listing.get("id")),
            "product_name": name[:500],
            "category": listing.get("bodyType") or None,
            "price": str(value),
            "currency": code,
            "available": listing.get("status") == "ACTIVE",
            "url": url,
            "location": location or None,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
