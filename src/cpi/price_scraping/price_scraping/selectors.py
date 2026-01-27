"""
Centralized CSS selectors for all spiders.
This module exports selectors for each spider to be reused in wayback machine scraping.
Supports fallback selectors - tries each selector in order until one returns data.
"""

from typing import Optional, List
from bs4 import BeautifulSoup

SPIDER_SELECTORS = {
    "rbpatel": {
        "product_name": [
            "main#main div.product-main h1::text",
            "main#main div.product-essential h1::text",
        ],
        "price": [
            "div.product-main span[class='woocommerce-Price-amount amount'] bdi::text",
            "div.product-essential span[class='woocommerce-Price-amount amount'] bdi::text",
        ],
        "category": [
            "div.product-main span.posted_in a::text",
            "div.product-essential span.posted_in a::text",
        ],
        "product_id": [
            "span[class='sku']::text",
        ],
    },
    "mh_online": {
        "product_name": [
            "h1[class='product_title entry-title']::text",
        ],
        "price": [
            "p.price ins span[class='woocommerce-Price-amount amount']::text",
            "p.price span[class='woocommerce-Price-amount amount']::text",
        ],
        "category": [
            "nav[class='woocommerce-breadcrumb'] ul li a::text",
            "ul[class='breadcrumb'] li a span::text",
        ],
        "product_id": [
            "span[class='sku']::text",
            "li[class='meta-sku'] span[class='meta-value']::text",
        ],
    },
    "aldi_au": {
        "product_name": [
            "h1.product-details__title::text",
        ],
        "details": ["span.product-details__unit-of-measurement::text"],
        "category": [
            "div.breadcrumbs__items a::text",
        ],
        "price": [
            "span.base-price__regular span::text",
        ],
    },
    "food_pro": {
        "product_name": [
            "div[class='summary entry-summary'] h2[itemprop='name']::text",
        ],
        "price": [
            "div[class='summary entry-summary'] p.price span[class='woocommerce-Price-amount amount'] bdi::text",
        ],
        "category": [
            "div[class='summary entry-summary'] span.posted_in a::text",
        ],
        "description": [
            "div[class='summary entry-summary'] div[class='woocommerce-product-details__short-description'] p::text",
        ],
    },
    "molisi": {
        "product_name": [
            "div.primary_block h1[itemprop='name']::text",
        ],
        "price": [
            "div.box-info-product span[class='price']::text",
        ],
        "category": [
            "ol[class='breadcrumb'] li a span::text",
        ],
        "product_id": [
            "p#product_reference meta[itemprop='sku']::attr(content)",
        ],
    },
    "samoa_market": {
        "product_name": [
            "article#main-product h1.m5::text",
        ],
        "price": [
            "article#main-product p[class*='f8pr-price s1pr price']::text",
        ],
        "product_id": [
            "article#main-product div.f8pr-codes p::text",
        ],
    },
    "dynamic_vanuatu": {
        "product_name": [
            "div.product__section-content h1[class='product__section-title product-title']::text",
        ],
        "price": [
            "div.product__section-content span[class='price-item price-item--regular']::text",
        ],
        "product_id": [
            "span#variantSku::text",
        ],
    },
    "pickaroo": {
        "product_name": [
            "h1[class='mt-2 product-name']::text",
        ],
        "price": [
            "div.price::text",
        ],
        "category": [
            "div.breadcrumb a::text",
        ],
        "details": ["span.size::text"],
    },
    "hypermart": {
        "product_name": [
            "div.content_det h1::text",
        ],
        "price": [
            "div.content_det h2::text",
        ],
        "category": [
            "div.breadcrumbs a::text",
        ],
    },
    "horizon_farms": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "meta[property='product:price:amount']::attr(content)",
        ],
        "details": [
            "meta[property='og:description']::attr(content)",
        ],
    },
    "makro": {
        "product_name": [
            "h1.font-20.mb-1::text",
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.text-danger.font-20::text",
            "div.price span::text",
        ],
        "details": [
            "div.product-description::text",
        ],
    },
    "thai_huot": {
        "product_name": [
            "div.product-detail h2::text",
            "div.product-info h2::text",
            "h1.product-title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "div.product-detail span.price::text",
            "div.product-info span.price::text",
            "span.product-price::text",
            "div.price::text",
        ],
        "category": [
            "nav.breadcrumb a::text",
            "div.breadcrumb a::text",
            "ul.breadcrumb li a::text",
        ],
        "product_id": [
            "span.sku::text",
            "span.product-sku::text",
        ],
    },
    "rakuten": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
            "title::text",
            "h1.item-name::text",
            "span.item_name::text",
        ],
        "price": [
            "meta[itemprop='price']::attr(content)",
            "meta[itemprop='lowPrice']::attr(content)",
            "meta[property='product:price:amount']::attr(content)",
            "span.price2::text",
            "span[itemprop='price']::text",
        ],
        "category": [
            "div.sdRanking a::text",
            "div.item-breadcrumb a::text",
            "ul.breadcrumb li a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    },
    "yahoo_shopping": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
            "h1.elName::text",
            "h1.ItemName::text",
            "title::text",
        ],
        "price": [
            "meta[property='product:price:amount']::attr(content)",
            "span.elPriceNumber::text",
            "span.ItemPrice::text",
            "p.elPrice::text",
        ],
        "category": [
            "ol.elBreadcrumb a::text",
            "ul.elBreadcrumb a::text",
            "div.ItemCategory a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    },
    "tiki": {
        "product_name": [
            "h1[class*='title']::text",
            "h1.product-name::text",
            "div.product-name::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "div.product-price__current-price::text",
            "div[class*='price-discount__price']::text",
            "span.product-price::text",
            "div.price::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "div[data-view-id='breadcrumb_container'] a.breadcrumb-item span::text",
        ],
        "product_id": [
            "div[data-view-id='pdp_details_view']::attr(data-id)",
        ],
    },
}


def get_selectors(spider_name: str) -> dict:
    """
    Get CSS selectors for a specific spider.

    Args:
        spider_name: Name of the spider (e.g., 'rbpatel', 'mh_online')

    Returns:
        Dictionary of selectors for the spider

    Raises:
        KeyError: If spider name is not found
    """
    if spider_name not in SPIDER_SELECTORS:
        raise KeyError(
            f"Spider '{spider_name}' not found in selectors. Available spiders: {list(SPIDER_SELECTORS.keys())}"
        )
    return SPIDER_SELECTORS[spider_name]


def extract_with_fallback(
    soup: BeautifulSoup, selector_list: List[str]
) -> Optional[str]:
    """
    Extract data from HTML using fallback selectors.
    Tries each selector in order until one returns data.

    Args:
        soup: BeautifulSoup object of the HTML content
        selector_list: List of CSS selectors to try in order

    Returns:
        Extracted text value or None if no selector returns data
    """
    for selector in selector_list:
        try:
            # Handle ::text pseudo-element
            if "::text" in selector:
                clean_selector = selector.replace("::text", "")
                elements = soup.select(clean_selector)
                if elements:
                    texts = [el.get_text(strip=True) for el in elements]
                    value = texts[0] if texts else None
                    if value:
                        return value
            # Handle ::attr() pseudo-element
            elif "::attr(" in selector:
                attr_match = selector.split("::attr(")[1].rstrip(")")
                clean_selector = selector.split("::attr(")[0]
                elements = soup.select(clean_selector)
                if elements:
                    value = elements[0].get(attr_match)
                    if value:
                        return value
            # Regular CSS selector
            else:
                elements = soup.select(selector)
                if elements:
                    value = elements[0].get_text(strip=True)
                    if value:
                        return value
        except Exception:
            # Continue to next selector on error
            continue

    return None
