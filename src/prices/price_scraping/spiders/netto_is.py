"""
Nettó (Iceland) — https://www.netto.is/.

Nettó (operated by Samkaup) runs no online store: the whole netto.is domain
is a static Webflow marketing site (confirmed via `data-wf-site` markers and
an empty `/sitemap.xml`). There is no product search, no category browse,
and no per-product URL anywhere on the domain.

The one page that carries real, structured, current transaction prices is
the weekly deals page `/tilbod` ("Offers"). It server-renders a Webflow CMS
collection of `.offer-card_wrapper` cards — one per promoted SKU, each with
a title, a brand/variant description, and (for most, not all) a
`.price-label_new-price` / `.price-label_old-price` pair with a per-unit
suffix (`kr. kg.`, `kr. pk.`, `kr. stk.`). Roughly a third of the 100 cards
on the page are brand-name banners with no attached price (generic "20%
off" promos for a whole brand, mostly from a concurrent "Heilsudagar"
health-week campaign) — those are skipped rather than emitting a null or
fabricated price. A hidden `fs-list-field="category"` div exists per card
(Finsweet CMS filtering) but ships empty in the server-rendered HTML, so
`category` is left null; the classifier assigns COICOP per product.

No product has a stable id or its own URL (no PDP exists at all — this is
a single static page, not a catalog). Per the onboarding brief,
`DuplicationPipeline` dedups on `item['url']`, so each row is given a
synthetic URL fragment `#<slugified-title>-<index>` to keep the whole set
instead of collapsing to one row; `product_id` mirrors the same slug.

The page is a *weekly rotating offers list*, not the full assortment, so
this is deliberately narrow (analytical_role stays `retailer_sku`, not
`official_avg` — these are one retailer's own transaction prices) and
undercounts Nettó's catalog. Re-run cadence is weekly (page states
"Tilboðin gilda til <date>", i.e. valid until a specific date each cycle).

Currency ISK, whole krónur (prices like `7959`, `299` are plain integers
with no minor-unit division, matching countries.yaml).

Verified live 2026-09-01: `GET /tilbod` -> 200, 216KB SSR, 34 of 100 offer
cards carry a real price, e.g. 'Nauta entrecote' (Kjötborðið, sérvalið) ISK
7959/kg, 'Lárpera' (avocado) ISK 869/kg, 'Kjúklingabringur 100%' (Ísfugl
chicken breast) ISK 3199/kg.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.netto.is"
LISTING_URL = f"{BASE_URL}/tilbod"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "item"


class NettoIsSpider(scrapy.Spider):
    name = "netto_is"
    allowed_domains = ["netto.is"]
    currency = "ISK"
    language = "is"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(LISTING_URL, callback=self.parse_listing)

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css(".offer-card_wrapper")
        emitted = 0
        for i, card in enumerate(cards):
            price_text = card.css(".price-label_new-price::text").get()
            if not price_text or not price_text.strip().isdigit():
                continue  # brand banner with no attached price — skip
            name = (card.css(".offer-card_title::text").get() or "").strip()
            if not name:
                continue
            description = (
                card.css(".offer-card_description::text").get() or ""
            ).strip()
            full_name = f"{name} {description}".strip() if description else name
            slug = f"{_slugify(name)}-{i}"
            emitted += 1
            yield {
                "product_id": slug,
                "product_name": full_name[:500],
                "category": None,
                "price": price_text.strip(),
                "currency": self.currency,
                "available": True,
                "url": f"{LISTING_URL}#{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: cards={len(cards)} priced_rows={emitted}")
