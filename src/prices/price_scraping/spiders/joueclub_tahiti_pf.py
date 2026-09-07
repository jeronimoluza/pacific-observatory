"""JoueClub Tahiti baby/toy category card parser."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import scrapy
from parsel import Selector

PRICE_RE = re.compile(r"(\d[\d\s\u00a0\u202f]*)(?:F\s*CFP|FCFP)", re.I)
MAX_PAGES = 2


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _price(text: str | None) -> str | None:
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    return re.sub(r"\D", "", match.group(1))


class JoueclubTahitiPfSpider(scrapy.Spider):
    name = "joueclub_tahiti_pf"
    allowed_domains = ["www.joueclubtahiti.com", "joueclubtahiti.com"]
    start_urls = ["https://www.joueclubtahiti.com/24-coin-des-petits"]
    language = "fr"
    currency = "XPF"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        session = requests.Session()
        session.headers.update({"User-Agent": self.custom_settings["USER_AGENT"]})
        url = self.start_urls[0]
        seen_pages = set()
        page_count = 0
        while url and url not in seen_pages and page_count < MAX_PAGES:
            page_count += 1
            seen_pages.add(url)
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            selector = Selector(text=resp.text)
            for item in self.parse_cards(selector, url):
                yield item
            next_url = selector.css('a[rel="next"]::attr(href)').get()
            if not next_url:
                next_url = selector.css("a::attr(href)").re_first(
                    r"[^\"']*24-coin-des-petits\?page=\d+"
                )
            url = urljoin(url, next_url) if next_url else None

    def parse_cards(self, selector, page_url):
        for card in selector.css("article[data-id-product]"):
            product_id = card.attrib.get("data-id-product")
            if not product_id:
                continue
            headings = [
                _clean(t)
                for t in card.css(
                    "h2::text, h3::text, .elementor-heading-title::text"
                ).getall()
            ]
            headings = [h for h in headings if h]
            if len(headings) >= 2:
                category, name = headings[0], headings[1]
            elif headings:
                category, name = "coin des petits", headings[0]
            else:
                category, name = "coin des petits", ""

            text = _clean(card.xpath("string(.)").get())
            price = _price(text)
            url = card.css('a[href*=".html"]::attr(href)').get()
            link_name = _clean(card.css('a[href*=".html"]::text').get())
            if link_name:
                name = link_name
            if not (product_id and name and price):
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": "Ajouter au panier" in text,
                "url": urljoin(page_url, url) if url else page_url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
