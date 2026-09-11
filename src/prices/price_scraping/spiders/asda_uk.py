"""
Spider for Asda (United Kingdom) -- https://groceries.asda.com/.

Next.js storefront whose full catalog search runs on a public Algolia
index (app id 8I6WSKCCNV, index ASDA_PRODUCTS). The search-only API key
is embedded in the homepage's Next.js config JSON
(window config -> algolia.searchAPIKey), harvested live 2026-09-10 via
curl_cffi impersonate=chrome124 (the plain HTML site 403s a bare curl/UA
request -- Akamai/whatever WAF fronts groceries.asda.com does not front
the Algolia CDN, so once the key is known no impersonation is needed to
query it).

Algolia enforces a hard "page * hitsPerPage < 20000" reachable-hits cap
per query (confirmed live: page=19 at hitsPerPage=1000 -> 200 with 1000
hits, page=20 -> the documented "you can only fetch the 20000 hits for
this query" error). The catalog is ~122,972 products, so a single
unfiltered query cannot reach it all. PRIMARY_TAXONOMY.CAT_NAME is a
faceted, single-valued attribute whose 49 values partition the whole
index exactly (facet counts sum to nbHits with zero overlap). Every
category is under the 20k cap except "Home & Entertainment" (52,778
products), which is further split by the also-faceted
PRIMARY_TAXONOMY.DEPT_NAME (24 values, all under 20k, counts again sum
exactly to the category total). Every other category is queried directly;
"Home & Entertainment" is queried once per department instead.

Enumerability verified live 2026-09-10: "Food Cupboard"
(nbHits=14,803) page=0 vs page=1 at hitsPerPage=1000 -> 1000/1000 hits,
ZERO objectID overlap -> DISTINCT.

Price: PRICES.EN.PRICE (England list price, GBP) -- ASDA prices some
items differently across the four home nations (EN/NI/SC/WA, e.g. deposit
return schemes), EN is used as the single national reference price.

The record's own "ID" field is not usable as a URL slug (its format is
inconsistent -- raw digits, 13-digit digits, or a "SKU<digits>" prefix --
and does not match ASDA's own PDP routing for the SKU-prefixed case). The
"CIN" field (populated on every sampled hit, 1000/1000 in one page) is
usable: https://groceries.asda.com/product/<CIN> was confirmed live
2026-09-10 to resolve (via curl_cffi impersonate=chrome124, following the
redirect to www.asda.com/groceries/product/<CIN>) to the correct product's
own og:title, e.g. CIN 9373511 -> og:title "ASDA Rice Snaps Marshmallow
Bars 176g (8 x 22g)", matching the Algolia record's NAME exactly. Items
missing CIN (none observed, but the field is optional in principle) are
dropped rather than emitted with a null/placeholder url: the project's
DuplicationPipeline hashes item["url"] to dedupe within a run, and a
constant fallback (empty string or None) would collapse every such item
into a single surviving row.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "8I6WSKCCNV"
_API_KEY = "03e4272048dd17f771da37b57ff8a75e"
_INDEX = "ASDA_PRODUCTS"
_ENDPOINT = f"https://{_APP_ID.lower()}-dsn.algolia.net/1/indexes/{_INDEX}/query"

_HITS_PER_PAGE = 1000

_ATTRS = [
    "ID",
    "CIN",
    "NAME",
    "PRICES",
    "BRAND",
    "PACK_SIZE",
    "PRIMARY_TAXONOMY",
    "STATUS",
    "DISPLAY_ONLINE",
    "objectID",
]

# PRIMARY_TAXONOMY.CAT_NAME facet values and counts, harvested live
# 2026-09-10. All but "Home & Entertainment" are queried directly.
_CATEGORIES = [
    "Food Cupboard",
    "Toiletries & Beauty",
    "Chilled Food",
    "Other",
    "Beer, Wine & Spirits",
    "Laundry & Household",
    "Meat, Poultry & Fish",
    "Bakery",
    "Frozen Food",
    "Health & Wellness",
    "Baby, Toddler & Kids",
    "Pet Food & Accessories",
    "Drinks",
    "World Food",
    "Fresh Fruit, Vegetables & Flowers",
    "Kiosk",
    "Christmas",
    "Dietary & Lifestyle",
    "Halloween",
    "Easter",
    "Sweets, Treats & Snacks",
    "The Entertainer Toys",
    "Events & Inspiration",
    "Mother's Day",
    "Rollback",
    "Coronation Celebration",
    "Father's Day",
    "Free From...",
    "Summer",
    "Get Match Ready",
    "Ramadan",
    "Back to School",
    "Live Better",
    "Vegan & Plant Based",
    "Happy Lunar New Year",
    "Valentine's Day",
    "Organic",
    "Better For You",
    "Big Night In",
    "Celebrate New Year",
    "JUST ESSENTIALS",
    "Price Drop",
    "(OLD) Exceptional by Asda",
    "Exceptional By Asda",
    "Garden & Outdoor",
    "Going to Uni",
    "Vegan & Free From",
    "Veganuary",
]

_HOME_ENTERTAINMENT = "Home & Entertainment"

# PRIMARY_TAXONOMY.DEPT_NAME values within "Home & Entertainment", all
# individually under the 20k reachable-hits cap, harvested live 2026-09-10.
_HOME_ENTERTAINMENT_DEPTS = [
    "Bed, Bath & Home",
    "Music, Film, Games & Books",
    "Kitchen",
    "Toys",
    "Partyware & Gifting",
    "Garden & Outdoor",
    "Stationery, Magazines & Stamps",
    "Technology & Electricals",
    "Christmas",
    "DIY & Car Care",
    "Greeting Cards",
    "Halloween",
    "Travel & Leisure",
    "Batteries & Light Bulbs",
    "Party, Cards & Gift Wrap",
    "JML",
    "At Home with Stacey Solomon",
    "Mother's Day Gifts & Dine",
    "Fathers Day",
    "Disney",
    "Valentine's Gifts & Decorations",
    "Celebrating Disney",
    "For The Home",
    "Kids Party",
]


class AsdaUkSpider(scrapy.Spider):
    name = "asda_uk"
    allowed_domains = ["algolia.net"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    def _headers(self):
        return {
            "X-Algolia-Application-Id": _APP_ID,
            "X-Algolia-API-Key": _API_KEY,
            "Content-Type": "application/json",
        }

    def _query(self, facet_filters, label, page):
        body = {
            "query": "",
            "hitsPerPage": _HITS_PER_PAGE,
            "page": page,
            "facetFilters": facet_filters,
            "attributesToRetrieve": _ATTRS,
        }
        return scrapy.Request(
            _ENDPOINT,
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse,
            meta={"facet_filters": facet_filters, "label": label, "page": page},
            dont_filter=True,
        )

    async def start(self):
        for cat in _CATEGORIES:
            yield self._query([[f"PRIMARY_TAXONOMY.CAT_NAME:{cat}"]], cat, 0)
        for dept in _HOME_ENTERTAINMENT_DEPTS:
            yield self._query(
                [
                    [f"PRIMARY_TAXONOMY.CAT_NAME:{_HOME_ENTERTAINMENT}"],
                    [f"PRIMARY_TAXONOMY.DEPT_NAME:{dept}"],
                ],
                f"{_HOME_ENTERTAINMENT} > {dept}",
                0,
            )

    def parse(self, response):
        facet_filters = response.meta["facet_filters"]
        label = response.meta["label"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.error("asda_uk: non-JSON response for %s page=%s", label, page)
            return

        nb_hits = payload.get("nbHits", 0)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in payload.get("hits", []):
            item = self._build(hit, scraped_at)
            if item:
                yield item

        max_reachable_page = min(payload.get("nbPages", 0), 20000 // _HITS_PER_PAGE)
        if page == 0:
            logger.info("asda_uk: %s nbHits=%s nbPages=%s", label, nb_hits, payload.get("nbPages"))
            for p in range(1, max_reachable_page):
                yield self._query(facet_filters, label, p)

    def _build(self, hit, scraped_at):
        if hit.get("STATUS") not in (None, "A"):
            return None
        if hit.get("DISPLAY_ONLINE") is False:
            return None
        prices = hit.get("PRICES") or {}
        en = prices.get("EN") or {}
        price = en.get("PRICE")
        if not price or price <= 0:
            return None
        name = hit.get("NAME")
        if not name:
            return None
        cin = hit.get("CIN")
        if not cin:
            return None
        taxonomy = hit.get("PRIMARY_TAXONOMY") or {}
        category = " > ".join(
            p
            for p in (
                taxonomy.get("CAT_NAME"),
                taxonomy.get("DEPT_NAME"),
                taxonomy.get("AISLE_NAME"),
            )
            if p
        ) or None
        return {
            "product_id": str(hit.get("ID") or hit.get("objectID")),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://groceries.asda.com/product/{cin}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
