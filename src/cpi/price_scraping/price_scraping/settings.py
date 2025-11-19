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

# Disable cookies
COOKIES_ENABLED = False

# Middleware
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "price_scraping.middlewares.CustomUserAgentMiddleware": 543,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 590,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 750,
}

# Item pipelines
ITEM_PIPELINES = {
    "price_scraping.pipelines.DuplicationPipeline": 300,
    "price_scraping.pipelines.JsonWriterPipeline": 400,
    "price_scraping.pipelines.LoggingPipeline": 500,
}

# Output directory for scraped data
OUTPUT_DIR = "data"

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
