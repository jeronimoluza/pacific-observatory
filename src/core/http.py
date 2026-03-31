"""Shared HTTP defaults for synchronous fetchers."""

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def make_session(**extra_headers) -> requests.Session:
    """Create a requests.Session with default browser-like headers."""
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    if extra_headers:
        s.headers.update(extra_headers)
    return s
