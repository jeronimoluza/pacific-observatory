"""Kaupule Funafuti market item prices from the public DOCX price list."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree

import scrapy


DOCX_URL = (
    "https://img1.wsimg.com/blobby/go/a5e6d2cd-374c-4f1d-9b3d-4bc9d63f0796/"
    "downloads/Market.docx?ver=1775957469429"
)
PUBLIC_PAGE_URL = "https://kaupulefunafuti.tv/market"

_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _docx_rows(body: bytes) -> list[tuple[str, str]]:
    with zipfile.ZipFile(io.BytesIO(body)) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))

    rows: list[tuple[str, str]] = []
    for table in root.findall(".//w:tbl", _NS):
        for row in table.findall("./w:tr", _NS):
            cells = []
            for cell in row.findall("./w:tc", _NS):
                text = " ".join(node.text or "" for node in cell.findall(".//w:t", _NS))
                cells.append(_clean(text))
            if len(cells) < 2:
                continue
            name, price_text = cells[0], cells[1]
            if not name or name.lower() in {"item", "items"}:
                continue
            if _PRICE_RE.search(price_text):
                rows.append((name, price_text))
    return rows


class KaupuleFunafutiMarketSpider(scrapy.Spider):
    name = "kaupule_funafuti_market"
    allowed_domains = ["kaupulefunafuti.tv", "img1.wsimg.com"]
    start_urls = [DOCX_URL]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        try:
            rows = _docx_rows(response.body)
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            self.logger.warning("Unable to parse Kaupule market DOCX: %s", exc)
            return

        for index, (name, price_text) in enumerate(rows, 1):
            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue
            product_id = _slug(f"{index}-{name}")
            yield {
                "product_id": product_id,
                "product_name": f"Kaupule Market {name}"[:500],
                "category": "Prepared food and bakery",
                "price": price_match.group(1),
                "price_text": price_text,
                "currency": self.currency,
                "available": True,
                "unit": "item",
                "document_url": response.url,
                "url": f"{PUBLIC_PAGE_URL}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
