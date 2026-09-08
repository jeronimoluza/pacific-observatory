"""
Freshmart PR (Puerto Rico) -- https://online.freshmartpr.com/.

Puerto Rico's natural/organic supermarket chain. The storefront is an Ember
SPA on the "NoQ" white-label grocery platform (noq-servers.net) sitting
behind an AWS WAF captcha SDK, so no price text is server-rendered and no
Freshop/WooCommerce/Shopify catalog endpoint exists. Two facts make it
scrapeable anyway, both verified live 2026-09-05:

1. The SPA publishes a per-STORE XML sitemap of every product it sells --
   /sitemap.xml is an index of 11 files, two per store (5 stores). Each
   product entry is a `/online/<store>/shop/all?pid=<uuid>` URL. Product
   uuids are per-store instances, not shared: Hato Rey and Carolina have
   6,551 and 6,672 pids respectively with ZERO overlap, so one store's
   sitemap is exactly one store's shelf.

2. The page bootstraps itself from an inline `<script id="init_config">`
   JSON blob that names the API host and namespace (host
   `production-us-1.noq-servers.net`, apiPath `/api/v1/application`,
   franchise oId 780). `GET {api}/products/{pid}` on that host is plain,
   unauthenticated JSON -- no cookie, no token, no WAF challenge -- and
   returns Name, Price, PriceRegular, UnitPrice, MeasureCode, the category
   path and IsAlcohol/IsTobacco flags for that store's instance of the SKU.

So the spider reads init_config once (so a platform redeploy that moves the
API host does not silently break it), walks the store's two sitemaps for
pids, and hits the product endpoint per pid.

ONE STORE ONLY. `STORE_SLUG = "freshmarthatorey"` (Hato Rey, San Juan) is
scraped deliberately rather than all five: the five sitemaps are five
independently-priced copies of one chain's catalogue, and walking all of
them would emit ~33k rows for ~6.5k distinct products, over-weighting this
chain in every downstream average. Add a second store only if per-store
price dispersion within PR becomes something the analysis wants.

Currency USD (Puerto Rico), matching countries.yaml puerto_rico and the
literal "$" the storefront renders.
"""

import json
import re
from datetime import datetime, timezone

import scrapy

_SITEMAP_TMPL = "https://online.freshmartpr.com/{slug}_{n}_sitemap.xml"
_PID_RE = re.compile(r"shop/all\?pid=([0-9a-fA-F-]{36})")
_INIT_CONFIG_RE = re.compile(
    r'id=["\']init_config["\'][^>]*>(.*?)</script>', re.S | re.I
)


class FreshmartPrSpider(scrapy.Spider):
    name = "freshmart_pr"
    allowed_domains = ["online.freshmartpr.com", "production-us-1.noq-servers.net"]
    currency = "USD"
    language = "es"

    STORE_SLUG = "freshmarthatorey"
    SITEMAP_PARTS = (1, 2)
    # Fallback only -- the real values are read from init_config at runtime.
    API_HOST = "https://production-us-1.noq-servers.net"
    API_PATH = "/api/v1/application"

    custom_settings = {
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.15,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "ROBOTSTXT_OBEY": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._api_base = self.API_HOST + self.API_PATH

    async def start(self):
        yield scrapy.Request(
            "https://online.freshmartpr.com/",
            callback=self.parse_init_config,
            dont_filter=True,
        )

    def parse_init_config(self, response):
        m = _INIT_CONFIG_RE.search(response.text)
        if m:
            try:
                cfg = json.loads(m.group(1).strip())
                host = (cfg.get("protocol") or "https://") + (cfg.get("host") or "")
                path = cfg.get("apiPath") or self.API_PATH
                if cfg.get("host"):
                    self._api_base = host.rstrip("/") + path
                    self.logger.info(f"{self.name}: api base from init_config -> {self._api_base}")
            except (json.JSONDecodeError, ValueError):
                self.logger.warning(
                    f"{self.name}: init_config present but unparseable; using fallback API base"
                )
        else:
            self.logger.warning(
                f"{self.name}: no init_config on the homepage; using fallback API base"
            )
        for n in self.SITEMAP_PARTS:
            yield scrapy.Request(
                _SITEMAP_TMPL.format(slug=self.STORE_SLUG, n=n),
                callback=self.parse_sitemap,
                dont_filter=True,
            )

    def parse_sitemap(self, response):
        pids = list(dict.fromkeys(_PID_RE.findall(response.text)))
        self.logger.info(f"{self.name}: {len(pids)} pids in {response.url}")
        for pid in pids:
            yield scrapy.Request(
                f"{self._api_base}/products/{pid}",
                callback=self.parse_product,
                headers={
                    "Accept": "application/json",
                    "Origin": "https://online.freshmartpr.com",
                    "Referer": "https://online.freshmartpr.com/",
                },
                cb_kwargs={"pid": pid},
            )

    def parse_product(self, response, pid: str):
        try:
            payload = response.json()
        except ValueError:
            return
        if payload.get("HasErrors"):
            return
        res = payload.get("Result") or {}
        name = (res.get("Name") or "").strip()
        price = res.get("Price")
        if not name or price in (None, ""):
            return
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if price <= 0:
            return
        cats = [
            c.get("Name")
            for c in (res.get("Categories") or [])
            if isinstance(c, dict) and c.get("Name")
        ]
        yield {
            "product_id": str(res.get("Cd") or res.get("Id") or pid),
            "product_name": name[:500],
            # Categories come parent-last in the payload; reverse so the
            # breadcrumb reads "Household > Cleaning Products".
            "category": " > ".join(reversed(cats)) or None,
            "price": str(price),
            "currency": self.currency,
            "available": bool(res.get("IsAvailableForPurchase", True)),
            "url": (
                f"https://online.freshmartpr.com/online/{self.STORE_SLUG}"
                f"/shop/all?pid={pid}"
            ),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
