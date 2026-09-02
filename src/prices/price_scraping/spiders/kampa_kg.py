"""Spider for kampa.kg -- small-wholesale grocery online store, Bishkek, Kyrgyz
Republic (https://kampa.kg/).

Server-rendered CS-Cart storefront (theme class prefix `ty-`, `cm-ajax`
widgets) -- Tier 1A HTML, no anti-bot, no JS hydration needed. Confirmed via
curl_cffi impersonate=chrome124 with no headers/cookies required.

Independent of the Umai Group / Yandex-Lavka-platform pair already onboarded
for this country (globus_online_kg) -- kampa.kg is its own CS-Cart
storefront, different backend, no product_id namespace overlap (rule 19
n/a: ids are CS-Cart's own auto-increment, globus_online_kg's are Yandex
Lavka hashes).

**Structural walk only -- do not follow a blanket LinkExtractor.** A first
attempt used a Scrapy `CrawlSpider` with `allow=r"/vse-kategorii/"` and a
`deny=r"-\\d+/$"` meant to skip individual product-detail pages. That deny
was wrong: many PDP slugs end in a unit/word, not a digit (`...-pachka`,
`...-400gr`, `...-zh-b`), so the crawl fell through onto thousands of
product-detail pages. Those PDPs render their own "related products" widget
using the SAME `.ty-compact-list__item` markup as a real category listing,
so the naive crawl silently absorbed related-product carousels as if they
were category contents -- `category` came out as the *hosting product's own
slug* instead of a department name, and the crawl generated ~4,700 requests
(153k links deduped away) for under 9,000 real rows. Confirmed live
2026-09-01 (e.g. a "Makfiki pasta 400g" PDP's related-widget yielded
"Kilka v tomate" and "Ватные палочки" under category="makaron-makfiki-400gr-
pachka").

This spider instead walks the category tree structurally, using the two
distinct CS-Cart widget classes that never co-occur ambiguously:
- `.ty-subcategories__item a` -- the category-tile grid shown on parent
  category pages (e.g. `/vse-kategorii/`, `/vse-kategorii/bakaleya-bishkek/`)
  -- followed as more categories to walk, recursively.
- `.ty-pagination__item a` -- the page-number/next-page control on a leaf
  category's product-listing page -- followed as more pages of the SAME
  category.
- `.ty-compact-list__item` -- product cards, parsed for data wherever they
  appear (only actually present on real leaf category listing pages with
  this walk, since PDPs and non-listing pages are never requested).

No blanket allow/deny over arbitrary hrefs, so PDPs are never visited at
all -- the spider only ever requests URLs it discovered via one of the two
structural selectors above, starting from `/vse-kategorii/`.

Product card fields (unchanged from the first attempt, verified live
2026-09-01): `.product-title` (name + href), and a
`[id="sec_discounted_price_<id>"]` span holding both the CS-Cart internal
product id (in the element id, NOT reliably in the URL slug -- one card's
href was `.../ris-lazer-tashkent-ves-20884/` while its price/sku controls
all carried id `20883`) and the current selling price as plain text
("133.00"), with currency in a sibling span ("сом").

Verified live 2026-09-01: KGS prices, e.g. 'Рис Лазер Ташкент вес' 133.00
KGS, 'Крупа Перловая Макфа 800гр' 49.00 KGS.
"""

import re
from datetime import datetime, timezone

import scrapy


class KampaKgSpider(scrapy.Spider):
    name = "kampa_kg"
    allowed_domains = ["kampa.kg"]
    start_urls = ["https://kampa.kg/vse-kategorii/"]
    currency = "KGS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        # Sub-category tiles -- present on parent/intermediate category pages.
        for href in response.css(".ty-subcategories__item a::attr(href)").getall():
            yield response.follow(href, callback=self.parse)

        # Pagination -- present on leaf category listing pages with >1 page.
        # NOTE: the anchor tag itself carries class="ty-pagination__item" (no
        # nested <a> inside a wrapping element) -- `.ty-pagination__item
        # a::attr(href)` (descendant-anchor form) matches nothing and was the
        # bug in the first correct-selector attempt, silently capping every
        # category at its first page (20 items) with zero errors raised.
        for href in response.css("a.ty-pagination__item::attr(href)").getall():
            yield response.follow(href, callback=self.parse)

        # Product cards -- only actually populated on leaf listing pages,
        # since this spider never requests anything but category/pagination
        # URLs discovered via the two selectors above.
        yield from self.parse_products(response)

    def parse_products(self, response):
        segments = [s for s in response.url.split("/") if s]
        category = (
            segments[-1]
            if segments and not segments[-1].startswith("page-")
            else (segments[-2] if len(segments) > 1 else "unknown")
        )
        for card in response.css(".ty-compact-list__item"):
            name = card.css(".product-title::text").get()
            href = card.css(".product-title::attr(href)").get()
            pid_attr = card.css('[id^="sec_discounted_price_"]::attr(id)').get()
            price = card.css('[id^="sec_discounted_price_"]::text').get()
            if not (name and href and pid_attr and price):
                continue
            pid = pid_attr.replace("sec_discounted_price_", "")
            name = re.sub(r"\s+", " ", name).strip()
            price = price.strip().replace(",", ".")
            if not name or not pid or not price:
                continue
            try:
                float(price)
            except ValueError:
                continue
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
