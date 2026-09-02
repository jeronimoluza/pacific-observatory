"""
Spider for Foster's Food Fair Grand Cayman — https://shop.fosters.ky/.

NCR Freshop tenant app_key=fosters (same platform as costuless_ky/_freshop_base).
Live store list under this app_key (GET /2/stores?app_key=fosters) has 9 entries;
only two are consumer-selectable AND carry products: store_id=3748 ("Foster's" /
Camana Bay flagship, 26,894 items) and store_id=6642 ("FOSTER'S Priced Right"
discount banner, 2,768 items) — distinct catalogs and prices per store, verified
live (same pattern documented in _freshop_base.py). This spider walks the larger
flagship catalog (3748); Priced Right is a separate discount banner and would be
a separate source if onboarded.

Currency: KYD, NOT assumed from the bare "$" in the API payload (which carries
no currency_code field, same gap as costuless_ky). Foster's is Cayman's
domestic supermarket chain (not a US chain with a Cayman branch), and
independent evidence (Cayman Resident consumer coverage, retrieved via web
search 2026-09-01) states groceries in Cayman are priced in Cayman dollars
and shoppers paying in USD must apply the exchange rate — e.g. a bag of
onions at "$4.99" is CI$4.99. Set currency=KYD on that basis.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class FostersKySpider(FreshopBaseSpider):
    name = "fosters_ky"
    currency = "KYD"
    language = "en"

    APP_KEY = "fosters"
    STORE_ID = "3748"

    # Fosters' catalog (26,894 items / ~269 pages) is far larger than
    # costuless_ky's (1,574 items / 16 pages), which is small enough to
    # never trip the tenant's own rate limiter. At the base class's
    # defaults (CONCURRENT_REQUESTS_PER_DOMAIN=2, DOWNLOAD_DELAY=0.8) this
    # spider gets a "400 {error_code: 429}" body from Freshop's API around
    # request 23 (skip=2200) — a rate-limit wrapped in an HTTP 400, not a
    # real client error. Slow down and retry that code specifically.
    custom_settings = {
        **FreshopBaseSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 12.0,
        # The tenant's own rate limiter ("400 {error_code:429}") trips at
        # an inconsistent point each run (observed at skip=2200, 3700,
        # 5600, 6100, then immediately at skip=100 on a later run) --
        # consistent with a budget shared across this wave's other
        # concurrently-running agents hitting the same
        # api.freshop.ncrcloud.com host, not something purely a function
        # of this spider's own request rate. It self-heals over time
        # (confirmed live: a direct re-probe of a failing skip value
        # succeeded ~60s later with nothing else changed). RETRY_TIMES is
        # high enough that Scrapy's own delay-spaced retries
        # (RETRY_TIMES * DOWNLOAD_DELAY) can outlast one of these windows
        # instead of giving up inside it.
        "RETRY_TIMES": 40,
        "RETRY_HTTP_CODES": [400, 429, 500, 502, 503, 504, 408],
        # AutoThrottle adapts delay from response LATENCY, and the
        # tenant's rate-limit response is small and fast to return -- so
        # AutoThrottle reads it as "safe to go faster" and shortens the
        # delay right when it needs to lengthen it. Disabling it and
        # pinning a flat delay is what actually avoids tripping the
        # limiter as often (verified: 0.8s/2-concurrent trips it at
        # ~request 23; AutoThrottle-adapted trips by request ~56).
        "AUTOTHROTTLE_ENABLED": False,
    }
