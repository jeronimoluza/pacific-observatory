"""Afrikonet (Sierra Leone) -- https://www.afrikonet.sl/. Bespoke
marketplace platform (Bootstrap-based, not Shopify/WooCommerce/PrestaShop/
OpenCart). Category listing pages render price inline
(`.product__new-price` inside each `.product[data-link]` card), so this is
a plain Tier 1A scrapy_html crawl over the category tree -- no PDP fetch
needed.

161 categories collected from the homepage nav, spanning most of the
COICOP basket (groceries, produce, pharmacy, electronics, home, fashion,
toys, automotive, books). Category pages are small (single page each, no
further pagination seen: ?page=2 on air-conditioners returns zero items),
so the wide category list is the enumeration surface rather than
within-category pagination.

Currency: displayed as "Le" (Leone symbol) on every price; verified the
magnitude implies the NEW Leone (SLE, redenominated 2022) not the old SLL
-- a 12000BTU air conditioner at Le8,000.00 is a plausible SLE price
(~USD 360 at ~22 SLE/USD) but would be absurd as SLL (~USD 0.36). Matches
countries.yaml's `SLE` for Sierra Leone.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

CATEGORIES = [
    "air-conditioners", "airpods", "allergy-medications", "antacids", "anti-virus",
    "arts-crafts", "automotive-transportation", "baby-clothing",
    "baby-diapers-and-care-products", "baby-essentials", "baby-food-feeding-items",
    "baby-products", "bar-soap", "batteries", "beading-jewelry-making",
    "beauty-and-cosmetics", "beauty-personal-care", "beverages", "bluetooth-speaker",
    "body-lotion", "body-wash", "books", "books-stationery-office-supplies",
    "bracelet", "building-materials", "cables-wires", "cake", "camera-photography",
    "car-electronics", "car-parts-accessories", "cars", "chocolates",
    "cleaning-and-sanitation", "cloud-services-hosting", "cold-flu-remedies",
    "detergents", "detergents-02", "digital-products", "diy-craft-kits",
    "dust-bin-bags", "e-books", "earrings", "educational-toys", "eggs",
    "electrical-equipments", "electrical-tools", "electronics-and-gadgets",
    "extension-cord", "facial-cream", "fantasy-books", "fashion",
    "financial-books", "first-aid-wellness-kit", "fitness-equipments", "flowers",
    "food-and-drinks", "fragrances", "fresh-produce", "fruits", "furniture",
    "gardening", "gardening-tools", "generator", "gifts", "grease",
    "groceries-food", "grooming-tools", "gym-supplements", "hair-band",
    "hair-brush", "hair-spray", "haircare", "hand-soap", "health-and-fitness",
    "home-and-living", "home-and-office-decor", "home-appliances", "home-decor",
    "home-furniture", "home-improvement", "home-textile", "household-essentials",
    "ice-cream", "it-hardware", "jewelries", "kids-furniture-decorations",
    "kitchenware-appliances", "knitting-crochet", "laptops-tablets", "light-bulbs",
    "liquid-soap", "makeup-and-cosmetics", "makeup-kits", "medications",
    "motivational-books", "motorbikes-scooters", "necklace",
    "nutrition-supplements", "office-furniture", "office-stationary",
    "office-textile", "outdoor-furniture", "outdoor-gear",
    "packaged-foods-snacks", "pain-relievers", "paint-wallpaper",
    "painting-drawing-supplies", "perfume", "pet-food", "pet-furniture-bedding",
    "pet-health-grooming", "pet-supplies", "pet-toys-accessories",
    "plants-pots-planters", "playstation", "plumbing-equipment", "power-strips",
    "prayer-items", "printers-office-machines", "produce", "refrigerators",
    "roses", "school-supplies", "scrapbooking-paper-craft", "skincare",
    "smartphones-accessories", "sneakers", "soap", "socks", "soft-drink",
    "software", "soil-fertilizers", "solar", "songs", "sports-apparel",
    "sports-outdoors", "stationery", "strollers-car-seats",
    "suitcases-backpacks", "switches-sockets", "tablets-pills", "team-sports",
    "technology-software", "teddy-bear", "tires-wheels", "tissue",
    "toys-for-kids", "toys-games", "travel-accessories",
    "travel-bags-luggage", "travel-electronics", "travel-luggage",
    "vacuum-cleaners", "vegetables", "vehicle-care", "vitamins-supplements",
    "washing-machines", "watches", "water-sports-gear",
    "web-development-tools", "yoga-meditation-accessories",
]

_PRICE_CLEAN = re.compile(r"[^0-9.]")


class AfrikonetSlSpider(scrapy.Spider):
    name = "afrikonet_sl"
    allowed_domains = ["afrikonet.sl"]
    currency = "SLE"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"https://www.afrikonet.sl/category/{cat}",
                callback=self.parse_listing,
                meta={"cat": cat},
            )

    def parse_listing(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        cat = response.meta["cat"]
        for card in soup.select(".product[data-link]"):
            name_el = card.select_one(".product__title")
            price_el = card.select_one(".product__new-price")
            url = card.get("data-link")
            if not name_el or not price_el or not url:
                continue
            price = _PRICE_CLEAN.sub("", price_el.get_text(strip=True))
            name = name_el.get_text(strip=True)
            if not name or not price:
                continue
            try:
                if float(price) == 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield {
                "product_id": url.rstrip("/").rsplit("-", 1)[-1],
                "product_name": name[:500],
                "category": cat,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
