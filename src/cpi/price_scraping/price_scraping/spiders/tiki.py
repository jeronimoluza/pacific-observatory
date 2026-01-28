"""
Spider for scraping Tiki.vn (Vietnam) - https://tiki.vn/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Start from main category pages
2. Follow pagination and subcategory links
3. Extract product data from listing pages (avoid individual product pages for efficiency)
"""

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urljoin
import logging
import re

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class TikiSpider(CrawlSpider):
    """
    CrawlSpider for Tiki.vn (Vietnam).
    Discovers product pages and extracts price data.
    """

    name = "tiki"
    allowed_domains = ["tiki.vn"]

    # Start with main category pages
    start_urls = [
        "https://tiki.vn/thuc-pham-tuoi-song/c44792",  # Fresh Food
        "https://tiki.vn/do-uong-bia-ruou/c2516",  # Beverages, Beer, Wine
        "https://tiki.vn/banh-keo/c8322",  # Snacks & Candy
        "https://tiki.vn/mi-thuc-pham-an-lien/c8236",  # Noodles & Instant Food
        "https://tiki.vn/dau-an-gia-vi/c8228",  # Cooking Oil & Condiments
        "https://tiki.vn/gao-hat-bot/c8212",  # Rice, Grains, Flour
        "https://tiki.vn/sua-bo-pho-mai/c8194",  # Milk, Butter, Cheese
        "https://tiki.vn/cham-soc-ca-nhan/c1520",  # Personal Care
        "https://tiki.vn/cham-soc-nha-cua/c1882",  # Home Care
    ]

    country = "vietnam"
    currency = "VND"
    language = "vi"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("tiki")

    # Rules for following links and extracting data
    rules = (
        # Follow pagination links
        Rule(
            LinkExtractor(
                allow=r"tiki\.vn/.+/c\d+\?page=\d+",
            ),
            callback="parse_listing",
            follow=True,
        ),
        # Follow category links
        Rule(
            LinkExtractor(
                allow=r"tiki\.vn/.+/c\d+",
                deny=r"(cart|checkout|account|login|register|wishlist)",
            ),
            callback="parse_listing",
            follow=True,
        ),
        # Follow product links
        Rule(
            LinkExtractor(
                allow=r"tiki\.vn/.+-p\d+\.html",
                deny=r"(cart|checkout|account|login|register|wishlist)",
            ),
            callback="parse_product",
            follow=False,
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def parse_listing(self, response):
        """
        Parse listing/category pages to extract product cards directly.
        This is more efficient than following individual product links.
        """
        logger.info(f"Parsing listing page: {response.url}")

        # Try to extract products from listing cards
        product_cards = response.css(
            "div[data-view-id='product_list_container'] a[href*='-p']"
        )

        if not product_cards:
            # Fallback selectors for product cards
            product_cards = response.css("div.product-item a[href*='-p']")

        items_found = 0
        for card in product_cards:
            item = self._parse_product_card(card, response)
            if item:
                items_found += 1
                yield item

        logger.info(f"Found {items_found} products on listing page")

    def _parse_product_card(self, card, response):
        """
        Extract product data from a product card on listing page.
        """
        # Extract product URL
        product_url = card.css("::attr(href)").get()
        if not product_url:
            return None

        # Make absolute URL
        product_url = urljoin(response.url, product_url)

        # Extract product ID from URL (format: -p{id}.html)
        product_id_match = re.search(r"-p(\d+)\.html", product_url)
        if not product_id_match:
            return None

        product_id = product_id_match.group(1)

        # Skip if already scraped
        if product_id in self.scraped_product_ids:
            return None
        self.scraped_product_ids.add(product_id)

        # Extract product name from card
        product_name = (
            card.css("div.name::text").get()
            or card.css("div.title::text").get()
            or card.css("::attr(title)").get()
        )

        # Extract price from card
        price_text = (
            card.css("div.price-discount__price::text").get()
            or card.css("div.price::text").get()
            or card.css("span.price::text").get()
        )

        # Clean price
        price = self._clean_price(price_text) if price_text else None

        # Try to extract category from breadcrumb or URL
        category = self._extract_category_from_url(response.url)

        if product_name and price:
            return {
                "product_name": product_name.strip(),
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": product_url,
                "product_id": product_id,
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        return None

    def parse_product(self, response):
        """
        Parse individual product page and extract relevant data.
        """
        # Extract product ID from URL
        product_id_match = re.search(r"-p(\d+)\.html", response.url)
        if not product_id_match:
            logger.warning(f"Could not extract product ID from {response.url}")
            return

        product_id = product_id_match.group(1)

        # Skip if already scraped
        if product_id in self.scraped_product_ids:
            return
        self.scraped_product_ids.add(product_id)

        # Initialize extractor with fallback selectors
        extractor = SelectorExtractor(response, logger)

        # Extract product information using fallback selectors
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price_text = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS["category"], method="getall"
        )

        # Clean price
        price = self._clean_price(price_text) if price_text else None

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": " > ".join(category) if category else None,
                "price": price,
                "currency": self.currency,
                "url": response.url,
                "product_id": product_id,
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")

    def _clean_price(self, price_str):
        """
        Clean Vietnamese price string.
        Examples: "100.000₫", "100.000 ₫", "100000đ"
        """
        if not price_str:
            return None

        # Remove currency symbols and spaces
        cleaned = re.sub(r"[₫đ\s]", "", str(price_str))
        # Remove dots used as thousand separators in Vietnamese
        cleaned = cleaned.replace(".", "")
        # Extract numeric value
        match = re.search(r"(\d+)", cleaned)
        return match.group(1) if match else None

    def _extract_category_from_url(self, url):
        """
        Extract category name from URL.
        Example: https://tiki.vn/thuc-pham-tuoi-song/c44792 -> "thuc-pham-tuoi-song"
        """
        match = re.search(r"tiki\.vn/([^/]+)/c\d+", url)
        if match:
            category_slug = match.group(1)
            # Convert slug to readable format
            return category_slug.replace("-", " ").title()
        return None
