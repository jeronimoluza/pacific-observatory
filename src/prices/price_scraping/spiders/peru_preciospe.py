"""Merchant-attributed Peru offers from PreciosPe's first-party search API."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import scrapy


API_URL = "https://api.preciospe.com/"
DEFAULT_QUERIES = (
    "celular",
    "laptop",
    "televisor",
    "playstation",
    "audifonos",
    "refrigeradora",
    "lavadora",
    "zapatillas",
    "supermercado",
    "bebe",
    "mascotas",
    "licores",
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _amount(value: object) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _canonical_url(value: object) -> str | None:
    raw = _clean(value)
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.query, ""))


def _merchant_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def iter_offer_rows(payload: dict, scraped_at: str):
    """Yield only atomic offers; grouped parent floors are never emitted."""
    for product in payload.get("resultados") or []:
        source_id = product.get("id")
        name = _clean(product.get("nombre"))
        if source_id is None or not name:
            continue

        grouped = product.get("producto_agrupado") is True
        if grouped:
            offers = product.get("ofertas_tiendas") or []
        else:
            offers = [
                {
                    "tienda": product.get("tienda"),
                    "precio": product.get("precio"),
                    "precio_texto": product.get("precio_texto"),
                    "link": product.get("link"),
                    "envio_gratis": product.get("envio_gratis"),
                }
            ]

        for offer in offers:
            merchant = _clean(offer.get("tienda"))
            price = _amount(offer.get("precio"))
            price_text = _clean(offer.get("precio_texto"))
            url = _canonical_url(offer.get("link"))
            if not (merchant and price and url and price_text.startswith("S/")):
                continue

            merchant_key = _merchant_key(merchant)
            if not merchant_key:
                continue
            offer_id = f"{source_id}:{merchant_key}" if grouped else str(source_id)

            list_price = None
            same_top_offer = (
                merchant.casefold() == _clean(product.get("tienda")).casefold()
                and url == _canonical_url(product.get("link"))
                and price == _amount(product.get("precio"))
            )
            original = _amount(product.get("precio_original"))
            if same_top_offer and original and original > price:
                list_price = format(original, "f")

            yield {
                "product_id": offer_id,
                "source_product_id": str(source_id),
                "product_name": name[:500],
                "merchant": merchant,
                "price": format(price, "f"),
                "list_price": list_price,
                "currency": "PEN",
                "country": "Peru",
                "category": _clean(product.get("categoria")) or None,
                "brand": _clean(product.get("marca")) or None,
                "condition": _clean(product.get("condicion")) or None,
                "free_shipping": bool(offer.get("envio_gratis", product.get("envio_gratis", False))),
                "url": url,
                "scraped_at_utc": scraped_at,
            }


class PeruPreciospeSpider(scrapy.Spider):
    name = "peru_preciospe"
    allowed_domains = ["api.preciospe.com"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 2,
    }

    def __init__(self, queries: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected = queries.split(",") if queries else DEFAULT_QUERIES
        self.queries = tuple(query for value in selected if (query := _clean(value)))
        self._seen_offers: set[tuple[str, str]] = set()

    async def start(self):
        for query in self.queries:
            body = json.dumps(
                {"query": query, "pais": "pe"},
                ensure_ascii=True,
                separators=(",", ":"),
            )
            yield scrapy.Request(
                API_URL,
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
                callback=self.parse_api,
                cb_kwargs={"query": query},
            )

    def parse_api(self, response, query: str):
        payload = response.json()
        if payload.get("success") is not True:
            self.logger.warning("PreciosPe query %r was unsuccessful", query)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in iter_offer_rows(payload, scraped_at):
            dedupe_key = (row["source_product_id"], row["url"])
            if dedupe_key in self._seen_offers:
                continue
            self._seen_offers.add(dedupe_key)
            yield row
