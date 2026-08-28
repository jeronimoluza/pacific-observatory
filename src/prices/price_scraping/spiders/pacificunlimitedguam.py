"""Pacific Unlimited Guam -- https://shop.pacificunlimitedguam.com/.

Food-service / HORECA wholesale distributor (bulk pastries, cakes, gelato,
BBQ meats sold in large case-pack units, e.g. "35lbs", "12 servings per
container"). Shopify catalog is open at /products.json — no Playwright, no
WAF encountered on the shop.* custom domain."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class PacificUnlimitedGuamSpider(ShopifyBaseSpider):
    name = "pacificunlimitedguam"
    allowed_domains = ["shop.pacificunlimitedguam.com"]
    base_url = "https://shop.pacificunlimitedguam.com"
    currency = "USD"
    language = "en"
