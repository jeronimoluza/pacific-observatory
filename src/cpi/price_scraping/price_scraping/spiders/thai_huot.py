"""
Spider for scraping Thai Huot (Cambodia) - https://thaihuotsupermarket.com/

Site uses a React SPA backed by a REST API at https://api.thaihuotsupermarket.com/api
(discovered 2026-05).  Direct HTTP requests fail with TLS resets / 403 because
Cloudflare (or equivalent) bot-protection blocks non-browser TLS fingerprints.

Strategy:
  1. Load https://thaihuotsupermarket.com/ via Playwright (real Chromium) to obtain
     Cloudflare clearance cookies and a matching TLS fingerprint.
  2. From inside that authenticated browser context, call the backing API via
     page.evaluate() / fetch() so all requests carry the cleared cookies.
  3. GET /api/categories         — fetch full category list
  4. GET /api/categories/{id}/products?page=N&per_page=50 — paginated products
  5. Yield one item per product: product_name, price (USD), category, product_id.

Pagination: iterate pages until an empty products array is returned or
MAX_PAGES_PER_CATEGORY is reached.
"""

import logging
from datetime import datetime

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

STOREFRONT_URL = "https://thaihuotsupermarket.com/"
API_BASE = "https://api.thaihuotsupermarket.com/api"
PER_PAGE = 50
MAX_PAGES_PER_CATEGORY = 10


class ThaiHuotSpider(scrapy.Spider):
    """
    Playwright spider for Thai Huot (Cambodia).
    Boots a real Chromium context to bypass Cloudflare, then calls the backing
    REST API via in-browser fetch() so all requests share the cleared session.
    """

    name = "thai_huot"
    allowed_domains = ["thaihuotsupermarket.com", "api.thaihuotsupermarket.com"]
    country = "cambodia"
    currency = "USD"

    custom_settings = {
        # Playwright is heavy — keep concurrency low to avoid browser exhaustion.
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": False,
        # Override global autothrottle for this spider so DOWNLOAD_DELAY holds.
        "AUTOTHROTTLE_ENABLED": False,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,
    }

    def start_requests(self):
        """
        Yield a single Playwright request to the storefront.  Cloudflare
        challenge (if any) is resolved during page load; once the page is
        rendered we call the API from inside the browser context.
        """
        yield scrapy.Request(
            STOREFRONT_URL,
            callback=self.parse_storefront,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_goto_kwargs": {
                    "wait_until": "networkidle",
                },
                # Wait a bit after network idle to let any CF challenge finish.
                "playwright_page_methods": [
                    PageMethod("wait_for_timeout", 3000),
                ],
            },
            errback=self.errback,
        )

    async def parse_storefront(self, response):
        """
        Called once after the storefront loads in a real Chromium context.
        Uses page.evaluate() to call the API from inside the browser so the
        requests share the same Cloudflare-cleared cookies/fingerprint.
        """
        page = response.meta["playwright_page"]

        try:
            # --- Fetch category list via in-browser fetch() ---
            logger.info("Fetching categories from API …")
            categories_raw = await page.evaluate(
                """async () => {
                    const r = await fetch('https://api.thaihuotsupermarket.com/api/categories',
                                         {credentials: 'include'});
                    return await r.json();
                }"""
            )
        except Exception as exc:
            logger.error("Failed to fetch categories: %s", exc)
            await page.close()
            return

        # API may return {"data": [...]} or a plain list.
        if isinstance(categories_raw, dict):
            categories = categories_raw.get("data", [])
        elif isinstance(categories_raw, list):
            categories = categories_raw
        else:
            logger.error(
                "Unexpected categories response shape: %r", str(categories_raw)[:300]
            )
            await page.close()
            return

        if not categories:
            logger.warning("No categories returned — check API response.")
            await page.close()
            return

        logger.info("Found %d categories; starting product scrape …", len(categories))

        scraped_at = datetime.utcnow().isoformat()

        for cat in categories:
            cat_id = cat.get("id")
            cat_name = cat.get("name", str(cat_id))
            if not cat_id:
                continue

            for page_num in range(1, MAX_PAGES_PER_CATEGORY + 1):
                try:
                    products_raw = await page.evaluate(
                        """async ([catId, pageNum, perPage]) => {
                            const url = `https://api.thaihuotsupermarket.com/api/categories/${catId}/products?page=${pageNum}&per_page=${perPage}`;
                            const r = await fetch(url, {credentials: 'include'});
                            return await r.json();
                        }""",
                        [cat_id, page_num, PER_PAGE],
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to fetch products for category %s page %d: %s",
                        cat_name,
                        page_num,
                        exc,
                    )
                    break

                # Unwrap envelope if present.
                if isinstance(products_raw, dict):
                    products = products_raw.get(
                        "data", products_raw.get("products", [])
                    )
                elif isinstance(products_raw, list):
                    products = products_raw
                else:
                    logger.warning(
                        "Unexpected products shape for '%s' p%d: %r",
                        cat_name,
                        page_num,
                        str(products_raw)[:200],
                    )
                    break

                if not isinstance(products, list) or not products:
                    logger.debug(
                        "No products on page %d for category '%s' — stopping pagination.",
                        page_num,
                        cat_name,
                    )
                    break

                logger.info(
                    "Category '%s' page %d: %d products",
                    cat_name,
                    page_num,
                    len(products),
                )

                for product in products:
                    product_id = str(product.get("id") or product.get("sku") or "")
                    name = product.get("name") or product.get("product_name")
                    price = product.get("price")

                    if not name or price is None:
                        continue

                    yield {
                        "product_id": product_id,
                        "product_name": str(name).strip(),
                        "price": str(price),
                        "currency": self.currency,
                        "category": cat_name,
                        "url": (
                            f"https://thaihuotsupermarket.com/products/slug/"
                            f"{product.get('slug', product_id)}"
                        ),
                        "scraped_at": scraped_at,
                    }

                # Stop paginating if we got fewer than a full page.
                if len(products) < PER_PAGE:
                    break

        await page.close()

    def errback(self, failure):
        logger.error(
            "Request failed: %s — %s", failure.request.url, repr(failure.value)
        )
