"""GAMS Africa Shop: bounded HTML catalogue discovery for electronics/IT."""
from __future__ import annotations
import re
from datetime import datetime, timezone
import scrapy

_PRICE = re.compile(r"([0-9][0-9\s,.]*)\s*(?:FCFA|CFA|XOF)", re.I)
def clean(v):
    if isinstance(v, (list, tuple)):
        v = " ".join(map(str, v))
    return " ".join((v or "").replace("\xa0", " ").split())
def price(v):
    m = _PRICE.search(clean(v))
    if not m:
        return None
    amount = m.group(1).replace(" ", "").replace(",", "")
    return amount if float(amount) > 0 else None

class BurkinaFasoGamsAfricaShopSpider(scrapy.Spider):
    name = "burkina_faso_gams_africa_shop"
    allowed_domains = ["shop.gams-africa.com"]
    start_urls = ["https://shop.gams-africa.com/index.php"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        yield from self._parse_cards(response)
        # Prefer explicit catalogue/category/PDP links; carousel cards are not complete inventory.
        seen = set()
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)
            if url in seen or "shop.gams-africa.com" not in url or "page=cart" in url: continue
            seen.add(url)
            label = clean(response.css(f'a[href="{href}"] ::text').get())
            if any(x in (url + " " + label).lower() for x in ("produit", "product", "categorie", "category", "article", "detail")):
                yield response.follow(url, self.parse_catalogue)

    def parse_catalogue(self, response):
        yield from self._parse_cards(response)
        for card in response.css("article, .product, .product-card, [class*='product']"):
            href = card.css("a::attr(href)").get()
            if href and "page=cart" not in href:
                yield response.follow(href, self.parse_product)
        next_url = response.css("a[rel='next']::attr(href), .pagination .next::attr(href)").get()
        if next_url: yield response.follow(next_url, self.parse_catalogue)

    def _parse_cards(self, response):
        seen = set()
        cards = response.css(".product-card, div[class*='product-card']")
        for card in cards:
            href = card.xpath(".//a[contains(@href, 'page=product')]/@href").get()
            name = clean(card.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' product-name ')]//a/text()").get())
            if not name:
                name = clean(card.xpath(".//a[contains(@href, 'page=product')][1]/text()").get())
            value = price(card.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' product-price ')]//text()").getall())
            if not name or not value:
                continue
            url = response.urljoin(href).split("#", 1)[0] if href else response.url
            key = (url, name, value)
            if key in seen:
                continue
            seen.add(key)
            yield {
                "product_id": url.rsplit("id=", 1)[-1] if "id=" in url else name,
                "product_name": name[:500],
                "category": clean(card.css(".product-category::text").get()) or None,
                "price": value,
                "currency": "XOF",
                "country": "Burkina Faso",
                "sector": "electronics_it",
                "url": url,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def parse_product(self, response):
        body = response.css("main, article, .product-detail, .product").get() or ""
        name = clean(response.css("h1::text, .product-title::text, [class*='product-name']::text").get())
        value = price(body)
        if not (name and value and float(value) > 0): return
        yield {"product_id": response.url.rstrip("/").rsplit("/", 1)[-1], "product_name": name[:500],
               "price": value, "currency": "XOF", "country": "Burkina Faso", "sector": "electronics_it",
               "url": response.url.split("?",1)[0], "scraped_at_utc": datetime.now(timezone.utc).isoformat()}
