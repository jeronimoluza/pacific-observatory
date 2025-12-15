"""
Centralized CSS selectors for all spiders.
This module exports selectors for each spider to be reused in wayback machine scraping.
"""

SPIDER_SELECTORS = {
    "rbpatel": {
        "product_name": [
            "main#main div.product-main h1::text",
        ],
        "price": [
            "div.product-main span[class='woocommerce-Price-amount amount'] bdi::text",
        ],
        "category": [
            "div.product-main span.posted_in a::text",
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
        ],
        "product_id": [
            "span[class='sku']::text",
        ],
    },
    "aldi_au": {
        "product_name": [
            "h1.product-details__title::text",
        ],
        "details": [
            "span.product-details__unit-of-measurement::text"
        ],
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
        raise KeyError(f"Spider '{spider_name}' not found in selectors. Available spiders: {list(SPIDER_SELECTORS.keys())}")
    return SPIDER_SELECTORS[spider_name]
