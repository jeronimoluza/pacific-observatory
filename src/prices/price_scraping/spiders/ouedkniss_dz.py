"""
Ouedkniss (Algeria) — https://www.ouedkniss.com/.

Algeria's largest general classifieds marketplace (real estate, vehicles,
electronics, appliances, food, services — private sellers + some verified
stores). The React SPA ships no SSR data (the /s search page and category
pages return an identical empty shell), and GraphQL introspection at
https://api.ouedkniss.com/graphql is disabled. The query itself is open,
though: captured live via Playwright network trace on the /s page
(SearchAnnouncementsQuery, operationName-keyed) and replays cleanly over
plain curl_cffi with just Origin/Referer headers, no auth, no cookies.

The bare search (no categorySlug, no q) returns zero results by design —
you must pass a categorySlug. Verified against `electronique_electromenager`
(Electronics & Home appliance): 839 pages at count=48/page, zero id overlap
between page 1 and page 2 (real pagination, not a flat-cap re-serve).
Prices are plain DZD integers (no minor-unit trap). priceUnit is usually
"UNIT" but can be "MONTH"/"DAY" for rentals/services — passed straight
through in `category` since there's no separate schema slot for it.

Walks the top-level LISTING_MENU categories (from menuFetch) rather than
one category, to get COICOP breadth across the classifier's basket
divisions rather than just electronics. "offres_demandes_emploi" (jobs) is
excluded — no retail price semantics.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.ouedkniss.com/graphql"
BASE_URL = "https://www.ouedkniss.com"
PAGE_SIZE = 48
MAX_PAGES_PER_CATEGORY = 60

CATEGORIES = [
    "immobilier",
    "automobiles_vehicules",
    "pieces_detachees",
    "telephones",
    "informatique",
    "electronique_electromenager",
    "vetements_mode",
    "sante_beaute",
    "meubles_maison",
    "loisirs_divertissements",
    "sport",
    "materiaux_equipement",
    "alimentaires",
    "voyages",
    "services",
]

_QUERY = """query SearchAnnouncementsQuery($q: String, $filter: SearchFilterInput, $mediaSize: MediaSize = MEDIUM) {
  search(q: $q, filter: $filter) {
    announcements {
      ...SearchAnnouncementsContent
      __typename
    }
    __typename
  }
}

fragment SearchAnnouncementsContent on AnnouncementPagination {
  data {
    ...AnnouncementContentNoUserReaction
    __typename
  }
  paginatorInfo {
    lastPage
    hasMorePages
    __typename
  }
  __typename
}

fragment AnnouncementContentNoUserReaction on Announcement {
  id
  title
  slug
  price
  pricePreview
  priceUnit
  priceType
  category {
    id
    slug
    __typename
  }
  defaultMedia(size: $mediaSize) {
    mediaUrl
    __typename
  }
  __typename
}
"""


class OuedknissDzSpider(scrapy.Spider):
    name = "ouedkniss_dz"
    allowed_domains = ["api.ouedkniss.com", "www.ouedkniss.com"]
    currency = "DZD"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 4,
    }

    def start_requests(self):
        for cat in CATEGORIES:
            yield self._page_request(cat, 1)

    def _page_request(self, category, page):
        payload = {
            "operationName": "SearchAnnouncementsQuery",
            "variables": {
                "mediaSize": "MEDIUM",
                "q": None,
                "filter": {
                    "categorySlug": category,
                    "origin": None,
                    "connected": False,
                    "delivery": None,
                    "regionIds": [],
                    "cityIds": [],
                    "priceRange": [],
                    "exchange": None,
                    "hasPictures": False,
                    "hasPrice": True,
                    "priceUnit": None,
                    "fields": [],
                    "page": page,
                    "orderByField": {"field": "REFRESHED_AT"},
                    "count": PAGE_SIZE,
                },
            },
            "query": _QUERY,
        }
        return scrapy.Request(
            GRAPHQL_URL,
            method="POST",
            body=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/s",
            },
            callback=self.parse_page,
            meta={"category": category, "page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON response cat={category} page={page}")
            return

        block = ((data.get("data") or {}).get("search") or {}).get("announcements") or {}
        items = block.get("data") or []
        paginator = block.get("paginatorInfo") or {}
        logger.info(
            f"{self.name}: cat={category} page={page} count={len(items)} "
            f"lastPage={paginator.get('lastPage')}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            price = it.get("price")
            title = (it.get("title") or "").strip()
            slug = it.get("slug")
            ann_id = it.get("id")
            if not title or price is None or ann_id is None:
                continue
            yield {
                "product_id": str(ann_id),
                "product_name": title[:500],
                "category": (it.get("category") or {}).get("slug"),
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}/{slug}-d{ann_id}" if slug else f"{BASE_URL}/s",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if items and page < MAX_PAGES_PER_CATEGORY and paginator.get("hasMorePages"):
            yield self._page_request(category, page + 1)
