"""
SNEL — Société Nationale d'Electricité (Democratic Republic of Congo)
https://www.snel.cd/.

SNEL is the state electricity utility; its homepage publishes the full,
government-set tariff grid (Basse/Moyenne/Haute Tension) as plain
server-rendered HTML tables inside two Bootstrap modals
(`#modal-tarif-bt`, `#modal-tarif-mt`) plus one accordion pane
(`#collapseTarifsHT`) — no JS rendering needed, no API. Probed live
2026-08-31: HTTP 200, tables present verbatim in the raw response body.
All tariffs are quoted in USD (per kWh, or per month for meter rental) —
genuine local practice for DRC utility billing, left unconverted.

The page mixes ~10 independently-titled tariff tables (BT: forfaitaire,
Résidentiel 1/2, semi-industriel commercial/force motrice; MT: force
motrice/vapeur/chauffage/office/résidentiel by PUISSANCE band; HT: by
zone) with irregular column counts (1 price column, or 4 "ajustement"
columns, or a 2-column "Terme A / Terme B" pair). Rather than special-case
each table, every `<table class="table table-bordered">` in those three
containers is walked generically: the first `<td>` in each body row is
the row label (a consumption tranche, a subscribed-power band, or a
tariff zone), the last `<thead>` row supplies the per-column labels, and
every remaining numeric `<td>` becomes one item, tagged with the nearest
preceding all-caps `<p><strong>` as its major category (e.g. "MOYENNE
TENSION FORCE MOTRICE") and the nearest mixed-case one as its subcategory
(e.g. "Résidentiel 1"). A row with fewer `<td>` than header columns (the
merged-cell "LOCATION COMPTEUR" rows) is handled for free: zip() just
stops at the shorter sequence.

Single-page source: every row shares the homepage URL, and the
DuplicationPipeline dedups on `item['url']`, so each row gets a unique
`#<slug>` fragment appended — otherwise all but the first row would be
silently dropped (see AGENT_BRIEF trap #4).
"""

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.snel.cd/"
_NUM_RE = re.compile(r"\d+(?:[.,]\s?\d+)?")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _parse_number(text: str):
    m = _NUM_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(0).replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _is_major(label: str) -> bool:
    letters = [c for c in unicodedata.normalize("NFKD", label) if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


class SnelCdSpider(scrapy.Spider):
    name = "snel_cd"
    allowed_domains = ["snel.cd"]
    currency = "USD"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(BASE_URL, callback=self.parse, errback=self.errback)

    def parse(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        count = 0

        bt = soup.find(id="modal-tarif-bt")
        if bt is not None:
            for item in self._walk_container(bt, "Basse Tension"):
                count += 1
                yield item

        mt = soup.find(id="modal-tarif-mt")
        if mt is not None:
            for item in self._walk_container(mt, "Moyenne Tension"):
                count += 1
                yield item

        ht = soup.find(id="collapseTarifsHT")
        if ht is not None:
            for item in self._walk_container(ht, "Haute Tension"):
                count += 1
                yield item

        logger.info(f"{self.name}: emitted {count} tariff rows")
        if count == 0:
            logger.warning(
                f"{self.name}: 0 rows parsed — page structure likely changed"
            )

    def _walk_container(self, container, default_major: str):
        major = default_major
        sub = None
        for el in container.find_all(["p", "table"]):
            if el.name == "p":
                strong = el.find("strong")
                if strong is None:
                    continue
                p_text = _clean(el.get_text(" ", strip=True))
                s_text = _clean(strong.get_text(" ", strip=True))
                if not s_text or p_text != s_text:
                    continue  # a mixed paragraph, not a bare category label
                if _is_major(s_text):
                    major, sub = s_text, None
                else:
                    sub = s_text
            elif el.name == "table":
                category = f"{major} - {sub}" if sub else major
                yield from self._walk_table(el, category)

    def _walk_table(self, table, category: str):
        thead = table.find("thead")
        headers = []
        if thead is not None:
            header_rows = thead.find_all("tr")
            if header_rows:
                headers = [
                    _clean(th.get_text(" ", strip=True))
                    for th in header_rows[-1].find_all("th")
                ]
        tbody = table.find("tbody")
        if tbody is None:
            return
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            label_parts = [_clean(cells[0].get_text(" ", strip=True))]
            if not label_parts[0]:
                continue
            for i in range(1, len(cells)):
                text = _clean(cells[i].get_text(" ", strip=True))
                value = _parse_number(text)
                if value is None:
                    # A non-numeric middle cell (e.g. the HT table's zone
                    # name in column 1) is descriptive, not a data point —
                    # fold it into the row label instead of dropping it.
                    if text:
                        label_parts.append(text)
                    continue
                row_label = " ".join(label_parts)
                col_label = headers[i] if i < len(headers) else ""
                yield self._item(category, row_label, col_label, value, text)

    def _item(self, category, row_label, col_label, value, raw_text):
        name_parts = [p for p in (category, row_label, col_label) if p]
        name = " | ".join(name_parts)[:500]
        slug_src = f"{category}|{row_label}|{col_label}|{raw_text}"
        slug = hashlib.sha1(slug_src.encode("utf-8")).hexdigest()[:12]
        return {
            "product_id": slug,
            "product_name": name,
            "category": category,
            "price": str(value),
            "currency": self.currency,
            "available": True,
            "url": f"{BASE_URL}#tarif-{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
