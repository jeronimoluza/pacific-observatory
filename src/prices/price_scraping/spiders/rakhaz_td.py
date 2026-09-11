"""
Rakhaz (Chad) -- https://www.rakhaz.com/ -- "Livraison de Fruits et Legumes"
(fresh fruit & vegetable delivery in N'Djamena).

Next.js frontend renders the catalogue client-side; found the real backend
via a Playwright network trace of /accueil (browser console showed a CORS
error for a *different* candidate, douniamarket.com, but Rakhaz's own fetch
succeeded): the product API lives on a separate Hostinger-hosted domain,
https://aliceblue-seal-957651.hostingersite.com/api/products?page=N -- plain
`requests` reads it fine over HTTPS with no auth, no impersonation needed.

Laravel-style paginator: {"data": [...], "meta": {"current_page",
"last_page", "total": 27, "per_page": 20}}. Enumerability confirmed: page1
(20 ids) vs page2 (7 ids) disjoint, meta.total=27 matches 20+7. Whole
catalog: 27 SKUs, 100% fresh fruits/vegetables/tubers/leafy-greens (Ananas,
Avocat bio du Cameroun, Bananes, Carottes, Celeri, Citron, Grenades,
Haricots verts, Ignames, Mandarine, Mangue du Cameroun, Melon, Molokhiya,
Oignons rouge, Orange, Papaye Bio, Pasteque frais du Tchad, Patate douce,
Piment rouge/vert, Poireaux, Poivrons jaunes, Pomme de Terre, Pommes,
Salades, Taro) -- explicitly "frais du Tchad" on the watermelon listing,
confirming domestic (not imported-catalogue) pricing. Prices are integer
XAF (no minor unit, e.g. Bananes 800/kg, Pommes de Terre 1500/kg) --
plausible N'Djamena market prices. Product names also carry an Arabic
translation (name_ar) alongside French, matching Chad's Arabic-speaking
population.

Channel: fresh-market. This is the wholesale/fresh-produce type of source
the SSA sweep flags as high-value for COICOP 01.1 -- supermarkets in this
market (hadimi_td, tchadcommerce_td, mossosouk_td) carry almost no fresh
produce.

Only 27 SKUs total -- below the skill's default framing of "large catalog"
but clears the Phase-6 >=5-row gate comfortably, and Chad has only 31
distinct product names in the entire 43M-row corpus, so this genuinely
doubles the country's product diversity.

Page family: API (reads the JSON REST API directly, never fetches a
rendered page). PDP url is synthesized from the product slug
(https://www.rakhaz.com/products/<id>) since the API response itself
carries no canonical product-page URL field.
"""

from datetime import datetime, timezone

import scrapy


class RakhazTdSpider(scrapy.Spider):
    name = "rakhaz_td"
    allowed_domains = ["aliceblue-seal-957651.hostingersite.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    BASE_URL = "https://aliceblue-seal-957651.hostingersite.com/api/products"

    async def start(self):
        yield scrapy.Request(f"{self.BASE_URL}?page=1", callback=self.parse_page, meta={"page": 1})

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            return
        data = payload.get("data") or []
        meta = payload.get("meta") or {}
        for p in data:
            item = self._item(p)
            if item:
                yield item
        page = response.meta["page"]
        last_page = meta.get("last_page", page)
        if page < last_page:
            nxt = page + 1
            yield scrapy.Request(
                f"{self.BASE_URL}?page={nxt}", callback=self.parse_page, meta={"page": nxt}
            )

    def _item(self, p: dict):
        if not p.get("is_active", True):
            return None
        price = p.get("price")
        try:
            if price is None or float(price) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        pid = str(p.get("id"))
        slug = p.get("slug") or pid
        cat = (p.get("category") or {}).get("name")
        return {
            "product_id": pid,
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": cat,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("stock", 0)) if p.get("stock") is not None else True,
            "url": f"https://www.rakhaz.com/products/{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
