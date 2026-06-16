"""Spider for LivingCost.org — crowd-sourced city cost-of-living aggregator.

Emits one record per (city, item) pair. Prices are USD-canonical: every
LivingCost page stores values in `<span data-usd="N.NNN">` and renders other
currencies client-side from a separate rates file. Local-currency rendering
needs an FX feed applied downstream.

Hybrid city discovery:
  - If `spider_kwargs.cities` is supplied in the YAML, scrape that explicit
    list (preferred for small Pacific panels).
  - If `cities` is absent, fetch the country landing page and auto-discover
    every `<a href="/cost/{country_slug}/{city}">` link (for large countries).

The `parse_html` classmethod is shared between live scrape and the Wayback
backfiller via the parse-hook in `prices/backfill.py` — keeps live and
historical parsing in sync.
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

_BASE = "https://livingcost.org"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class LivingCostSpider(scrapy.Spider):
    name = "livingcost"
    allowed_domains = ["livingcost.org"]
    currency = "USD"  # source is USD-canonical

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        # Aggregator emits ~50 records per URL — URL-hash dedupe would drop 49.
        "ITEM_PIPELINES": {
            "price_scraping.pipelines.JsonWriterPipeline": 400,
            "price_scraping.pipelines.LoggingPipeline": 500,
        },
    }

    def __init__(
        self,
        country_slug: str | None = None,
        cities: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not country_slug:
            raise ValueError(
                "LivingCostSpider requires spider_kwargs.country_slug "
                "(the aggregator's URL slug, e.g. 'fiji', 'vietnam')."
            )
        self.country_slug = country_slug
        self.cities: list[str] | None = list(cities) if cities else None
        self._missing_cities: list[str] = []
        self._scraped_cities: list[str] = []

    async def start(self):
        if self.cities:
            for city in self.cities:
                yield self._city_request(city)
        else:
            # Auto-discover: hit country landing page, parse city links
            url = f"{_BASE}/cost/{self.country_slug}"
            yield scrapy.Request(
                url,
                meta={"impersonate": "chrome120"},
                callback=self.parse_country_for_cities,
                errback=self.errback_country,
            )

    def _city_request(self, city: str) -> scrapy.Request:
        url = f"{_BASE}/cost/{self.country_slug}/{city}"
        return scrapy.Request(
            url,
            meta={"impersonate": "chrome120", "city": city},
            callback=self.parse_city,
            errback=self.errback_city,
        )

    def parse_country_for_cities(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        # The "Cities by population" section uses <h2 id="cities"> followed by
        # an <ol> of city <li>s. Other URL patterns matching /cost/<country>/X
        # are country-comparison cards (Indonesia-vs-Japan etc.); scoping
        # discovery to the cities <ol> avoids matching them.
        heading = soup.find(id="cities")
        cities_list = heading.find_next("ol") if heading is not None else None
        if cities_list is None:
            logger.warning(
                "[livingcost] no <h2 id='cities'> + <ol> found on country "
                "page for %s — layout may have changed.",
                self.country_slug,
            )
            return
        path_re = re.compile(
            rf"^(?:https?://(?:www\.)?livingcost\.org)?"
            rf"/cost/{re.escape(self.country_slug)}/([a-z0-9\-]+)/?$"
        )
        discovered: list[str] = []
        seen: set[str] = set()
        for a in cities_list.select("a[href]"):
            href = a.get("href", "").split("?")[0].split("#")[0]
            m = path_re.match(href)
            if not m:
                continue
            slug = m.group(1)
            if slug and slug not in seen:
                seen.add(slug)
                discovered.append(slug)
        if not discovered:
            logger.warning(
                "[livingcost] auto-discover found 0 cities for %s — country "
                "page may use a different layout, or country is not in panel.",
                self.country_slug,
            )
            return
        logger.info(
            "[livingcost] auto-discovered %d cities for %s: %s",
            len(discovered),
            self.country_slug,
            ", ".join(discovered[:10]) + ("…" if len(discovered) > 10 else ""),
        )
        for city in discovered:
            yield self._city_request(city)

    def parse_city(self, response):
        city = response.meta.get("city")
        records = list(self.parse_html(response.text, response.url, city=city))
        if not records:
            self._missing_cities.append(city or response.url)
            logger.warning(
                "[livingcost] city=%s url=%s yielded 0 records — panel may be "
                "empty or page layout changed.",
                city,
                response.url,
            )
            return
        self._scraped_cities.append(city or "?")
        for rec in records:
            yield rec

    def errback_city(self, failure):
        request = failure.request
        city = request.meta.get("city", "?")
        status = (
            getattr(failure.value.response, "status", "?")
            if hasattr(failure.value, "response")
            else "?"
        )
        self._missing_cities.append(city)
        logger.warning(
            "[livingcost] city=%s url=%s failed (status=%s) — likely not in "
            "LivingCost panel; skipping.",
            city,
            request.url,
            status,
        )

    def errback_country(self, failure):
        logger.error(
            "[livingcost] country landing page fetch failed for %s: %s",
            self.country_slug,
            failure.value,
        )

    def closed(self, reason):
        # Loud end-of-run summary, per design clarification #6.
        logger.info(
            "[livingcost] === SUMMARY === country=%s reason=%s scraped_cities=%d %s missing_cities=%d %s",
            self.country_slug,
            reason,
            len(self._scraped_cities),
            self._scraped_cities or "[]",
            len(self._missing_cities),
            self._missing_cities or "[]",
        )
        if self._missing_cities:
            logger.warning(
                "[livingcost] !! %d cities had no LivingCost panel data: %s "
                "— consider removing from YAML or setting active: false.",
                len(self._missing_cities),
                self._missing_cities,
            )

    # ------------------------------------------------------------------
    # Shared parser — used by live scrape AND backfill.py's parse_html hook
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(
        cls,
        html: str,
        url: str,
        city: str | None = None,
    ) -> Iterator[dict]:
        """Yield one dict per (city, item) pair on a LivingCost city page.

        Pure function: takes raw HTML + URL, returns records. No Scrapy
        dependencies, no I/O — safe to call from the Wayback backfiller on
        archived snapshots.
        """
        soup = BeautifulSoup(html, "html.parser")

        if city is None:
            parts = [p for p in urlparse(url).path.split("/") if p]
            # /cost/<country>/<city>  → parts = ["cost", country, city]
            if len(parts) >= 3 and parts[0] == "cost":
                city = parts[2]

        date_label = cls._extract_updated(soup)
        scraped_at = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        for table in soup.select("table.table"):
            caption = table.find("caption")
            if caption is None:
                continue
            category = caption.get_text(strip=True)
            for tr in table.select("tbody tr"):
                th = tr.find("th")
                if th is None:
                    continue
                emoji = th.find("span", class_="font-weight-normal")
                if emoji is not None:
                    emoji.decompose()
                label = th.get_text(" ", strip=True)
                if not label:
                    continue
                span = tr.select_one("span[data-usd]")
                if span is None:
                    continue
                try:
                    price_usd = float(span["data-usd"])
                except (ValueError, KeyError, TypeError):
                    continue
                price_raw = span.get_text(strip=True)
                item_key = cls._slugify(label)
                yield {
                    "product_id": (f"{city}:{item_key}" if city else item_key),
                    "product_name": label,
                    "price": price_usd,
                    "price_raw": price_raw,
                    "currency": "USD",
                    "price_usd": price_usd,
                    "category": category,
                    "city": city,
                    "url": url,
                    "source_date_label": date_label,
                    "scraped_at": scraped_at,
                }

    @staticmethod
    def _extract_updated(soup: BeautifulSoup) -> str | None:
        # HTML form: <p ...>Updated: <time datetime="2026-03-11...">March 11, 2026</time></p>
        # The "Updated:" string and the date live in different child nodes,
        # so we walk up to the containing <p> and get its full text.
        text = soup.find(string=re.compile(r"Updated:"))
        if text is None:
            return None
        parent = text.parent
        if parent is not None:
            full = parent.get_text(" ", strip=True)
            if full.startswith("Updated:"):
                return full
        return str(text).strip() or None

    @staticmethod
    def _slugify(label: str) -> str:
        s = _SLUG_RE.sub("_", label.lower()).strip("_")
        return s[:60]
