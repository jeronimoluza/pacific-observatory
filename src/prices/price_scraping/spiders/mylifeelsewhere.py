"""Spider for MyLifeElsewhere — country-level cost-of-living aggregator.

MLE only publishes country-level pages (no city pages exist). Each page
holds ~34 items across 7 categories (Restaurants, Groceries,
Transportation, Housing, Childcare, Entertainment and Sports, Clothing).
Prices are DUAL-CURRENCY: each cost cell has USD as the direct text node
and local currency in a nested ``<div class="text-gray-400">`` (e.g.
``$4.75`` + ``FJD10.46``).

Because of the dual encoding, this is the first aggregator where both
``price`` (local) AND ``price_usd`` come straight from the source — no
downstream FX needed. The 3-letter ISO currency code is parsed from the
nested div text prefix (e.g. ``FJD10.46`` → ``FJD``).

No city dimension: ``city`` is left null and ``product_id`` is
``{country_slug}:{item_slug}``.

The ``parse_html`` classmethod is pure (no Scrapy deps) so the Wayback
backfiller in ``prices/backfill.py`` can replay archived snapshots.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urlparse

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = "https://www.mylifeelsewhere.com"
_USD_RE = re.compile(r"\$\s*([\d.,]+)")
_LOCAL_RE = re.compile(r"^([A-Z]{2,4})\s*([\d.,]+)")
_NUMBER_RE = re.compile(r"([\d.,]+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Filter out non-category h3s that appear elsewhere on the page.
_NON_CATEGORY_H3 = {
    "nice to see you!",
    "help us improve these prices",
    "ask the elsewhere community",
    "change currency:",
}


class MyLifeElsewhereSpider(scrapy.Spider):
    name = "mylifeelsewhere"
    allowed_domains = ["mylifeelsewhere.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        # ~34 records per URL — URL-hash dedupe would drop 33.
        "ITEM_PIPELINES": {
            "price_scraping.pipelines.JsonWriterPipeline": 400,
            "price_scraping.pipelines.LoggingPipeline": 500,
        },
        "USER_AGENT": _UA,
    }

    def __init__(self, country_slug: str | None = None, **kwargs):
        super().__init__(**kwargs)
        if not country_slug:
            raise ValueError(
                "MyLifeElsewhereSpider requires spider_kwargs.country_slug "
                "(MLE URL slug, e.g. 'fiji', 'hong-kong', 'french-polynesia')."
            )
        self.country_slug = country_slug
        self._record_count = 0

    async def start(self):
        url = f"{_BASE}/cost-of-living/{self.country_slug}"
        yield scrapy.Request(
            url,
            meta={"impersonate": "chrome120"},
            callback=self.parse_country,
            errback=self.errback_country,
        )

    def parse_country(self, response):
        records = list(
            self.parse_html(response.text, response.url, country_slug=self.country_slug)
        )
        if not records:
            logger.warning(
                "[mylifeelsewhere] country=%s url=%s yielded 0 records — "
                "country may not be in MLE panel or layout changed.",
                self.country_slug,
                response.url,
            )
            return
        self._record_count = len(records)
        for rec in records:
            yield rec

    def errback_country(self, failure):
        logger.error(
            "[mylifeelsewhere] country page fetch failed for %s: %s",
            self.country_slug,
            failure.value,
        )

    def closed(self, reason):
        logger.info(
            "[mylifeelsewhere] === SUMMARY === country=%s reason=%s records=%d",
            self.country_slug,
            reason,
            self._record_count,
        )

    # ------------------------------------------------------------------
    # Shared parser — used by live scrape AND backfill.py
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(
        cls,
        html: str,
        url: str,
        country_slug: str | None = None,
    ) -> Iterator[dict]:
        """Yield one dict per (country, item) on an MLE country page.

        Both ``price`` (local) and ``price_usd`` are populated from the
        source — MLE puts USD in the direct text node and local currency
        in a nested ``<div class="text-gray-400">``.
        """
        soup = BeautifulSoup(html, "html.parser")

        if country_slug is None:
            parts = [p for p in urlparse(url).path.split("/") if p]
            # /cost-of-living/<country>  →  parts = ["cost-of-living", country]
            if len(parts) >= 2 and parts[0] == "cost-of-living":
                country_slug = parts[1]

        scraped_at = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Walk h3 + table.table-fixed pairs in document order.
        current_cat: str | None = None
        for el in soup.find_all(["h3", "table"]):
            if el.name == "h3":
                txt = el.get_text(strip=True)
                if txt.lower() not in _NON_CATEGORY_H3:
                    current_cat = txt
                continue
            classes = el.get("class") or []
            if "table-fixed" not in classes or current_cat is None:
                continue
            for tr in el.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue  # skip header row
                # td[0] = item name (may include nested .text-gray-400 sub-label)
                # td[1] = "$USD<div class='text-gray-400'>LOCALCURRENCY+AMOUNT</div>"
                name = tds[0].get_text(" ", strip=True)
                # Collapse repeated whitespace from inner spans
                name = re.sub(r"\s+", " ", name).strip()
                if not name:
                    continue

                cost_td = tds[1]
                # USD: take direct text of the td (excluding nested divs)
                usd_text = "".join(
                    s for s in cost_td.find_all(string=True, recursive=False)
                ).strip()
                if not usd_text:
                    # Fallback: full td text minus any nested div text
                    full = cost_td.get_text(" ", strip=True)
                    nested = cost_td.find("div", class_="text-gray-400")
                    if nested:
                        full = full.replace(nested.get_text(strip=True), "").strip()
                    usd_text = full
                usd_m = _USD_RE.search(usd_text)
                if not usd_m:
                    continue
                try:
                    price_usd = float(usd_m.group(1).replace(",", ""))
                except ValueError:
                    continue

                nested = cost_td.find("div", class_="text-gray-400")
                local_raw = nested.get_text(strip=True) if nested else ""
                local_m = _LOCAL_RE.match(local_raw)
                if local_m:
                    currency = local_m.group(1)
                    try:
                        price_local = float(local_m.group(2).replace(",", ""))
                    except ValueError:
                        price_local = None
                else:
                    # Some countries show USD only (e.g. USD economies); use USD.
                    currency = "USD"
                    price_local = price_usd
                    local_raw = usd_text.strip()

                item_key = cls._slugify(name)
                price_field = price_local if price_local is not None else price_usd
                price_raw = local_raw or usd_text.strip()
                yield {
                    "product_id": (
                        f"{country_slug}:{item_key}" if country_slug else item_key
                    ),
                    "product_name": name,
                    "price": price_field,
                    "price_raw": price_raw,
                    "currency": currency,
                    "price_usd": price_usd,
                    "category": current_cat,
                    "city": None,
                    "url": url,
                    "source_date_label": None,
                    "scraped_at": scraped_at,
                }

    @staticmethod
    def _slugify(label: str) -> str:
        s = _SLUG_RE.sub("_", label.lower()).strip("_")
        return s[:60]
