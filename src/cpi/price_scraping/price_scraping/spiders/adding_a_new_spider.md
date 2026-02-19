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

---

## Learnings from Batch Spider Creation Session (Feb 2026)

This section documents lessons learned from creating and debugging 26 new spiders across 13 countries in a single session.

### 1. Four Spider Architecture Types

Not all sites can be scraped the same way. Choose the right architecture based on how the site serves data:

| Architecture | When to Use | Example Spiders |
|---|---|---|
| **CrawlSpider** | Server-rendered HTML with product data in raw HTML | `jianke`, `exta`, `citypharm`, `south_star_drug`, `pharmacy_111` |
| **REST API** | Site has a public JSON API for products | `boots_th` |
| **GraphQL API** | Site uses Magento/PWA with GraphQL endpoint | `guardian_my`, `guardian_sg`, `mannings` |
| **Playwright** | JS-rendered SPA where products only appear after JS execution | `fairprice` |

**Key insight**: Always check for APIs first before resorting to Playwright. APIs are faster, more reliable, and less likely to be blocked.

### 2. How to Discover APIs

Before writing a CrawlSpider or Playwright spider, check if the site has an API:

```python
# Use Playwright to intercept API calls on page load
import asyncio
from playwright.async_api import async_playwright

async def find_apis(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        api_calls = []
        async def on_response(response):
            ct = response.headers.get('content-type', '')
            if 'json' in ct:
                body = await response.text()
                if len(body) > 500:
                    api_calls.append((response.url, len(body)))
        page.on('response', on_response)
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(5000)
        for u, sz in api_calls:
            print(f'  [{sz}b] {u}')
        await browser.close()

asyncio.run(find_apis('https://example.com/'))
```

**Signs of a GraphQL API**: URL contains `/graphql`, response has `{"data": {...}}` structure. Common on Magento PWA sites (Guardian, Mannings).

**Signs of a REST API**: URL contains `/api/v1/products` or similar. Check for pagination params like `?page=1&size=50`.

### 3. GraphQL Spider Pattern (Magento PWA)

Guardian Malaysia, Guardian Singapore, and Mannings all use the same Magento GraphQL pattern. If a site uses Magento PWA Studio, try this query:

```python
PRODUCTS_QUERY = """
query GetProducts($categoryId: String!, $pageSize: Int!, $currentPage: Int!) {
  products(
    filter: { category_id: { eq: $categoryId } }
    pageSize: $pageSize
    currentPage: $currentPage
  ) {
    items { name sku price_range { minimum_price { final_price { value currency } } } url_key }
    total_count
  }
}
"""
```

To discover category IDs:
```bash
curl -s 'https://www.example.com/graphql' \
  -H 'Content-Type: application/json' \
  -d '{"query":"query{category(id:2){children{id name children_count}}}"}'
```

### 4. REST API Spider Pattern

For sites with REST APIs (like Boots Thailand):

```python
class BootsThSpider(scrapy.Spider):
    def start_requests(self):
        yield scrapy.Request(
            f"{API_BASE}?page=1&size=50",
            callback=self.parse_api,
            headers={"Accept": "application/json"},
            meta={"page": 1},
        )

    def parse_api(self, response):
        data = json.loads(response.text)
        for product in data.get("entities", []):
            yield { ... }
        # Paginate
        if current_page < total_pages:
            yield scrapy.Request(next_url, ...)
```

### 5. CrawlSpider: Always Verify URL Patterns First

Before writing a CrawlSpider, use `curl` and `grep` to verify:

```bash
# Check what links exist on the homepage
curl -s "https://www.example.com/" | grep -oE 'href="[^"]*"' | \
  grep -i "product\|item\|shop\|category" | sort -u | head -20

# Check if a product page has data in raw HTML
curl -s "https://www.example.com/product/123.html" | \
  grep -oE '<h1[^>]*>[^<]*</h1>'

# Check for prices in raw HTML
curl -s "https://www.example.com/product/123.html" | \
  grep -oE '(¥|￥|\$|RM|Rp|฿|₱)[\d.,]+'
```

**Common mistakes**:
- Wrong `start_urls` (e.g., `/category/medicine` when the site uses `/product-category/medicine`)
- Wrong `LinkExtractor` patterns (e.g., `/product/` when products are at `/item/`)
- Selectors that work on listing pages but not product pages (or vice versa)

### 6. Embedded JSON in HTML

Some sites (like Cosmed) use Angular/React templates that don't render in raw HTML, but embed the product data as JSON in `<script>` tags or inline JavaScript:

```python
import re

def parse_product(self, response):
    # Extract from embedded JSON
    title_match = re.search(r'"Title"\s*:\s*"([^"]+)"', response.text)
    price_match = re.search(r'"Price"\s*:\s*([\d.]+)', response.text)
    product_name = title_match.group(1) if title_match else None
    price = price_match.group(1) if price_match else None
```

**How to detect**: `curl` the page and search for product data in the raw HTML. If the `<h1>` is empty but you find `"productName":"Widget"` in a script block, use regex extraction.

### 7. WooCommerce Sites

WooCommerce sites (like Exta, Doctor OnCall) have predictable patterns:
- **URLs**: `/product/{slug}`, `/product-category/{slug}`, `/page/{n}`
- **Price selector**: `span.woocommerce-Price-amount bdi::text`
- **Breadcrumbs**: `nav.woocommerce-breadcrumb a::text`
- **Product name**: `h1.product_title::text`

### 8. Anti-Bot Protection Tiers

Sites fall into tiers of anti-bot difficulty:

| Tier | Behavior | Examples | Strategy |
|---|---|---|---|
| **None** | Raw HTML has all data | `jianke`, `exta`, `citypharm` | CrawlSpider |
| **Light** | Needs JS for prices only | `cosmed` | CrawlSpider + JSON regex |
| **Medium** | Full SPA, but has API | `guardian_*`, `mannings`, `boots_th` | API spider |
| **Heavy** | SPA + Cloudflare/Akamai | `watsons_*`, `chemist_warehouse` | Blocked; need proxy/cookies |
| **Extreme** | Connection refused | All Watsons regional sites | Cannot scrape without specialized infra |

### 9. Scrapy-Playwright: The HTML Tag Trap

When a Playwright spider returns 0 items despite a large response (100K+ chars), the **most common root cause is the wrong HTML tag in the CSS selector**, not a rendering issue.

Product card containers vary by site framework:
- `<div class="product">` — generic / custom themes
- `<li class="product">` — K24Klik (Indonesia)
- `<section class="product">` — Doctor OnCall WooCommerce theme

If `div.product` returns 0 but `.product` returns 28+, the tag is wrong. **Always verify the actual tag**:

```python
from scrapy.http import HtmlResponse

response = HtmlResponse(url='test', body=html.encode('utf-8'))
products = response.css('.product')
if products:
    print(f'Tag: {products[0].root.tag}')  # Shows: li, section, div, etc.
```

### 10. Scrapy-Playwright Configuration That Works

The working pattern (used by `fairprice`, `k24klik`, `doctor_oncall`):

```python
custom_settings = {
    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    "PLAYWRIGHT_LAUNCH_OPTIONS": {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    },
    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,
    "DOWNLOAD_DELAY": 3,
    "RANDOMIZE_DOWNLOAD_DELAY": True,
    "CONCURRENT_REQUESTS": 1,
}
```

Key meta settings for requests:
```python
meta={
    "playwright": True,
    "playwright_include_page": True,          # REQUIRED — get the page object
    "playwright_page_goto_kwargs": {
        "wait_until": "domcontentloaded",     # Don't wait for networkidle
    },
    "playwright_page_methods": [
        PageMethod("wait_for_timeout", 5000),
        PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight / 2)"),
        PageMethod("wait_for_timeout", 2000),
        PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
        PageMethod("wait_for_timeout", 2000),
    ],
}
```

**Critical**: The parse method must be `async` and must close the page:
```python
async def parse_listing(self, response):
    playwright_page = response.meta.get("playwright_page")
    if playwright_page:
        await playwright_page.close()
    # ... rest of parsing
```

**Do NOT** set `DOWNLOAD_HANDLERS` or `TWISTED_REACTOR` in `custom_settings` — they are already in the global `settings.py`. Overriding them in `custom_settings` can cause conflicts.

### 11. Playwright Listing Page Extraction Tips

When extracting from listing pages (not individual product pages), use these strategies:

**Product name**: Prefer `img::attr(alt)` or `h3 a::text` over `*::text` (which picks up CSS/JS noise):
```python
# K24Klik: img alt has clean name (strip "Apotek Online - " prefix)
name = card.css("img.lazy::attr(alt)").get()

# Doctor OnCall: h3 > a has the product name
name = card.css("h3 a::text").get()
```

**Price**: Use targeted selectors (`span::text, p::text`) instead of `*::text` to avoid picking up `<style>` and `<script>` content:
```python
card_texts = card.css("span::text, p::text").getall()
all_text = " ".join(t.strip() for t in card_texts if t.strip())
price_match = re.search(r"Rp\s*([\d.,]+)", all_text)
```

**Product URL**: Some listing pages use `javascript:void(0)` links. Filter these out:
```python
product_url = card.css("a::attr(href)").get()
if product_url and product_url.startswith("javascript"):
    product_url = None
```

### 12. Selector Debugging Workflow

When selectors don't match:

1. **Download the page**: `curl -s -L "URL" -o /tmp/page.html`
2. **Search for the known value**: `python3 -c "html=open('/tmp/page.html').read(); idx=html.find('KNOWN_VALUE'); print(html[idx-200:idx+200])"`
3. **Find the container class**: Look at the HTML around the value for class names
4. **Update selectors in `selectors.py`**: Use the discovered class names
5. **Test**: `poetry run python src/cpi/price_scraping/run_spider.py spider_name --limit 3`

### 13. Centralized Selectors Pattern

All CSS selectors are in `selectors.py` using the `SelectorExtractor` utility. This allows:
- Multiple fallback selectors per field (tried in order)
- Easy updates when sites change their HTML
- Reuse across spiders and wayback scraping

```python
# In selectors.py
"my_spider": {
    "product_name": [
        "h1.product-title::text",     # Primary
        "h1::text",                     # Fallback 1
        "meta[property='og:title']::attr(content)",  # Fallback 2
    ],
    "price": [ ... ],
    "category": [ ... ],
}
```
