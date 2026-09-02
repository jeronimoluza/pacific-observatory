"""
Spider for Hurley's Marketplace (Grand Cayman) — https://shop.hurleys.ky/.

NCR Freshop tenant app_key=hurleys (same platform/pattern as costuless_ky
and fosters_ky). GET /2/stores?app_key=hurleys lists 4 entries; two are
consumer-selectable and product-bearing: store_id=1874 ("Hurley's", the
flagship store, 17,074 items — used here) and store_id=7634 ("Hurley's
DASH", their delivery-service pricing, 17,048 items, largely overlapping
catalogue). Only the flagship store is onboarded to avoid double-counting
the same shelf under two banners (same reasoning as fosters_ky's Priced
Right exclusion).

Currency: KYD. Same API gap as fosters_ky/costuless_ky (no currency_code
field, plain "$" price string). Hurley's Marketplace is a wholly domestic
Cayman chain (not a US chain with a local branch), and independent
evidence (Cayman Resident consumer coverage, retrieved via web search
2026-09-01) states Cayman grocery prices are quoted in Cayman Islands
dollars. Set currency=KYD on that basis, consistent with fosters_ky.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class HurleysKySpider(FreshopBaseSpider):
    name = "hurleys_ky"
    currency = "KYD"
    language = "en"

    APP_KEY = "hurleys"
    STORE_ID = "1874"

    # Same tenant-side rate-limit behaviour observed on fosters_ky's larger
    # catalogue (a "400 {error_code:429}" body, fast enough that
    # AutoThrottle reads it as "go faster" instead of backing off) — pin a
    # flat delay and disable AutoThrottle rather than rediscover this.
    custom_settings = {
        **FreshopBaseSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 3.0,
        "RETRY_TIMES": 60,
        "RETRY_HTTP_CODES": [400, 429, 500, 502, 503, 504, 408],
        "AUTOTHROTTLE_ENABLED": False,
    }
