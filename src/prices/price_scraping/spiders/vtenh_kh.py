"""Spider for VTENH Shop Easy (Cambodia), a Spree/Rails marketplace.

Taxon listing pages are server-rendered (12 cards per page, rel="next"
pagination). The /api paths are disallowed by robots.txt, so this spider
reads only the public HTML listings. Each taxon page also links its child
taxons in the nav; children are crawled first so products carry the most
specific category, then the parent sweep picks up anything left over.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class VtenhKhSpider(scrapy.Spider):
    name = "vtenh_kh"
    allowed_domains = ["vtenh.com", "www.vtenh.com"]
    base_url = "https://www.vtenh.com"
    currency = "USD"
    language = "en"
    store_name = "VTENH"
    root_taxons = (
        "others/groceries",
        "groceries/meats-and-vegetables",
        "home-and-living/household-supplies",
        "babies-and-kids/mom-and-baby",
        "lifestyles-and-hobbies/pets/pet-food",
        "beauty-and-personal-care/dental-care",
        "beauty-and-personal-care/body-care",
        "beauty-and-personal-care/health-and-supplements",
        "beauty-and-personal-care/others/hair-products",
    )

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
    }

    _price_re = re.compile(r"\d[\d,]*(?:\.\d+)?")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_taxons = set()
        self.seen_products = set()

    async def start(self):
        for taxon in self.root_taxons:
            yield self._discover_request(taxon)

    def _discover_request(self, taxon):
        self.seen_taxons.add(taxon)
        return scrapy.Request(
            f"{self.base_url}/en/t/cat/{taxon}",
            callback=self.parse_discover,
            priority=1000,
            meta={"taxon": taxon},
        )

    def parse_discover(self, response):
        taxon = response.meta["taxon"]
        prefix = f"/en/t/cat/{taxon}/"
        for href in response.css("a::attr(href)").getall():
            if not href.startswith(prefix) or "?" in href:
                continue
            child = href[len("/en/t/cat/") :].rstrip("/")
            if child not in self.seen_taxons:
                yield self._discover_request(child)
        # Deeper taxons sweep first so products keep the most specific label.
        yield scrapy.Request(
            f"{self.base_url}/en/t/cat/{taxon}?page=1",
            callback=self.parse_listing,
            priority=taxon.count("/"),
            meta={"taxon": taxon},
        )

    def parse_listing(self, response):
        taxon = response.meta["taxon"]
        cards = response.css("div.product-listing > div[id^=product_]")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            product_id = card.attrib["id"].removeprefix("product_")
            if product_id in self.seen_products:
                continue
            href = card.css("a.product-card-link::attr(href)").get()
            name = card.css(".custom-card-title-container p::attr(title)").get()
            price_text = card.css(".card-price-container .main-price::text").get()
            if not href or not name or not name.strip() or not price_text:
                continue
            match = self._price_re.search(price_text)
            if not match:
                continue
            self.seen_products.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": " ".join(name.split()),
                "price": match.group(0).replace(",", ""),
                "currency": self.currency,
                "category": taxon.split("/")[-1].replace("-", " ").lower(),
                "url": urljoin(self.base_url, href.split("?")[0]),
                "language": self.language,
                "store": self.store_name,
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css("link[rel=next]::attr(href)").get()
        if cards and next_href:
            yield response.follow(
                next_href,
                callback=self.parse_listing,
                priority=response.request.priority,
                meta={"taxon": taxon},
            )
