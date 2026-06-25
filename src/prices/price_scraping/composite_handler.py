from scrapy_impersonate.handler import ImpersonateDownloadHandler
from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler


class CompositeDownloadHandler(ImpersonateDownloadHandler):
    """
    Per-scheme handler that dispatches by request.meta:
      meta['playwright']=True   -> scrapy-playwright (real Chromium, JS rendering)
      meta['impersonate']=<...> -> scrapy-impersonate (curl_cffi, real Chrome TLS)
      otherwise                 -> standard Twisted HTTP11 (fast, fingerprintable)

    Allows the 8 Cloudflare-blocked Shopify spiders to use TLS impersonation while
    keeping Playwright available for citymall_mm and central_th.
    """

    _playwright_handler = None

    @classmethod
    def from_crawler(cls, crawler):
        instance = super().from_crawler(crawler)
        instance._playwright_handler = ScrapyPlaywrightDownloadHandler.from_crawler(
            crawler
        )
        return instance

    def download_request(self, request, spider):
        if request.meta.get("playwright"):
            return self._playwright_handler.download_request(request, spider)
        return super().download_request(request, spider)
