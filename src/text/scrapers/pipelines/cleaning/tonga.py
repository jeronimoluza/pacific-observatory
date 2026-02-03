"""
Cleaning functions for Tongan newspapers.

Handles cleaning for:
- Matangi Tonga
"""

import logging
from typing import Optional

from .registry import register_cleaner

logger = logging.getLogger(__name__)


@register_cleaner
def clean_matangi_url(url: str, base_url: str = None) -> Optional[str]:
    """
    Resolve the final article URL for Matangi Tonga by following the 'print' link.

    Matangi Tonga articles are on a separate print-friendly page, so this function
    scrapes the initial URL to find the print URL.

    Args:
        url: The initial article URL from the listing page
        base_url: The base URL for resolving relative links

    Returns:
        The absolute URL to the print-friendly article page, or None if not found
    """
    if not url:
        return None

    import httpx
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    try:
        # Ensure URL is absolute
        absolute_url = (
            urljoin(base_url, url) if base_url and not url.startswith("http") else url
        )

        # Scrape the initial article page to find the print link
        with httpx.Client() as client:
            response = client.get(absolute_url, follow_redirects=True)
            response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        print_link = soup.select_one(".print-page a, .node-main-content .print a")

        if print_link and print_link.get("href"):
            print_url = print_link["href"]
            # Ensure the print URL is absolute
            final_url = urljoin(base_url, print_url) if base_url else print_url
            logger.info(f"Resolved Matangi URL: {url} -> {final_url}")
            return final_url
        else:
            logger.warning(f"No print link found for Matangi URL: {url}")
            # Fallback to the original URL if no print link is found
            return absolute_url

    except Exception as e:
        logger.error(f"Failed to resolve Matangi print URL for {url}: {e}")
        return None
