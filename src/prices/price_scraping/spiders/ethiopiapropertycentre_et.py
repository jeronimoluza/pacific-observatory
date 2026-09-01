"""
Spider for Ethiopia Property Centre (EPC) — https://ethiopiapropertycentre.com/

Residential rental-listing aggregator for Addis Ababa (part of the regional
"PropertyCentre" network, same platform family as Nigeria Property Centre /
Property24). Server-rendered listing pages under
`/for-rent/<flats-apartments|houses>/addis-ababa/showtype?page=N` carry plain
`<a href="/for-rent/.../<id>-<slug>">` cards; each PDP embeds a Schema.org
`RealEstateListing` JSON-LD block with `name`, `offers.price`,
`offers.priceCurrency`, `offers.availability` — no CSS selectors needed for
the price data itself, same JSON-LD pattern as aradamart_et/capelle_nr.

Re-verified live 2026-09-01: /for-rent/flats-apartments/addis-ababa/showtype
-> 200, "1,057 properties", 53 pages of ~20 cards each; /for-rent/houses/
addis-ababa/showtype -> 200, "1,015 properties". Requesting one page past
the last (page=54 for flats) returns a 302 redirect with zero listing
cards, which is the stop condition this spider walks to (no need to
hardcode a page count).

Scope: for-rent only (flats-apartments + houses), Addis Ababa only, in this
first pass — these are the two residential categories that map to COICOP
04.1.1 (actual rentals for housing); office-space/commercial/land listings
and the for-sale side of the site are out of scope (for-sale skews toward
diaspora investment buyers per one sampled listing's own title, "ideal for
diaspora buyers" — a different locality/consumption story than a tenant
renting a home to live in). Other regions (amhara, oromia, southern-nations
are all present in the site's own nav) are a natural follow-up but not
walked here.

CURRENCY NOTE (rule 8 — flagged loudly per onboarding policy): every
sampled listing's own JSON-LD priceCurrency is USD, not ETB, across both
flats and houses. This is a genuine, well-documented feature of the Addis
Ababa mid/high-end rental market (landlords set and collect rent in USD),
not a diaspora-remittance mislabel — the properties are physically in
Addis Ababa for local occupancy. The site *displays* a secondary "Br
xxx,xxx" figure next to the USD price, but that is a live FX-converted
estimate for browsing convenience, not the amount the tenant actually
pays — this spider does not harvest it. `currency` is read per-item from
JSON-LD (not hardcoded) in case a minority of listings are ETB-quoted.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://ethiopiapropertycentre.com"
_CATEGORIES = ["flats-apartments", "houses"]


class EthiopiapropertycentreEtSpider(scrapy.Spider):
    name = "ethiopiapropertycentre_et"
    allowed_domains = ["ethiopiapropertycentre.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    async def start(self):
        for category in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/for-rent/{category}/addis-ababa/showtype",
                callback=self.parse_listing,
                cb_kwargs={"category": category, "page": 1},
            )

    def parse_listing(self, response, category, page):
        # Match only actual PDP links (neighborhood/<numeric-id>-<slug>), not
        # neighborhood-level showtype sub-listing pages (e.g.
        # ".../addis-ababa/arada/showtype" or "...?bedrooms=2") which also
        # start with the same prefix but carry no RealEstateListing JSON-LD.
        pdp_re = re.compile(
            rf"^/for-rent/{re.escape(category)}/addis-ababa/[a-z0-9-]+/\d+-[a-z0-9-]+$"
        )
        paths = sorted(
            {
                href
                for href in response.css("a::attr(href)").getall()
                if pdp_re.match(href)
            }
        )
        logger.info(
            f"ethiopiapropertycentre_et: category={category} page={page} found {len(paths)} links"
        )
        if not paths:
            return
        for path in paths:
            url = _BASE + path
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(
                url, callback=self.parse_product, cb_kwargs={"category": category}
            )
        yield scrapy.Request(
            f"{_BASE}/for-rent/{category}/addis-ababa/showtype?page={page + 1}",
            callback=self.parse_listing,
            cb_kwargs={"category": category, "page": page + 1},
        )

    def parse_product(self, response, category):
        listing = self._extract_json_ld(response)
        if not listing:
            logger.warning(f"No RealEstateListing JSON-LD at {response.url}")
            return
        offers = listing.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        currency = offers.get("priceCurrency") or self.currency
        name = listing.get("name")
        # The site bakes a literal 1.00 into offers.price for listings marked
        # "Price on Application". Shipping those would put $1 apartments into
        # division-04 rents, which this source feeds directly (coicop 04.1.1).
        try:
            if price is not None and float(price) <= 1:
                logger.warning(
                    f"Dropping 'Price on Application' placeholder "
                    f"(price={price}) at {response.url}"
                )
                return
        except (TypeError, ValueError):
            pass

        if not (price and name):
            logger.warning(f"Missing price or name at {response.url}")
            return
        availability = offers.get("availability", "")
        listing_id = response.url.rstrip("/").rsplit("/", 1)[-1].split("-", 1)[0]
        yield {
            "product_id": listing_id,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": currency,
            "available": "OutOfStock" not in availability
            and "SoldOut" not in availability,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_json_ld(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("@type") == "RealEstateListing":
                return d
        return None
