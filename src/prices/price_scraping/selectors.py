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
            "p.price ins span.woocommerce-Price-amount.amount bdi::text",
            "p.price ins span.woocommerce-Price-amount.amount::text",
            "p.price span.woocommerce-Price-amount.amount bdi::text",
            "p.price span.woocommerce-Price-amount.amount::text",
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
    # --- China ---
    "jianke": {
        "product_name": [
            "div.product-name h1::text",
            "h1::text",
            "meta[name='Keywords']::attr(content)",
        ],
        "price": [
            "dl.bigPrice em::text",
            "dl.assort em::text",
            "span.price::text",
        ],
        "category": [
            "div.crumb_p a::text",
            "div.wid980.crumb_p a::text",
        ],
    },
    "pharmacy_111": {
        "product_name": [
            ".productName::text",
            "p.pro_name::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.price::text",
            "div.pro_price span.price::text",
            "em.price::text",
        ],
        "category": [
            "div.breadcrumb a::text",
            "ol.breadcrumb li a::text",
        ],
    },
    # --- Hong Kong ---
    "mannings": {
        "product_name": [
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
            "div.product-info h1::text",
        ],
        "price": [
            "span.product-price::text",
            "span[class*='price']::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
            "nav.breadcrumb a::text",
        ],
    },
    # --- Mongolia ---
    "citypharm": {
        "product_name": [
            "h1[itemprop='name']::text",
            "h1.te_product_name::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span[itemprop='price']::text",
            "span.oe_price::text",
            "h4.oe_price_h4 span::text",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Taiwan ---
    "cosmed": {
        "product_name": [
            "h1.product-name::text",
            "h1.product-title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.product-price::text",
            "span.price::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Indonesia ---
    "k24klik": {
        "product_name": [
            "h1.product-name::text",
            "h1.product-title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.product-price::text",
            "span.price::text",
            "div.price::text",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Malaysia ---
    "guardian_my": {
        "product_name": [
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
            "div.product-info h1::text",
        ],
        "price": [
            "span.product-price::text",
            "span[class*='price']::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    "doctor_oncall": {
        "product_name": [
            "h1.product-name::text",
            "h1.product-title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.product-price::text",
            "span.price::text",
            "div.price::text",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Philippines ---
    "south_star_drug": {
        "product_name": [
            "h1.product__title::text",
            "h1.product-single__title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.price-item.price-item--regular::text",
            "span.price-item.price-item--sale::text",
            "span.price-item::text",
            "meta[property='og:price:amount']::attr(content)",
        ],
        "category": [
            "nav.breadcrumbs a::text",
            "div.breadcrumb a::text",
            "ol.breadcrumb li a::text",
        ],
    },
    # --- Singapore ---
    "guardian_sg": {
        "product_name": [
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
            "div.product-info h1::text",
        ],
        "price": [
            "span.product-price::text",
            "span[class*='price']::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Thailand ---
    "boots_th": {
        "product_name": [
            "h1.product-name::text",
            "meta[property='og:title']::attr(content)",
            "div.product-info h1::text",
        ],
        "price": [
            "span.product-price::text",
            "span[class*='price']::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "ol.breadcrumb li a::text",
            "div.breadcrumb a::text",
        ],
    },
    "exta": {
        "product_name": [
            "h1.product_title::text",
            "h1::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "p.price span.woocommerce-Price-amount bdi::text",
            "span.woocommerce-Price-amount bdi::text",
            "p.price::text",
        ],
        "category": [
            "nav.woocommerce-breadcrumb a::text",
            "div.breadcrumb a::text",
        ],
    },
    # --- Vietnam ---
    "long_chau": {
        "product_name": [
            "h1[data-test='product_name']::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span[data-test='price']::text",
            "div[data-test='price']::text",
        ],
        "category": [
            "ul.breadcrumb li a::text",
            "nav.breadcrumb a::text",
            "div[class*='breadcrumb'] a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='product_id']::attr(value)",
        ],
    },
    # --- Laos (Khaivai — WooCommerce variant) ---
    "khaivai": {
        "product_name": [
            "h1.mb-2.fs-20.fw-600::text",
            "meta[property='og:title']::attr(content)",
            "h1.fs-20::text",
            "h1::text",
        ],
        "price": [
            # og:price:amount returns "LAK100,000" — spider strips the prefix
            "meta[property='og:price:amount']::attr(content)",
            "strong#chosen_price.h4.fw-600.text-primary::text",
            "span.fs-17.fw-600.text-primary::text",
        ],
        "category": [
            "nav.woocommerce-breadcrumb a::text",
            "div.breadcrumb a::text",
            "a[class*='category']::text",
        ],
        "product_id": [
            "input[name='product_id']::attr(value)",
            "meta[property='product:retailer_item_id']::attr(content)",
        ],
    },
    # --- Laos (Shopify) ---
    "shopping_d": {
        "product_name": [
            "h1.product__title::text",
            "h1.product-single__title::text",
            "h1[class*='product'][class*='title']::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.price-item--regular::text",
            "span.price-item::text",
            "span[class*='price-item']::text",
            "meta[property='og:price:amount']::attr(content)",
        ],
        "category": [
            "nav.breadcrumb a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='product-id']::attr(value)",
            "input[name='id']::attr(value)",
        ],
    },
    # --- Brunei (WooCommerce) ---
    "guan_hock_lee": {
        "product_name": [
            "h1.product_title.entry-title::text",
            "h1.product_title::text",
            "h1.entry-title::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "p.price span.woocommerce-Price-amount bdi::text",
            "p.price span.woocommerce-Price-amount::text",
            "span.woocommerce-Price-amount bdi::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "nav.woocommerce-breadcrumb a::text",
            "span.posted_in a::text",
            "a[rel='tag']::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "span.sku::text",
            "div.product::attr(id)",
        ],
    },
    # --- New Zealand (Shopify) ---
    "bargain_chemist": {
        "product_name": [
            "h1.product__title::text",
            "h1.product-single__title::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span.price-item--regular::text",
            "span.price-item--sale::text",
            "meta[property='og:price:amount']::attr(content)",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "meta[property='product:category']::attr(content)",
            "nav.breadcrumb a::text",
            "a.breadcrumb__link::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='product-id']::attr(value)",
            "input[name='id']::attr(value)",
        ],
    },
    "nz_online_chemist": {
        "product_name": [
            "h1.product__title::text",
            "h1.product-single__title::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span.price-item--regular::text",
            "span.price-item--sale::text",
            "meta[property='og:price:amount']::attr(content)",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "meta[property='product:category']::attr(content)",
            "nav.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='id']::attr(value)",
        ],
    },
    "chemist_plus": {
        "product_name": [
            "h1.product-title::text",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "span.product-price-minimum::text",
            "p.product-price span.money::text",
            "span.money.product-price-minimum::text",
            "meta[property='og:price:amount']::attr(content)",
        ],
        "category": [
            "meta[property='product:category']::attr(content)",
            "nav.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='id']::attr(value)",
        ],
    },
    # --- Mongolia ---
    "nomin": {
        "product_name": [
            "h1::text",
            "title::text",
        ],
        "price": [
            "p.text-xl.font-medium.text-black::text",
            "p.text-xl::text",
            "div.text-xl.font-medium.text-black::text",
        ],
    },
    # --- Vietnam (Co.opmart) ---
    "coopmart": {
        "product_name": [
            "h1::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "div.att-product-detail-latest-price::text",
            "[class*='att-product-detail-latest-price']::text",
            "meta[property='product:price:amount']::attr(content)",
        ],
        "category": [
            "a.breadcrumb-item::text",
            "li.breadcrumb-item a::text",
            "nav.breadcrumb a::text",
        ],
    },
    # --- Taiwan ---
    "pchome_24h": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
            "h1::text",
            "title::text",
        ],
        "price": [
            "div.o-prodPrice__price::text",
            "span.value::text",
            "meta[itemprop='price']::attr(content)",
        ],
        "category": [
            "nav.o-prodMainName__bread a::text",
            "meta[property='product:category']::attr(content)",
        ],
        "product_id": [
            "link[rel='canonical']::attr(href)",
            "meta[property='og:url']::attr(content)",
        ],
    },
    # --- Australia (Coles, Next.js SSR) ---
    "coles_au": {
        "product_name": [
            "h1.product__title::text",
            "h1[data-testid='title']::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "span.price__value[data-testid='pricing']::text",
            "span.price__value::text",
        ],
        "category": [
            "nav[aria-label='breadcrumb'] a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "link[rel='canonical']::attr(href)",
        ],
    },
    # --- Hong Kong (Wellcome, Nuxt SSR) ---
    "wellcome_hk": {
        "product_name": [
            "meta[name='og:title']::attr(content)",
            "meta[property='og:title']::attr(content)",
            "h1::text",
        ],
        "price": [
            "meta[name='product:price:amount']::attr(content)",
            "meta[property='product:price:amount']::attr(content)",
            "span.price::text",
        ],
        "category": [
            "nav.breadcrumb a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "link[rel='canonical']::attr(href)",
            "meta[name='og:url']::attr(content)",
        ],
    },
    # --- South Korea (Emart / SSG.com) ---
    "emart_kr": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
            "h2.cdtl_info_tit::text",
            "h1::text",
        ],
        "price": [
            "span.cdtl_new_price em.ssg_price::text",
            "em.ssg_price::text",
        ],
        "category": [
            "div.cdtl_category_info a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='og:url']::attr(content)",
            "link[rel='canonical']::attr(href)",
        ],
    },
    # --- Samoa (Farmer Joe via SamoaMarket, Shopify) ---
    "farmer_joe": {
        "product_name": [
            "meta[property='og:title']::attr(content)",
            "h1.m5::text",
            "h1.product__title::text",
            "h1::text",
        ],
        "price": [
            "meta[property='product:price:amount']::attr(content)",
            "meta[property='og:price:amount']::attr(content)",
            "span.price-item--regular::text",
            "span.f8pr-price::text",
        ],
        "category": [
            "nav.breadcrumb a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='product-id']::attr(value)",
            "input[name='id']::attr(value)",
        ],
    },
    # --- Malaysia (Jaya Grocer, Shopify Hydrogen-style) ---
    "jaya_grocer": {
        "product_name": [
            "h1.product__title::text",
            "h1::text",
            "meta[property='og:title']::attr(content)",
        ],
        "price": [
            "product-price span.price::text",
            "span.price-item--regular::text",
            "span.price::text",
        ],
        "category": [
            "nav.breadcrumb a::text",
            "ol.breadcrumb a::text",
        ],
        "product_id": [
            "meta[property='product:retailer_item_id']::attr(content)",
            "input[name='product-id']::attr(value)",
            "input[name='id']::attr(value)",
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
