"""Scrape CompraExpress's public Guinea-Bissau storefront catalogue."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_KEY = "sb_publishable_R6c8CjjgpJ5Vvf19yxbrPA_Bodm1ycU"
API_URL = (
    "https://dzxmasurrzpxmpacadcy.supabase.co/rest/v1/produtos"
    "?select=id,nome,preco_xof,categoria_slug"
    "&ativo=eq.true"
    "&or=(visibilidade.eq.local,visibilidade.eq.ambos,"
    "and(visibilidade.eq.auto,pais_codigo.eq.GW))"
    "&order=vendas.desc&limit=150"
)


def clean(value):
    return " ".join(str(value or "").split())


def parse_products(response):
    try:
        products = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(products, list):
        return

    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for product in products:
        if not isinstance(product, dict):
            continue
        product_id = clean(product.get("id"))
        name = clean(product.get("nome"))
        if not product_id or not name or product_id in seen:
            continue
        try:
            price = Decimal(str(product.get("preco_xof")))
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": clean(product.get("categoria_slug") or "general merchandise")[:500],
            "price": format(price, "f"),
            "currency": "XOF",
            "country": "Guinea-Bissau",
            "sector": "consumer_goods",
            "available": True,
            "url": f"https://compraexpress.app/produto/{product_id}",
            "language": "pt",
            "scraped_at_utc": scraped_at,
        }


class GuineaBissauCompraexpressSpider(scrapy.Spider):
    name = "guinea_bissau_compraexpress"
    allowed_domains = ["dzxmasurrzpxmpacadcy.supabase.co"]
    start_urls = [API_URL]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "apikey": API_KEY,
            "Authorization": f"Bearer {API_KEY}",
            "Referer": "https://compraexpress.app/",
        },
    }

    def parse(self, response):
        yield from parse_products(response)
