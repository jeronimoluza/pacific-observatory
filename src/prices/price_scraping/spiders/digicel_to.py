"""
Digicel Tonga mobile data/voice bundles —
https://www.digicelpacific.com/mobile/to/bundles.

Digicel Pacific runs one Next.js site for all its island markets under
/mobile/<iso2>/... . The bundles page embeds its offer cards as JSON in the
<script id="__NEXT_DATA__"> tag (props.pageProps.flexibleContent), no API
call needed. flexibleContent alternates RichText (section heading) and
CardGroup (the OfferCard list for that section) in document order, so the
most recent RichText heading is used as each card's category.

Locality: path is Tonga-specific (/mobile/to/), and one card is literally
titled "Kava Night" (a Tongan cultural reference, not used on other island
pages) confirming this is Tonga-localized content, not a generic template.
Verified against /mobile/fj/bundles: Fiji's page returns a different set of
prices/headings (several explicitly suffixed "Fj"), confirming prices are
NOT a shared Pacific-wide table — each country page carries its own local
pricing. Tonga's cards show bare "$" with no ISO code anywhere in the page
(no priceCurrency / TOP / "pa'anga" string present), so currency is set to
TOP (Tonga's own currency, informally written "$" domestically) rather than
copied from another market.

Single static page (11 offers, all under one URL) — DuplicationPipeline
dedups on item['url'], so each row gets a synthetic #<card-id> fragment or
every row but the first would be silently dropped.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

URL = "https://www.digicelpacific.com/mobile/to/bundles"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_PRICE_RE = re.compile(r"[\d.]+")


class DigicelToSpider(scrapy.Spider):
    name = "digicel_to"
    allowed_domains = ["www.digicelpacific.com"]
    currency = "TOP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    start_urls = [URL]

    def parse(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("digicel_to: no __NEXT_DATA__ block found")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning("digicel_to: __NEXT_DATA__ was not valid JSON")
            return

        blocks = data.get("props", {}).get("pageProps", {}).get("flexibleContent", [])
        category = None
        count = 0
        for block in blocks:
            typename = block.get("__typename")
            if typename == "RichText":
                category = self._heading_text(block)
            elif typename == "CardGroup":
                for card in block.get("content", []):
                    item = self._item(card, category, response.url)
                    if item:
                        yield item
                        count += 1
        logger.info(f"digicel_to: emitted {count} rows")

    @staticmethod
    def _heading_text(richtext_block: dict) -> str | None:
        try:
            children = richtext_block["value"]["document"]["children"]
            for child in children:
                if child.get("type") == "heading":
                    spans = [
                        s.get("value", "")
                        for s in child.get("children", [])
                        if s.get("type") == "span"
                    ]
                    text = " ".join(spans).strip()
                    if text:
                        return text
        except (KeyError, TypeError):
            pass
        return None

    def _item(self, card: dict, category: str | None, page_url: str):
        if card.get("__typename") != "OfferCard":
            return None
        card_id = card.get("id")
        price_raw = card.get("price")
        if not card_id or not price_raw:
            return None
        pm = _PRICE_RE.search(price_raw)
        if not pm:
            return None
        heading = (card.get("heading") or "").strip()
        return {
            "product_id": card_id,
            "product_name": heading[:500],
            "category": category,
            "price": pm.group(0),
            "currency": self.currency,
            "available": True,
            "url": f"{page_url}#{card_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
