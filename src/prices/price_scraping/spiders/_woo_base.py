"""
Shared base class for WooCommerce Store API spiders.

Many independent WooCommerce/WordPress storefronts expose the public,
unauthenticated Store API at /wp-json/wc/store/v1/products (a few
non-standard installs use ?rest_route=/wc/store/v1/products or the older
/wp-json/wc/store/products namespace instead). We paginate per_page=100
until a short/empty page is returned.

WooCommerce returns integer prices in the smallest currency unit; each
product's prices.currency_minor_unit tells us how many places to shift
(e.g. minor_unit=2 means 2430 -> 24.30, minor_unit=0 needs no division).
prices.currency_code is authoritative over the country's declared currency.

Subclasses set: name, allowed_domains, currency, language, BASE_URL, and
optionally CATEGORY_ID (to scope a general marketplace to a food category
when the unfiltered endpoint isn't worth walking whole).

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PER_PAGE = 100
MAX_PAGES = 200  # safety cap

# `.woocommerce-Price-amount` / `p.price` elements inside these ancestor
# classes belong to a related/upsell products carousel, not the page's own
# product — skip them when hunting for the primary price element.
_EXCLUDED_PRICE_ANCESTOR_CLASSES = {
    "related",
    "upsells",
    "up-sells",
    "cross-sells",
    "products",
}
_OUT_OF_STOCK_WORDS = (
    "out of stock",
    "outofstock",
    "sold out",
    "rupture",
    "agotado",
    "épuisé",
    "epuise",
    "sin stock",
)


class WooBaseSpider(scrapy.Spider):
    name = None
    BASE_URL: str = ""
    CATEGORY_ID: str | int | None = None
    # Set when the API's currency_code field is known-wrong for this tenant
    # (e.g. a site misconfiguration) so we trust our own probed currency.
    FORCE_CURRENCY: str | None = None
    # Set when the API reports prices in a non-ISO subunit (e.g. Iranian
    # Toman, currency_code "IRT", minor_unit 0) that must be scaled to the
    # ISO currency actually emitted (Toman -> Rial is x10).
    PRICE_MULTIPLIER: float = 1
    # The subunit code PRICE_MULTIPLIER corrects for. Set it alongside the
    # multiplier so the scaling only fires while the API is still reporting
    # that code: a tenant that later fixes its currency_code would otherwise
    # start emitting silently 10x prices, with nothing in the row to show it.
    PRICE_MULTIPLIER_CURRENCY: str | None = None
    # Set when the repo-wide pinned curl_cffi profile (settings.py
    # IMPERSONATE_BROWSERS, currently chrome120) 403s on this tenant's WAF but
    # a different browser profile clears it (confirmed case: cassandraonlinemarket_ht
    # 403s on chrome120, 200s on chrome124/123/safari17_0). None preserves the
    # prior behaviour (repo-wide pinned profile) for every other subclass.
    IMPERSONATE_PROFILE: str | None = None

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

    def _page_url(self, page: int) -> str:
        sep = "&" if "?" in self.BASE_URL else "?"
        url = f"{self.BASE_URL}{sep}per_page={PER_PAGE}&page={page}"
        if self.CATEGORY_ID is not None:
            url += f"&category={self.CATEGORY_ID}"
        return url

    def _meta(self, page: int) -> dict:
        meta = {"page": page}
        if self.IMPERSONATE_PROFILE:
            meta["impersonate"] = self.IMPERSONATE_PROFILE
        return meta

    async def start(self):
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            meta=self._meta(1),
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"{self.name} page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt),
                callback=self.parse_page,
                meta=self._meta(nxt),
            )

    def _item(self, p: dict):
        prices = p.get("prices") or {}
        raw = prices.get("price")
        if raw is None:
            return None
        reported = prices.get("currency_code")
        scaled = self.PRICE_MULTIPLIER != 1 and (
            self.PRICE_MULTIPLIER_CURRENCY is None
            or reported == self.PRICE_MULTIPLIER_CURRENCY
        )
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            value = int(raw) / (10**minor) if minor else int(raw)
            if scaled:
                value = value * self.PRICE_MULTIPLIER
        except (TypeError, ValueError):
            value = raw
        cats = p.get("categories") or []
        cat = (
            " > ".join(
                html.unescape(c.get("name"))
                for c in cats
                if isinstance(c, dict) and c.get("name")
            )
            or None
        )
        return {
            "product_id": str(p.get("sku") or p.get("id")),
            "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
            "category": cat,
            "price": str(value),
            "currency": self.FORCE_CURRENCY
            or (self.currency if scaled else reported)
            or self.currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": p.get("permalink") or "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Archived storefront HTML parser — used only by the Wayback/Common
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (_item, above) reads the JSON Store API; archives only hold the
    # human-facing product-detail page, a different surface entirely. This
    # walks a fallback chain across the 56 subclasses' varied WP themes:
    # JSON-LD Product node -> OpenGraph/product meta tags -> WooCommerce
    # DOM markup.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived WooCommerce product-detail page.

        Pure function: no Scrapy Response, no network, no class state.
        Yields 0 or 1 row; yields nothing when the page isn't a product
        page. Does NOT stamp scraped_at_utc — the backfiller stamps the
        snapshot time itself.
        """
        soup = BeautifulSoup(html_text, "html.parser")
        row = (
            cls._woo_row_from_json_ld(soup, url)
            or cls._woo_row_from_meta_tags(soup, url)
            or cls._woo_row_from_dom(soup, url)
        )
        if row is None:
            return
        yield row

    @staticmethod
    def _woo_normalize_price(raw) -> str | None:
        """Strip currency symbols/thousands seps; EU (1.234,56) and US (1,234.56)."""
        if raw is None:
            return None
        s = re.sub(r"[^\d.,\-]", "", str(raw))
        if not s:
            return None
        has_comma, has_dot = "," in s, "." in s
        if has_comma and has_dot:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")  # comma = decimal sep
            else:
                s = s.replace(",", "")  # comma = thousands sep
        elif has_comma:
            tail = s.split(",")[-1]
            s = s.replace(",", ".") if len(tail) == 2 else s.replace(",", "")
        try:
            return str(float(s))
        except ValueError:
            return None

    @staticmethod
    def _woo_iter_json_ld_nodes(data):
        if isinstance(data, list):
            for item in data:
                yield from WooBaseSpider._woo_iter_json_ld_nodes(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from WooBaseSpider._woo_iter_json_ld_nodes(item)

    @classmethod
    def _woo_row_from_json_ld(cls, soup: BeautifulSoup, url: str) -> dict | None:
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            text = script.string or script.get_text()
            if not text:
                continue
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            for node in cls._woo_iter_json_ld_nodes(data):
                if not isinstance(node, dict) or node.get("@type") != "Product":
                    continue
                row = cls._woo_row_from_product_node(node, url)
                if row is not None:
                    return row
        return None

    @classmethod
    def _woo_row_from_product_node(cls, node: dict, url: str) -> dict | None:
        name = node.get("name")
        if not name:
            return None
        offers = node.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            offers = {}
        price = offers.get("price")
        currency = offers.get("priceCurrency")
        if price is None or not currency:
            spec = offers.get("priceSpecification")
            if isinstance(spec, list):
                spec = spec[0] if spec else None
            if isinstance(spec, dict):
                price = price if price is not None else spec.get("price")
                currency = currency or spec.get("priceCurrency")
        norm_price = cls._woo_normalize_price(price) if price is not None else None
        if not norm_price:
            return None
        row: dict = {
            "product_name": html.unescape(str(name)).strip()[:500],
            "price": norm_price,
            "url": offers.get("url") or node.get("url") or url,
        }
        sku = node.get("sku")
        if sku:
            row["product_id"] = str(sku)
        if currency:
            row["currency"] = str(currency)
        category = node.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        if category:
            row["category"] = str(category)
        availability = offers.get("availability")
        if availability:
            low = str(availability).lower()
            if "outofstock" in low:
                row["available"] = False
            elif "instock" in low:
                row["available"] = True
        return row

    @classmethod
    def _woo_row_from_meta_tags(cls, soup: BeautifulSoup, url: str) -> dict | None:
        def meta_content(prop: str) -> str | None:
            tag = soup.find("meta", attrs={"property": prop}) or soup.find(
                "meta", attrs={"name": prop}
            )
            return tag.get("content") if tag else None

        price_raw = meta_content("product:price:amount")
        price = cls._woo_normalize_price(price_raw) if price_raw else None
        if not price:
            return None
        name = cls._woo_extract_product_name(soup)
        if not name:
            return None
        row: dict = {
            "product_name": html.unescape(name).strip()[:500],
            "price": price,
            "url": meta_content("og:url") or url,
        }
        currency = meta_content("product:price:currency")
        if currency:
            row["currency"] = currency
        availability = meta_content("product:availability")
        if availability:
            low = availability.lower().replace(" ", "")
            if "outofstock" in low:
                row["available"] = False
            elif "instock" in low:
                row["available"] = True
        return row

    @classmethod
    def _woo_row_from_dom(cls, soup: BeautifulSoup, url: str) -> dict | None:
        name = cls._woo_extract_product_name(soup)
        price_el = cls._woo_select_price_element(soup)
        if not name or price_el is None:
            return None
        price = cls._woo_normalize_price(cls._woo_price_text(price_el))
        if not price:
            return None
        row: dict = {
            "product_name": html.unescape(name).strip()[:500],
            "price": price,
            "url": url,
        }
        sku_el = soup.select_one(".sku")
        if sku_el and sku_el.get_text(strip=True):
            row["product_id"] = sku_el.get_text(strip=True)
        cat_el = soup.select_one(".posted_in")
        if cat_el:
            cat_text = re.sub(r"^\S+\s*:\s*", "", cat_el.get_text(" ", strip=True))
            if cat_text:
                row["category"] = cat_text
        stock_el = soup.select_one(".stock")
        if stock_el:
            stock_text = stock_el.get_text(strip=True).lower()
            if stock_text:
                row["available"] = not any(w in stock_text for w in _OUT_OF_STOCK_WORDS)
        return row

    @staticmethod
    def _woo_extract_product_name(soup: BeautifulSoup) -> str | None:
        el = (
            soup.select_one(".product_title")
            or soup.select_one("h1.entry-title")
            or soup.find("h1")
        )
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
        tag = soup.find("meta", attrs={"property": "og:title"})
        if tag and tag.get("content"):
            return re.split(r"\s[|–-]\s", tag["content"])[0].strip()
        return None

    @staticmethod
    def _woo_select_price_element(soup: BeautifulSoup):
        for el in soup.select("p.price, span.price"):
            parent_classes: set[str] = set()
            for parent in el.parents:
                classes = parent.get("class") if hasattr(parent, "get") else None
                if classes:
                    parent_classes.update(classes)
            if parent_classes & _EXCLUDED_PRICE_ANCESTOR_CLASSES:
                continue
            return el
        return None

    @staticmethod
    def _woo_price_text(el) -> str:
        ins = el.select_one("ins")
        if ins is not None:
            return ins.get_text(" ", strip=True)
        return el.get_text(" ", strip=True)
