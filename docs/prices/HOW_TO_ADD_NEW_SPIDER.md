# How to Add a New Supermarket Price Spider

This guide walks through adding a new retailer to the supermarket
prices pipeline. A "spider" is a Scrapy crawler that collects
product names and prices from a retailer's website.

## Prerequisites

- Python 3.11+
- The repository cloned and installed: `pip install -e ".[scraping]"`
- The country must exist in `src/configs/countries.yaml`

## Quick Start

1. Create config: `src/prices/configs/{region}/{country}/{retailer}.yaml`
2. Create spider (if needed): `src/prices/scrapers/{retailer}.py`
3. Test: `po prices collect --source {retailer} --dry-run`
4. Run: `po prices collect --source {retailer}`

## Step 1: Assess the Retailer

Before writing a spider, check:

1. **Does the site have an API?** Open DevTools → Network tab →
   filter XHR. Many sites load products via JSON APIs.
2. **Does it require JavaScript?** If products don't appear in
   `view-source:`, you'll need Scrapy-Playwright.
3. **Does it block scrapers?** Check robots.txt and try a simple
   request. If blocked, you may need rate limiting or Playwright.
4. **What's the product catalog structure?** Note the category
   hierarchy and URL patterns.

## Step 2: Create the YAML Config

Copy the template:
```bash
mkdir -p src/prices/configs/{region}/{country}
cp src/prices/configs/_examples/spider_template.yaml \
   src/prices/configs/{region}/{country}/{retailer}.yaml
```

Fill in the config with:
- Retailer metadata (name, country, currency)
- Category URLs to crawl
- CSS selectors for product extraction
- Rate limiting settings

## Step 3: Write the Spider (if needed)

For simple retailer sites, the generic spider + YAML config may
be sufficient. For complex sites, create a custom Scrapy spider:

```bash
cp src/prices/scrapers/_example_spider.py \
   src/prices/scrapers/{retailer}.py
```

### Spider Contract

```python
class RetailerSpider(scrapy.Spider):
    name = "retailer_slug"

    def start_requests(self):
        # Yield requests for each category URL from config
        ...

    def parse_product_list(self, response):
        # Extract product items from listing page
        ...

    def parse_product(self, response):
        # Extract product details from individual product page
        yield {
            "product_name": "...",
            "price": 12.99,
            "currency": "FJD",
            "url": response.url,
            "category": "...",
            "scraped_at": "...",
        }
```

### Output Schema

| Field | Required | Description |
|-------|----------|-------------|
| `product_name` | Yes | Full product name as shown on site |
| `price` | Yes | Current price (float) |
| `currency` | Yes | ISO 4217 code |
| `url` | Yes | Product page URL |
| `category` | No | Product category from retailer |
| `unit_price` | No | Price per unit (e.g., per kg) |
| `image_url` | No | Product image URL |
| `scraped_at` | Yes | UTC timestamp |

## Step 4: Test

```bash
# Preview crawl plan
po prices collect --source {retailer} --dry-run

# Run with limited pages (edit config: max_pages)
po prices collect --source {retailer}

# Check output
ls data/prices/{country}/{retailer}/raw_items/

# Try classification
po prices build --country {country}
```

## Step 5: Commit

- `src/prices/configs/{region}/{country}/{retailer}.yaml`
- `src/prices/scrapers/{retailer}.py` (if custom spider)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 403 / blocked | Add Playwright: `scrapy-playwright`. Lower concurrency. |
| Product prices wrong | Check selector — dynamic pricing may need JS rendering. |
| Missing products | The site may lazy-load. Check if API endpoints exist. |
| Captcha | Consider Wayback Machine historical data as alternative. |

## Reference

- Config template: `src/prices/configs/_examples/spider_template.yaml`
- Pipeline docs: [docs/prices/PIPELINE.md](PIPELINE.md)
- COICOP classification: [docs/prices/COICOP_CLASSIFICATION.md](COICOP_CLASSIFICATION.md)
