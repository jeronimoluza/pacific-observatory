"""
Spider for Avito Morocco (https://www.avito.ma/) — general classifieds
marketplace, asking prices across most consumer categories (COICOP wide;
coicop_classification: classifier).

Server-rendered Next.js pages carry a full `__NEXT_DATA__` JSON blob with
every ad on the listing page already embedded — no need to visit the
per-ad detail page at all. Each ad object under
`props.pageProps.componentProps.ads.ads` carries `listId`, `subject`
(title), `price.value`/`price.currency` (or `oldPrice` when `price` is
an empty dict — seen on ads marked "non négociable" style with the
original asking price only), `category.formatted` (breadcrumb string)
and `href` (canonical PDP url). Verified live 2026-09-06 with
curl_cffi impersonate=chrome124, no WAF encountered.

Pagination is the `?o=<n>` query param appended to the listing URL
(confirmed: page 1 and `?o=2` return disjoint `listId` sets). Two broad
top-level listing pages are crawled: `market` (Informatique, Maison et
Jardin, Habillement et Mode, Sport, Loisirs, Bébé, Animalerie —
divisions 03/05/09/12) and the used-cars category (division 07,
`voitures_d_occasion-à_vendre`).

Ads with no numeric price on either `price` or `oldPrice` (free items,
swaps, "prix a debattre" with fields genuinely empty) are dropped.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)

_CATEGORIES = [
    ("https://www.avito.ma/fr/maroc/market", "market"),
    (
        "https://www.avito.ma/fr/maroc/voitures_d_occasion-%C3%A0_vendre",
        "voitures_d_occasion",
    ),
]


class AvitoMaSpider(scrapy.Spider):
    name = "avito_ma"
    allowed_domains = ["avito.ma"]
    currency = "MAD"
    language = "fr"
    MAX_PAGES = 100000  # dedup on `seen`; a re-served / exhausted page yields fresh=0 and stops

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for base_url, label in _CATEGORIES:
            yield scrapy.Request(
                base_url,
                callback=self.parse,
                meta={"impersonate": "chrome124", "page": 1, "base": base_url, "seen": set(), "label": label},
            )

    def parse(self, response):
        base = response.meta["base"]
        page = response.meta["page"]
        seen = response.meta["seen"]
        label = response.meta["label"]

        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"avito_ma: no __NEXT_DATA__ on {response.url}")
            return
        try:
            data = json.loads(m.group(1))
            ads = data["props"]["pageProps"]["componentProps"]["ads"]["ads"]
        except (KeyError, json.JSONDecodeError) as exc:
            logger.warning(f"avito_ma: could not walk __NEXT_DATA__ on {response.url}: {exc}")
            return

        fresh = 0
        for ad in ads:
            item = self._item(ad)
            if item is None:
                continue
            list_id = ad.get("listId")
            if list_id in seen:
                continue
            seen.add(list_id)
            fresh += 1
            yield item

        if fresh and page < self.MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{base}?o={nxt}",
                callback=self.parse,
                meta={
                    "impersonate": "chrome124",
                    "page": nxt,
                    "base": base,
                    "seen": seen,
                    "label": label,
                },
            )

    def _item(self, ad):
        name = ad.get("subject")
        href = ad.get("href")
        list_id = ad.get("listId")
        if not (name and href and list_id):
            return None
        price_obj = ad.get("price") or {}
        value = price_obj.get("value")
        if value is None:
            price_obj = ad.get("oldPrice") or {}
            value = price_obj.get("value")
        if not value or value <= 0:
            return None
        category = (ad.get("category") or {}).get("formatted") or (ad.get("category") or {}).get("name")
        return {
            "product_id": list_id,
            "product_name": name.strip(),
            "category": category,
            "price": float(value),
            "currency": self.currency,
            "available": True,
            "url": href,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
