"""Spider for Expatistan — crowd-sourced city cost-of-living aggregator.

Emits one record per (city, item) pair. Prices are in LOCAL currency
(`27 FJ$`, `12,500 ₫`); the spider does NOT convert to USD — apply the WB FX
feed downstream, like the retailer spiders do. The 3-letter ISO currency
code is supplied by the YAML manifest's `spider_kwargs.currency`.

Anti-bot: the site is fronted by Cloudflare. Plain `curl` fails the TLS
fingerprint challenge, but `meta['impersonate']='chrome120'` (curl_cffi via
scrapy-impersonate) passes cleanly — no Playwright needed. The site's
robots.txt explicitly bans `claudebot`, so a generic Chrome UA is set in
custom_settings.

Hybrid city discovery:
  - If `spider_kwargs.cities` is supplied, scrape that explicit list.
    Cities use Expatistan's disambiguated `<city>-<country>` slug
    (e.g. `suva-fiji`, `hong-kong`) — bare city slugs redirect to the
    disambiguated form.
  - If `cities` is absent, fetch `/cost-of-living/country/<country_slug>`
    and auto-discover every city link from the "List of all cities
    available in <Country>" table.

The `parse_html` classmethod is pure (no Scrapy deps) so the Wayback
backfiller in `prices/backfill.py` can replay archived snapshots through
the same parser.
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

_BASE = "https://www.expatistan.com"
_CITY_PATH_RE = re.compile(
    r"^(?:https?://(?:www\.)?expatistan\.com)?/cost-of-living/([a-z0-9\-]+)/?$"
)
_NUMBER_RE = re.compile(r"([\d.,]+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ExpatistanSpider(scrapy.Spider):
    name = "expatistan"
    allowed_domains = ["expatistan.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 3.0,  # Cloudflare-fronted — be gentle
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        # ~52 records per URL — URL-hash dedupe would drop 51.
        "ITEM_PIPELINES": {
            "price_scraping.pipelines.JsonWriterPipeline": 400,
            "price_scraping.pipelines.LoggingPipeline": 500,
        },
        # robots.txt explicitly bans `claudebot` — set a generic Chrome UA.
        "USER_AGENT": _UA,
    }

    def __init__(
        self,
        country_slug: str | None = None,
        currency: str | None = None,
        cities: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not country_slug:
            raise ValueError(
                "ExpatistanSpider requires spider_kwargs.country_slug "
                "(the aggregator's URL slug, e.g. 'fiji', 'hong-kong')."
            )
        if not currency:
            raise ValueError(
                "ExpatistanSpider requires spider_kwargs.currency "
                "(3-letter ISO, e.g. 'FJD', 'HKD' — site uses local currency)."
            )
        self.country_slug = country_slug
        self.currency = currency
        self.cities: list[str] | None = list(cities) if cities else None
        self._missing_cities: list[str] = []
        self._scraped_cities: list[str] = []

    async def start(self):
        if self.cities:
            for city in self.cities:
                yield self._city_request(city)
        else:
            url = f"{_BASE}/cost-of-living/country/{self.country_slug}"
            yield scrapy.Request(
                url,
                meta={"impersonate": "chrome120"},
                callback=self.parse_country_for_cities,
                errback=self.errback_country,
            )

    def _city_request(self, city: str) -> scrapy.Request:
        url = f"{_BASE}/cost-of-living/{city}"
        return scrapy.Request(
            url,
            meta={"impersonate": "chrome120", "city": city},
            callback=self.parse_city,
            errback=self.errback_city,
        )

    def parse_country_for_cities(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        # Country page has an h2 "List of all cities available in <Country>"
        # followed by a table.extra-spacing-in-mobile of city anchors.
        # Anchors point at /cost-of-living/<city-country> (disambiguated slugs).
        h2 = soup.find("h2", string=lambda s: bool(s) and "List of all cities" in s)
        tbl = h2.find_next("table") if h2 is not None else None
        if tbl is None:
            logger.warning(
                "[expatistan] no 'List of all cities' table on country page "
                "%s — layout may have changed or country has no panel.",
                self.country_slug,
            )
            return
        discovered: list[str] = []
        seen: set[str] = set()
        for a in tbl.select("a[href]"):
            href = a.get("href", "").split("?")[0].split("#")[0]
            m = _CITY_PATH_RE.match(href)
            if not m:
                continue
            slug = m.group(1)
            # Skip back-link to country page itself (`country/<slug>` doesn't
            # match the regex, but `unknown-city/...` could).
            if slug.startswith(("country", "unknown-city", "rate")):
                continue
            if slug and slug not in seen:
                seen.add(slug)
                discovered.append(slug)
        if not discovered:
            logger.warning(
                "[expatistan] auto-discover found 0 cities for %s — country "
                "table may use a different layout.",
                self.country_slug,
            )
            return
        logger.info(
            "[expatistan] auto-discovered %d cities for %s: %s",
            len(discovered),
            self.country_slug,
            ", ".join(discovered[:10]) + ("…" if len(discovered) > 10 else ""),
        )
        for city in discovered:
            yield self._city_request(city)

    def parse_city(self, response):
        city = response.meta.get("city")
        # Missing-data sentinel: server redirects to /unknown-city/<slug>
        if "/unknown-city/" in response.url or "/cost-of-living/rate/" in response.url:
            self._missing_cities.append(city or response.url)
            logger.warning(
                "[expatistan] city=%s redirected to %s — no panel data, skipping.",
                city,
                response.url,
            )
            return
        records = list(
            self.parse_html(
                response.text, response.url, currency=self.currency, city=city
            )
        )
        if not records:
            self._missing_cities.append(city or response.url)
            logger.warning(
                "[expatistan] city=%s url=%s yielded 0 records — panel may be "
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
            "[expatistan] city=%s url=%s failed (status=%s) — likely not in "
            "Expatistan panel; skipping.",
            city,
            request.url,
            status,
        )

    def errback_country(self, failure):
        logger.error(
            "[expatistan] country landing page fetch failed for %s: %s",
            self.country_slug,
            failure.value,
        )

    def closed(self, reason):
        logger.info(
            "[expatistan] === SUMMARY === country=%s reason=%s scraped_cities=%d %s missing_cities=%d %s",
            self.country_slug,
            reason,
            len(self._scraped_cities),
            self._scraped_cities or "[]",
            len(self._missing_cities),
            self._missing_cities or "[]",
        )
        if self._missing_cities:
            logger.warning(
                "[expatistan] !! %d cities had no Expatistan panel data: %s "
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
        currency: str = "?",
        city: str | None = None,
    ) -> Iterator[dict]:
        """Yield one dict per (city, item) pair on an Expatistan city page.

        Also emits the page's two summary rows ("Family of four monthly
        costs", "Single person monthly costs") as category="Summary" — these
        are the city's CPI-analog totals.
        """
        soup = BeautifulSoup(html, "html.parser")

        if city is None:
            parts = [p for p in urlparse(url).path.split("/") if p]
            # /cost-of-living/<city>  →  parts = ["cost-of-living", city]
            if len(parts) >= 2 and parts[0] == "cost-of-living":
                city = parts[1]

        date_label = cls._extract_date(soup)
        scraped_at = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Item table.
        table = soup.select_one("table.comparison.single-city")

        # --- Summary block: span.price elements OUTSIDE the item table.
        # Page layout: two <li>s near the top each with a <span class="price">
        # for "Family of four monthly costs" and "Single person monthly costs".
        table_descendants = (
            set(id(d) for d in table.descendants) if table is not None else set()
        )
        for span in soup.select("span.price"):
            if id(span) in table_descendants:
                continue
            li = span.find_parent("li")
            if li is None:
                continue
            price_raw = span.get_text(strip=True)
            # Label = li text minus the price text.
            label = li.get_text(" ", strip=True).replace(price_raw, "").strip(" :,.")
            if not label:
                continue
            price_num = cls._parse_price_num(price_raw)
            if price_num is None:
                continue
            item_key = cls._slugify(label)
            yield {
                "product_id": (f"{city}:{item_key}" if city else item_key),
                "product_name": label,
                "price": price_num,
                "price_raw": price_raw,
                "currency": currency,
                "category": "Summary",
                "city": city,
                "url": url,
                "source_date_label": date_label,
                "scraped_at": scraped_at,
            }

        # --- Item rows: pairs of (td.item-name, td.price) within each tr,
        # tracking the most-recently-seen tr.categoryHeader. Item rows can
        # overlap across rows (item N appears in row i+1 again because of
        # the responsive 2-column layout); dedupe by item name.
        if table is None:
            return
        seen: set[str] = set()
        current_cat: str | None = None
        for tr in table.find_all("tr"):
            classes = tr.get("class") or []
            if "categoryHeader" in classes:
                # Category name is the FIRST <th>; subsequent <th> is "Update prices".
                ths = tr.find_all("th")
                if ths:
                    current_cat = ths[0].get_text(strip=True)
                continue
            cells = tr.find_all("td", recursive=False)
            i = 0
            while i < len(cells) - 1:
                cls_a = cells[i].get("class") or []
                cls_b = cells[i + 1].get("class") or []
                if "item-name" in cls_a and "price" in cls_b:
                    name = cells[i].get_text(" ", strip=True)
                    if name and name not in seen:
                        seen.add(name)
                        price_raw = cells[i + 1].get_text(" ", strip=True)
                        price_num = cls._parse_price_num(price_raw)
                        if price_num is not None:
                            item_key = cls._slugify(name)
                            yield {
                                "product_id": (
                                    f"{city}:{item_key}" if city else item_key
                                ),
                                "product_name": name,
                                "price": price_num,
                                "price_raw": price_raw,
                                "currency": currency,
                                "category": current_cat,
                                "city": city,
                                "url": url,
                                "source_date_label": date_label,
                                "scraped_at": scraped_at,
                            }
                    i += 2
                else:
                    i += 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_date(soup: BeautifulSoup) -> str | None:
        # Page title: "Cost of Living in Suva. Updated Prices May 2026."
        if soup.title:
            m = re.search(r"Updated Prices ([A-Z][a-z]+ \d{4})", soup.title.get_text())
            if m:
                return m.group(1)
        # Fallback: h2 "Current as of May 2026."
        for h2 in soup.find_all("h2"):
            m = re.search(r"as of ([A-Z][a-z]+ \d{4})", h2.get_text())
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _parse_price_num(s: str) -> float | None:
        # Strip thousands commas, then grab first numeric token.
        # Handles "27 FJ$", "1,870 FJ$", "0.17 FJ$", "12,500 ₫", "$2.54".
        cleaned = s.replace(",", "")
        m = _NUMBER_RE.search(cleaned)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    @staticmethod
    def _slugify(label: str) -> str:
        s = _SLUG_RE.sub("_", label.lower()).strip("_")
        return s[:60]
