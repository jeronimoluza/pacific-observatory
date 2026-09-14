"""Merchant-attributed UYU offers from Lo+Justo product detail pages."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus, urlsplit, urlunsplit

import scrapy


DEFAULT_QUERY = "iphone"


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _uyu_amount(value: object) -> Decimal | None:
    """Parse a displayed Uruguayan-peso amount, never a US$ amount."""
    text = _clean(value)
    match = re.fullmatch(r"\$\s*([0-9][0-9.]*)(?:,([0-9]{1,2}))?", text)
    if not match:
        return None
    normalized = match.group(1).replace(".", "")
    if match.group(2):
        normalized += "." + match.group(2)
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    return amount if amount > 0 else None


def _merchant_url(value: object) -> str | None:
    parsed = urlsplit(_clean(value))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.hostname in {"lomasjusto.uy", "www.lomasjusto.uy"}:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.query, ""))


def _merchant_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _source_product_id(url: str) -> str | None:
    parsed = urlsplit(url)
    path = parsed.path.strip("/")
    return path or None


def _price_date(response) -> str | None:
    text = _clean(
        " ".join(response.css(".det .specs::text, .det .specs ::text").getall())
    )
    match = re.search(r"precios del\s+(\d{2})/(\d{2})/(\d{4})", text, re.I)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def iter_offer_rows(response, scraped_at: str):
    """Yield atomic UYU offers from detail rows; aggregate floors are ignored."""
    source_url = response.css('link[rel="canonical"]::attr(href)').get() or response.url
    source_id = _source_product_id(source_url)
    product_name = _clean(response.css(".det h1::text").get())
    category = source_id.split("/", 1)[0] if source_id and "/" in source_id else None
    if not (source_id and product_name):
        return

    price_date = _price_date(response)
    for offer in response.css(".det .ofertas .of"):
        merchant = _clean(offer.css(".tienda::text").get())
        price = _uyu_amount(offer.css(".p::text").get())
        url = _merchant_url(offer.css("a.ir::attr(href)").get())
        merchant_key = _merchant_key(merchant)
        if not (merchant_key and price and url):
            continue

        yield {
            "product_id": f"{source_id}:{merchant_key}",
            "source_product_id": source_id,
            "product_name": product_name[:500],
            "merchant": merchant,
            "price": format(price, "f"),
            "currency": "UYU",
            "country": "Uruguay",
            "category": category,
            "channel": "price_comparison",
            "price_date": price_date,
            "url": url,
            "source_url": source_url,
            "scraped_at_utc": scraped_at,
        }


class UruguayLomasjustoUySpider(scrapy.Spider):
    name = "uruguay_lomasjusto_uy"
    allowed_domains = ["lomasjusto.uy"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 2,
    }

    def __init__(self, query: str = DEFAULT_QUERY, max_products: int = 24, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = _clean(query) or DEFAULT_QUERY
        self.max_products = max(1, int(max_products))
        self._seen_offers: set[tuple[str, str]] = set()

    async def start(self):
        yield scrapy.Request(
            f"https://lomasjusto.uy/buscar?q={quote_plus(self.query)}",
            callback=self.parse_listing,
        )

    def parse_listing(self, response):
        """Use listing pages only for discovery; their `desde` prices are aggregates."""
        links = response.css(".lista .grid a.card::attr(href)").getall()
        for href in links[: self.max_products]:
            yield response.follow(href, callback=self.parse_product)

    def parse_product(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in iter_offer_rows(response, scraped_at):
            dedupe_key = (row["source_product_id"], row["url"])
            if dedupe_key in self._seen_offers:
                continue
            self._seen_offers.add(dedupe_key)
            yield row
