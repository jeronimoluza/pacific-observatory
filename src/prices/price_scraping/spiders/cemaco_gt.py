"""Cemaco (Guatemala) -- https://www.cemaco.com/. Shard listed this as
Tier-1A custom HTML (apex is a 383-byte S3 meta-refresh stub to
www.cemaco.com), but the www SSR pages embed schema.org JSON-LD with
`cemacogt.vtexassets.com` image URLs and `/api/catalog_system/pub/...`
resolves live -- it is an open VTEX tenant, so this uses VtexBaseSpider
instead of a hand-rolled HTML scrape. Verified live 2026-08-17: category
tree returns 44 top-level nodes, product search returns real GTQ prices
(e.g. "Set de Cama Colchon..." offers lowPrice 5028, priceCurrency GTQ)."""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class CemacoGtSpider(VtexBaseSpider):
    name = "cemaco_gt"
    allowed_domains = ["cemaco.com"]
    HOST = "www.cemaco.com"
    currency = "GTQ"
    language = "es"
