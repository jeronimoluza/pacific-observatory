"""
AB Curacao (Curacao) -- https://aanbodcuracao.com/. Osclass user-classifieds
site ("Aanbod Curacao"): second-hand goods, vehicles, furniture, services.
Prices are shown as "<amount> ANG" in the listing card; "Bespreek met
verkoper" (negotiable) and "Gratis" cards carry no price and are skipped.

Enumeration: /index.php?page=search&iPage=N pages through every ad, 20 per
page, until a page has no cards. Card markup (div.simple-prod): a.title (name
+ item href with ?page=item&id=N), div.category a (category), div.price span.
"""

import re

import scrapy

_ID_RE = re.compile(r"[?&]id=(\d+)")
_PRICE_RE = re.compile(r"^\s*([\d.,]+)\s*(ANG|XCG|NAF)\s*$")
_MAX_PAGES = 200


class AanbodcuracaoCwSpider(scrapy.Spider):
    name = "aanbodcuracao_cw"
    allowed_domains = ["aanbodcuracao.com"]
    currency = "ANG"
    language = "nl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 2,
        # Cloudflare tenant: the repo-pinned chrome120 profile gets a 403,
        # chrome124 clears it (probed 2026-10-12).
        # The repo's random User-Agent rotation mismatches the TLS profile, so
        # turn it off and let curl_cffi send its own chrome124 headers.
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
            "scrapy.downloadermiddlewares.retry.RetryMiddleware": 590,
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": 725,
        },
    }

    def _page(self, n):
        return scrapy.Request(
            f"https://aanbodcuracao.com/index.php?page=search&iPage={n}",
            callback=self.parse_listing,
            cb_kwargs={"n": n},
        )

    async def start(self):
        yield self._page(1)

    def parse_listing(self, response, n):
        cards = response.css("div.simple-prod")
        for card in cards:
            href = card.css("a.title::attr(href)").get() or ""
            id_m = _ID_RE.search(href)
            name = " ".join((card.css("a.title::text").get() or "").split())
            price_txt = " ".join(
                card.css("div.price.isGrid span::text").get("").split()
            )
            price_m = _PRICE_RE.match(price_txt)
            if not (id_m and name and price_m):
                continue
            price = float(price_m.group(1).replace(",", ""))
            if price <= 0:
                continue
            category = " ".join(card.css("div.category a::text").get("").split())
            yield {
                "product_id": id_m.group(1),
                "product_name": name[:500],
                "category": category or None,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
            }
        if cards and n < _MAX_PAGES:
            yield self._page(n + 1)
