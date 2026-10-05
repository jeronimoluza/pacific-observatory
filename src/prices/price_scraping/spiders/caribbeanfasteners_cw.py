"""
Caribbean Fasteners Webshop (Curacao) -- https://caribbean-fasteners.com/en/

Sylius storefront, "Curacao | Free standard delivery". Hardware, safety,
tools, machines, chemicals, ladders and window/door hardware, priced in ANG
(shown as "ANG 341.48"). Server-rendered; open robots.txt.

Walks the top-level /en/taxons/<slug> listings (parent taxons include their
children) with ?page=N until a page adds no new product. Variant products
show "From ANG x" (the cheapest variant); that minimum is what we record.

Page family: listing.
"""

import re

import scrapy

TAXONS = [
    "fasteners",
    "window-door-hardware",
    "safety",
    "tools",
    "machines",
    "machine-tool-accessories",
    "chemicals",
    "parts",
    "ladders-scaffolds-material-handling",
]
MAX_PAGES = 200


class CaribbeanFastenersCwSpider(scrapy.Spider):
    name = "caribbeanfasteners_cw"
    allowed_domains = ["caribbean-fasteners.com"]
    currency = "ANG"
    language = "en"
    BASE = "https://caribbean-fasteners.com"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
    }

    def start_requests(self):
        self.seen = set()
        for t in TAXONS:
            yield self._req(t, 1)

    def _req(self, taxon, page):
        url = f"{self.BASE}/en/taxons/{taxon}" + (f"?page={page}" if page > 1 else "")
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={"taxon": taxon, "page": page},
            dont_filter=True,
        )

    def parse_listing(self, response):
        taxon, page = response.meta["taxon"], response.meta["page"]
        new = 0
        for card in response.css("#products div.card"):
            href = card.css("a.sylius-product-name::attr(href)").get()
            name = card.css("a.sylius-product-name::text").get()
            ptxt = " ".join(card.css("div.sylius-product-price::text").getall())
            m = re.search(r"([\d,]+\.\d+|[\d,]+)", ptxt)
            if not (href and name and m):
                continue
            url = response.urljoin(href)
            if url in self.seen:
                continue
            self.seen.add(url)
            new += 1
            yield {
                "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name.strip(),
                "price": m.group(1).replace(",", ""),
                "currency": self.currency,
                "category": taxon.replace("-", " "),
                "url": url,
                "language": self.language,
            }
        if new and page < MAX_PAGES:
            yield self._req(taxon, page + 1)
