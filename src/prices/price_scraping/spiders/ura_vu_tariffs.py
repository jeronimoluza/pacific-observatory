"""Vanuatu Utilities Regulatory Authority electricity and water tariffs."""

from __future__ import annotations

import hashlib
import re
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import certifi
import scrapy


_BASE_URL = "https://ura.gov.vu/en/component/content?id=14"
_CHAIN_PEM = Path(__file__).with_name("_ura_gov_vu_chain.pem")


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "ura_gov_vu_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


def _clean(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


class UraVuTariffsSpider(scrapy.Spider):
    name = "ura_vu_tariffs"
    allowed_domains = ["ura.gov.vu", "www.ura.gov.vu"]
    currency = "VUV"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _BASE_URL,
            callback=self.parse,
            meta={
                "impersonate": "chrome120",
                "impersonate_args": {"verify": _ca_bundle()},
            },
        )

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        current_table = response.css("table").get()
        if not current_table:
            return

        for row in scrapy.Selector(text=current_table).css("tr"):
            cells = [
                _clean(" ".join(cell.css("::text").getall()))
                for cell in row.css("th,td")
            ]
            cells = [cell for cell in cells if cell]
            if len(cells) < 4 or cells[0].lower() == "regulated service":
                continue
            if cells[0].upper() in {"ELECTRICITY", "WATER"}:
                service = cells[0].title()
                utility, unit, price, effective = cells[1:5]
            else:
                utility, unit, price, effective = cells[0:4]
                service = "Electricity" if unit == "Vatu/kWh" else "Water"
            price = re.sub(r"[^0-9.]", "", price)
            if not utility or not price:
                continue

            row_key = f"{service}|{utility}|{unit}|{price}|{effective}"
            product_id = hashlib.sha1(row_key.encode("utf-8")).hexdigest()[:16]
            yield {
                "product_id": product_id,
                "product_name": f"URA {service.lower()} tariff - {utility}",
                "category": f"{service} tariff",
                "price": price,
                "currency": self.currency,
                "available": True,
                "unit": unit,
                "effective_date": effective.rstrip("*"),
                "url": f"{response.url}#tariff-{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
