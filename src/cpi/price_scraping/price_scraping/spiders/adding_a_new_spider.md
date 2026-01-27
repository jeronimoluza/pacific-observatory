# Adding a New Spider

This guide documents lessons learned from creating the `rakuten.py` and `yahoo_shopping.py` spiders for Japanese e-commerce sites.

## Key Challenges

### 1. Anti-Bot Protection

Modern e-commerce sites (especially Japanese ones like Rakuten) have strong anti-bot protection:

- **Akamai/Cloudflare**: Returns short responses (40-100 chars) with "Reference #..." messages
- **JavaScript rendering**: Product data often loaded dynamically via JS
- **Rate limiting**: Too many requests trigger blocks

**Solution**: Use `scrapy-playwright` with stealth settings:

```python
custom_settings = {
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    },
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
    "DOWNLOAD_DELAY": 3,
    "RANDOMIZE_DOWNLOAD_DELAY": True,
    "CONCURRENT_REQUESTS": 2,
}
```

### 2. Scraping Strategy: Listing Pages vs Product Pages

**Avoid**: Following individual product links - these are heavily protected and often blocked.

**Prefer**: Extract data directly from category listing/search result pages where product cards show:
- Product name (often in `title` attribute or `alt` text)
- Price (usually in dedicated price elements)
- Product URL (for reference, not for following)

## Step-by-Step Process

### Step 1: Analyze the Website Structure

Before writing code, manually inspect the target website:

```bash
# Check what CSS classes are used for product elements
curl -s "https://example.com/category/food" -H "User-Agent: Mozilla/5.0" | \
  grep -oE 'class="[^"]*[Pp]roduct[^"]*"|class="[^"]*[Ii]tem[^"]*"' | \
  sort | uniq | head -20
```

Look for patterns like:
- `class="item"`, `class="product-card"`, `class="item-price-value"`
- Data attributes: `data-product-id`, `data-price`

### Step 2: Identify Category URLs

Find the URL pattern for category pages:
- Rakuten: `https://search.rakuten.co.jp/search/mall/-/{category_id}/`
- Yahoo Shopping: `https://shopping.yahoo.co.jp/category/{category_id}/recommend`

Create a list of category IDs covering the products you need:

```python
CATEGORY_IDS = [
    ("100227", "食品"),      # Food
    ("2498", "ダイエット"),  # Diet/Health
    # ... more categories
]
```

### Step 3: Create the Spider

Use this template structure:

```python
"""
Spider for scraping [Site Name] - [URL]
"""

import scrapy
import logging
import re
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class MySiteSpider(scrapy.Spider):
    name = "my_site"
    allowed_domains = ["example.com"]
    country = "japan"  # or appropriate country
    currency = "JPY"   # or appropriate currency
    language = "jp"    # or appropriate language

    CATEGORY_IDS = [
        # (category_id, category_name)
    ]

    MAX_PAGES_PER_CATEGORY = 3

    custom_settings = {
        # Playwright settings (see above)
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()  # For deduplication

    def start_requests(self):
        for category_id, category_name in self.CATEGORY_IDS:
            url = f"https://example.com/category/{category_id}/"
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": 1,
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    def parse_listing(self, response):
        # Check response validity
        if len(response.text) < 1000:
            logger.warning(f"Short response: {len(response.text)} chars")
            return

        # Extract product cards
        product_cards = response.css("div.item, li.product-card")

        items_found = 0
        for card in product_cards:
            item = self._parse_product_card(card, response.meta["category_name"])
            if item:
                items_found += 1
                yield item

        logger.info(f"Found {items_found} products")

        # Handle pagination...

    def _parse_product_card(self, card, category_name):
        # Extract with multiple fallback selectors
        product_name = (
            card.css("a::attr(title)").get() or
            card.css("img::attr(alt)").get() or
            card.css("span.name::text").get()
        )

        price_text = (
            card.css("span.price::text").get() or
            card.css("div.price-value::text").get()
        )

        # ... validation and cleaning

        return {
            "product_name": product_name.strip(),
            "category": category_name,
            "price": cleaned_price,
            "currency": self.currency,
            "url": product_url,
            "product_id": product_id,
            "language": self.language,
        }
```

### Step 4: Test Incrementally

```bash
# Test with small page limit first
poetry run python src/cpi/price_scraping/run_spider.py my_site --limit 3

# Check for items scraped
grep "item_scraped_count" in the output

# Inspect output file
head -5 data/cpi/price_scraping/{country}/{spider}/raw_items/*.jsonl
```

### Step 5: Debug Common Issues

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| 0 items, short responses (40-100 chars) | Bot detection | Use Playwright with stealth settings |
| 0 items, long responses (100K+ chars) | Wrong CSS selectors | Inspect actual HTML, update selectors |
| Items found but missing data | Selector mismatch | Add fallback selectors |
| Duplicate items | No deduplication | Track `scraped_product_ids` set |

## CSS Selector Tips

1. **Use multiple fallbacks** - Sites change their HTML frequently:
   ```python
   product_name = (
       card.css("selector1::text").get() or
       card.css("selector2::attr(title)").get() or
       card.css("selector3::text").get()
   )
   ```

2. **Check for data in attributes**:
   - `::attr(title)` - Often contains full product name
   - `::attr(alt)` - Image alt text often has product name
   - `::attr(href)` - URLs contain product IDs

3. **Price cleaning** - Always clean price strings:
   ```python
   def _clean_price(self, price_str):
       if not price_str:
           return None
       cleaned = re.sub(r"[¥￥,\s円$]", "", str(price_str))
       match = re.search(r"(\d+)", cleaned)
       return match.group(1) if match else None
   ```

## Output Requirements

Each scraped item must include:
- `product_name`: String
- `category`: String (from category mapping)
- `price`: String (numeric, cleaned)
- `currency`: String (e.g., "JPY", "USD")
- `url`: String (product URL)
- `product_id`: String (unique identifier)
- `language`: String (e.g., "jp", "en")

## Files to Update

When adding a new spider:

1. **Create spider file**: `spiders/{spider_name}.py`
2. **Add selectors** (optional): `selectors.py` - if using centralized selectors
3. **Test thoroughly** before committing

## Useful Commands

```bash
# Run spider with page limit
poetry run python src/cpi/price_scraping/run_spider.py {spider_name} --limit 10

# Check output
ls -la data/cpi/price_scraping/{country}/{spider_name}/raw_items/

# View scraped data
head -5 data/cpi/price_scraping/{country}/{spider_name}/raw_items/*.jsonl | python3 -m json.tool
```

---

## Advanced Debugging: Lessons from Rakuten Spider

The following sections document hard-won lessons from debugging the Rakuten spider, which initially only scraped 25-30 products instead of thousands.

### Problem: Scraping Sponsored Ads Instead of Real Products

**Symptom**: Spider returns a small number of items (e.g., 25-30) even though the page shows hundreds of products.

**Root Cause**: Many e-commerce sites display **sponsored/ad products** at the top of search results in a carousel or featured section. These ads use different HTML structures and **redirect URLs** for tracking.

**How to Identify**:
1. Check the scraped URLs - ad products often have tracking redirect URLs:
   ```
   # Ad/sponsored URL pattern (BAD - skip these):
   https://grp07.ias.rakuten.co.jp/redirect_rpp/?s=...&ii=...

   # Real product URL pattern (GOOD - keep these):
   https://item.rakuten.co.jp/shop-name/product-id/
   ```

2. Check if categories match - ads often show unrelated products:
   ```
   # Scraping "食品" (food) category but getting towels and cosmetics = ads
   ```

**Solution**: Filter out ad redirect URLs explicitly:
```python
def _parse_product_card(self, card, category_name):
    product_url = card.css("a[href*='item.rakuten.co.jp']::attr(href)").get()

    # Skip sponsored/ad products (redirect URLs)
    if product_url and "ias.rakuten.co.jp/redirect" in product_url:
        return None

    # ... rest of parsing
```

### Problem: CSS Selectors Only Match Ad Section

**Symptom**: Selectors work but only find elements in the sponsored section, not the main product grid.

**Solution**: Use multiple parsing strategies with fallbacks:

```python
async def parse_search_results(self, response):
    items_found = 0

    # Strategy 1: Look for data attributes (most reliable)
    product_cards = response.css("div[data-ratid]")
    for card in product_cards:
        item = self._parse_product_card_v2(card, category_name)
        if item:
            items_found += 1
            yield item

    # Strategy 2: Fallback to class-based selectors
    if items_found == 0:
        product_cards = response.css("div.searchresultitem")
        # ... parse with different method

    # Strategy 3: Extract from embedded JSON
    if items_found == 0:
        scripts = response.css("script::text").getall()
        for script in scripts:
            if '"Items"' in script:
                # Parse JSON data
```

### Problem: Lazy-Loaded Content Not Appearing

**Symptom**: Response is long but product cards are empty or missing.

**Root Cause**: Modern sites lazy-load product images and data as you scroll.

**Solution**: Use Playwright to scroll the page before extracting:

```python
def start_requests(self):
    yield scrapy.Request(
        url,
        meta={
            "playwright": True,
            "playwright_include_page": True,  # Need page object for scrolling
            "playwright_page_goto_kwargs": {
                "wait_until": "domcontentloaded",  # Don't wait for networkidle
            },
            "playwright_page_methods": [
                # Wait for container to load
                PageMethod("wait_for_selector", "div.searchresultitems", timeout=30000),
                # Scroll to trigger lazy loading
                PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight / 2)"),
                PageMethod("wait_for_timeout", 2000),
                PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                PageMethod("wait_for_timeout", 2000),
            ],
        },
    )
```

**Important**: When using `playwright_include_page: True`, close the page after use to free resources:

```python
async def parse_search_results(self, response):
    playwright_page = response.meta.get("playwright_page")
    if playwright_page:
        await playwright_page.close()
    # ... rest of parsing
```

### Problem: Price Not Found in Dedicated Elements

**Symptom**: Price selectors return `None` even though prices are visible on the page.

**Solution**: Search all text for price patterns as a fallback:

```python
def _parse_product_card(self, card, category_name):
    # Try dedicated price elements first
    price_text = (
        card.css("span[class*='price']::text").get()
        or card.css("div[class*='price']::text").get()
    )

    # Fallback: search all text for yen pattern
    if not price_text:
        all_text = " ".join(card.css("*::text").getall())
        price_match = re.search(r'([\d,]+)円', all_text)
        if price_match:
            price_text = price_match.group(1)
```

### Recommended Settings for Heavy Anti-Bot Sites

```python
custom_settings = {
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",  # Prevents crashes in Docker/limited memory
        ],
    },
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,  # 90s for slow pages
    "DOWNLOAD_DELAY": 2,
    "RANDOMIZE_DOWNLOAD_DELAY": True,
    "CONCURRENT_REQUESTS": 1,  # Lower to avoid rate limiting
}
```

### Debugging Checklist

When a spider returns fewer items than expected:

1. **Check URL patterns in output** - Are they real product URLs or ad redirects?
2. **Check category consistency** - Do scraped products match the category being scraped?
3. **Log selector matches** - Add `logger.info(f"Found {len(cards)} cards")` for each strategy
4. **Inspect response length** - Short responses (<5000 chars) often indicate bot detection
5. **Try scrolling** - Lazy-loaded content needs scroll triggers
6. **Look for embedded JSON** - Many sites embed product data in `<script>` tags
7. **Test with browser DevTools** - Manually inspect what selectors should match

### Quick Diagnostic Commands

```bash
# Count items in output file
wc -l data/cpi/price_scraping/{country}/{spider}/raw_items/*.jsonl

# Check for ad redirect URLs in output (should be 0)
grep -c "ias.rakuten.co.jp/redirect" data/cpi/price_scraping/{country}/{spider}/raw_items/*.jsonl

# View sample products with formatting
head -5 *.jsonl | python3 -c "import json,sys; [print(json.dumps(json.loads(l), indent=2, ensure_ascii=False)[:500]) for l in sys.stdin]"

# Check unique categories in output
cat *.jsonl | python3 -c "import json,sys; print(set(json.loads(l)['category'] for l in sys.stdin))"
```
