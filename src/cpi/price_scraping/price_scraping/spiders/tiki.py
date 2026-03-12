"""Scrape Tiki.vn (Vietnam) - https://tiki.vn/

Listing-first crawl bounded to seeded retail branches.

Rationale:
- Tiki listing pages already contain sufficient name+price coverage.
- Product-page crawling and broad category traversal cause scope explosion.
"""

import logging
import json
import re
from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import scrapy

logger = logging.getLogger(__name__)


class TikiSpider(scrapy.Spider):
    """Bounded listing-first spider for Tiki.vn."""

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

    MAX_PAGES_PER_BRANCH = 60
    MAX_CONSECUTIVE_EMPTY_PAGES = 2

    _DENY_PATH_PARTS = (
        "cart",
        "checkout",
        "account",
        "login",
        "register",
        "wishlist",
        "bestsellers",
        "khuyen-mai",
        "flash-sale",
        "deal",
        "hot",
        "sale",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()
        self._allowed_root_slugs = {
            self._root_slug_from_url(url)
            for url in self.start_urls
            if self._root_slug_from_url(url)
        }
        self._seen_listing_urls: set[str] = set()
        self._empty_pages_by_branch: dict[str, int] = defaultdict(int)

    def start_requests(self):
        for url in self.start_urls:
            root_slug = self._root_slug_from_url(url)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "branch_root": root_slug,
                    "branch_key": root_slug or url,
                    "page": 1,
                },
            )

    def parse_listing(self, response):
        """
        Parse listing/category pages to extract product cards directly.
        This is more efficient than following individual product links.
        """
        if response.url in self._seen_listing_urls:
            return
        self._seen_listing_urls.add(response.url)

        logger.info("Parsing listing page: %s", response.url)

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

        # Fallback: Tiki often embeds product cards only in __NEXT_DATA__ JSON.
        if items_found == 0:
            for item in self._parse_next_data_products(response):
                items_found += 1
                yield item

        logger.info("Found %s products on listing page", items_found)

        branch_key = response.meta.get("branch_key") or (
            response.meta.get("branch_root") or response.url
        )
        page = response.meta.get("page", 1)

        if items_found == 0:
            self._empty_pages_by_branch[branch_key] += 1
        else:
            self._empty_pages_by_branch[branch_key] = 0

        # Stop exploring a branch that is repeatedly non-productive.
        if self._empty_pages_by_branch[branch_key] >= self.MAX_CONSECUTIVE_EMPTY_PAGES:
            logger.info("Stopping branch %s after consecutive empty pages", branch_key)
            return

        # Follow subcategory links within the same intended root slug set.
        for next_url in self._extract_category_links(response):
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                meta={
                    "branch_root": response.meta.get("branch_root"),
                    "branch_key": branch_key,
                    "page": 1,
                },
            )

        # Pagination: proceed sequentially to avoid crawling deep tails when yield stops.
        if page < self.MAX_PAGES_PER_BRANCH:
            next_page_url = self._next_page_url(response.url, page + 1)
            if next_page_url:
                yield scrapy.Request(
                    next_page_url,
                    callback=self.parse_listing,
                    meta={
                        "branch_root": response.meta.get("branch_root"),
                        "branch_key": branch_key,
                        "page": page + 1,
                    },
                )

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

        # Prefer stable branch category from the seeded root slug.
        category = None
        branch_root = response.meta.get("branch_root")
        if branch_root:
            category = branch_root.replace("-", " ").title()
        if not category:
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

    def _parse_next_data_products(self, response):
        next_data_raw = response.css("script#__NEXT_DATA__::text").get()
        if not next_data_raw:
            return

        try:
            next_data = json.loads(next_data_raw)
        except Exception:
            return

        # Known shape (2026-03): props.initialState.catalog.data is a list of products.
        data = (
            next_data.get("props", {})
            .get("initialState", {})
            .get("catalog", {})
            .get("data")
        )
        if not isinstance(data, list):
            return

        branch_root = response.meta.get("branch_root")
        category = (
            branch_root.replace("-", " ").title()
            if branch_root
            else self._extract_category_from_url(response.url)
        )

        for prod in data:
            if not isinstance(prod, dict):
                continue

            product_name = prod.get("name") or prod.get("title")
            price_val = prod.get("price")
            url_path = prod.get("url") or prod.get("url_path") or prod.get("short_url")
            if not product_name or price_val is None or not url_path:
                continue

            product_url = urljoin(response.url, "/" + str(url_path).lstrip("/"))
            product_id_match = re.search(r"-p(\d+)\.html", product_url)
            if not product_id_match:
                continue

            product_id = product_id_match.group(1)
            if product_id in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(product_id)

            # Price may already be numeric in JSON.
            price = (
                self._clean_price(price_val)
                if isinstance(price_val, str)
                else str(price_val)
            )
            if not price:
                continue

            yield {
                "product_name": str(product_name).strip(),
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": product_url,
                "product_id": product_id,
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

    def _root_slug_from_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        return parts[0] if parts else None

    def _is_denied_url(self, url: str) -> bool:
        lowered = url.lower()
        return any(part in lowered for part in self._DENY_PATH_PARTS)

    def _extract_category_links(self, response) -> list[str]:
        links = response.css("a::attr(href)").getall()
        out: list[str] = []
        for href in links:
            if not href:
                continue
            if "-p" in href or href.endswith(".html"):
                continue
            abs_url = urljoin(response.url, href)
            if "tiki.vn" not in abs_url:
                continue
            if self._is_denied_url(abs_url):
                continue
            # Must look like a category page: /{slug}/c{digits}
            if not re.search(
                r"/[^/]+/c\d+(?:\?.*)?$",
                urlparse(abs_url).path
                + ("?" + (urlparse(abs_url).query) if urlparse(abs_url).query else ""),
            ):
                continue
            root_slug = self._root_slug_from_url(abs_url)
            if self._allowed_root_slugs and root_slug not in self._allowed_root_slugs:
                continue
            out.append(abs_url.split("#", 1)[0])
        return list(dict.fromkeys(out))

    def _next_page_url(self, url: str, page: int) -> str | None:
        if page <= 1:
            return url

        if self._is_denied_url(url):
            return None

        parsed = urlparse(url)
        base = parsed._replace(query="").geturl()
        query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k != "page"
        ]
        query.append(("page", str(page)))
        return f"{base}?{urlencode(query)}"

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
