"""
Scrapy settings for price_scraping project.
Configuration for web scraping behavior, pipelines, and data handling.
"""

# Project name
BOT_NAME = "price_scraping"

# Spider modules
SPIDER_MODULES = ["price_scraping.spiders"]
NEWSPIDER_MODULE = "price_scraping.spiders"

# Obey robots.txt rules (set to False for testing, True for production)
ROBOTSTXT_OBEY = False

# Concurrent requests
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 8
CONCURRENT_REQUESTS_PER_IP = 8

# Download delay (seconds between requests)
DOWNLOAD_DELAY = 0.1

# User agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Enable cookies (required for Cloudflare cf_clearance/__cf_bm session)
COOKIES_ENABLED = True

# Middleware
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "price_scraping.middlewares.CustomUserAgentMiddleware": 543,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 590,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750,
    "scrapy_impersonate.middleware.RandomBrowserMiddleware": 725,
}

# curl_cffi browser pool for TLS-fingerprint impersonation (RandomBrowserMiddleware
# picks one per request). Pinned to Chrome 120 for reproducibility.
IMPERSONATE_BROWSERS = ["chrome120"]

# Item pipelines
ITEM_PIPELINES = {
    "price_scraping.pipelines.DuplicationPipeline": 300,
    "price_scraping.pipelines.JsonWriterPipeline": 400,
    "price_scraping.pipelines.LoggingPipeline": 500,
}

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Retry settings
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Timeout settings
DOWNLOAD_TIMEOUT = 15

# Autothrottle settings
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0
AUTOTHROTTLE_DEBUG = False

# Memory usage optimization
MEMDEBUG_ENABLED = False
TELNETCONSOLE_ENABLED = False

# Composite handler dispatches by request.meta:
#   meta['playwright']=True   -> scrapy-playwright (JS rendering)
#   meta['impersonate']=<...> -> scrapy-impersonate / curl_cffi (real Chrome TLS)
#   otherwise                 -> standard Twisted HTTP11
DOWNLOAD_HANDLERS = {
    "http": "price_scraping.composite_handler.CompositeDownloadHandler",
    "https": "price_scraping.composite_handler.CompositeDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000  # 60 seconds

# Reduce concurrent requests for Playwright to avoid overwhelming the browser
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
