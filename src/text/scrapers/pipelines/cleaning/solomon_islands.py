"""
Cleaning functions for Solomon Islands newspapers.

Handles cleaning for:
- SIBC (Solomon Islands Broadcasting Corporation)
- Solomon Star
- Solomon Times
"""

import logging

from .registry import register_cleaner
from .common import handle_mixed_dates, clean_html_text

logger = logging.getLogger(__name__)


@register_cleaner
def clean_sibc_date(date_str: str) -> str:
    """
    Clean SIBC date format and normalize to YYYY-MM-DD format.

    Args:
        date_str: Raw date string from SIBC

    Returns:
        Normalized date string in YYYY-MM-DD format
    """
    if not date_str:
        return ""

    # Use the handle_mixed_dates function to normalize to YYYY-MM-DD
    return handle_mixed_dates(date_str)


@register_cleaner
def clean_sibc_body(body_text: str) -> str:
    """
    Clean SIBC article body by removing author bylines.

    SIBC articles often start with author bylines like "By Aaron Szetu in Gizo, Western Province".
    This function removes paragraphs that start with "By " to clean the article content.

    Args:
        body_text: Raw article body text

    Returns:
        Cleaned article body text with author bylines removed
    """
    if not body_text:
        return ""

    # Split the text into sentences/paragraphs (assuming they're separated by periods and spaces)
    # or by common paragraph separators
    paragraphs = []

    # Try to split by common paragraph separators first
    if ". " in body_text:
        # Split by '. ' but be careful not to split abbreviations
        parts = body_text.split(". ")
        for i, part in enumerate(parts):
            if i < len(parts) - 1:  # Add the period back except for the last part
                part = part + "."
            paragraphs.append(part.strip())
    else:
        # If no clear paragraph separation, treat as single paragraph
        paragraphs = [body_text.strip()]

    # Filter out paragraphs that start with "By "
    cleaned_paragraphs = []
    for paragraph in paragraphs:
        if paragraph and not paragraph.startswith("By "):
            cleaned_paragraphs.append(paragraph)

    # Join the remaining paragraphs back together
    cleaned_text = " ".join(cleaned_paragraphs).strip()

    return cleaned_text


@register_cleaner
def clean_solomon_star_date(date_str: str) -> str:
    """
    Clean Solomon Star date format.

    Handles pandas "mixed" format parsing that was used in the original scraper:
    urls_df["date"] = pd.to_datetime(urls_df["date"], format="mixed")

    Args:
        date_str: Raw date string from Solomon Star

    Returns:
        Standardized date string (YYYY-MM-DD format)
    """
    if not date_str:
        return ""

    try:
        import pandas as pd

        # Replicate the original pandas "mixed" format processing
        parsed_date = pd.to_datetime(date_str, format="mixed")
        return parsed_date.strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"Could not parse Solomon Star date '{date_str}': {e}")
        # Fallback to handle_mixed_dates function
        return handle_mixed_dates(date_str)


@register_cleaner
def clean_solomon_star_content(content_element) -> str:
    """
    Clean Solomon Star article content.

    Replicates the original scraper logic:
    text = " ".join(p.text for p in text_entry.find_all("p"))

    Args:
        content_element: BeautifulSoup element containing article content

    Returns:
        Cleaned content string with paragraphs joined by spaces
    """
    if not content_element:
        return ""

    try:
        if hasattr(content_element, "find_all"):
            paragraphs = content_element.find_all("p")
            if not paragraphs:
                paragraphs = content_element.find_all("div")
            # Join paragraph text with spaces, filtering out empty paragraphs
            content_parts = [p.text.strip() for p in paragraphs if p.text.strip()]
            return " ".join(content_parts)
        else:
            # If it's already text, clean it
            return clean_html_text(str(content_element))
    except Exception as e:
        logger.error(f"Error cleaning Solomon Star content: {e}")
        return clean_html_text(str(content_element))


@register_cleaner
def clean_solomon_star_tags(tags_element) -> str:
    """
    Clean Solomon Star tags/categories.

    Replicates the original scraper logic:
    tag = ", ".join(p.text for p in tag_entry.find_all("a"))

    Args:
        tags_element: BeautifulSoup element containing category links

    Returns:
        Comma-separated tags string
    """
    if not tags_element:
        return ""

    try:
        if hasattr(tags_element, "find_all"):
            links = tags_element.find_all("a")
            # Join link text with commas, filtering out empty tags
            tag_parts = [link.text.strip() for link in links if link.text.strip()]
            return ", ".join(tag_parts)
        else:
            # If it's already text, return cleaned version
            return clean_html_text(str(tags_element))
    except Exception as e:
        logger.error(f"Error cleaning Solomon Star tags: {e}")
        return clean_html_text(str(tags_element))


@register_cleaner
def clean_solomon_times_date(date_str: str, **kwargs) -> str:
    """
    Clean Solomon Times date format.

    For thumbnails: Extract dates from archive URL paths like:
    "https://www.solomontimes.com/news/latest/2024/05" -> "2024-05-01"

    For articles: Parse date from article content using standard date parsing.

    Args:
        date_str: Raw date string (may be empty for URL-based extraction)
        **kwargs: Additional context including 'page_url' for URL-based extraction

    Returns:
        Standardized date string (YYYY-MM-DD format)
    """
    # Check if we have a page_url in kwargs for URL-based extraction
    page_url = kwargs.get("page_url") or kwargs.get("url")

    # If we have a page URL and it's an archive URL, extract date from path
    if page_url and "/news/latest/" in page_url:
        try:
            # Extract year/month from URL path like the original scraper
            # Original: date = "-".join(i for i in page[0].split("/")[-2:])
            path_parts = page_url.rstrip("/").split("/")
            if len(path_parts) >= 2:
                year = path_parts[-2]
                month = path_parts[-1]

                # Validate year and month
                if year.isdigit() and month.isdigit():
                    year_int = int(year)
                    month_int = int(month)

                    if 2000 <= year_int <= 2030 and 1 <= month_int <= 12:
                        # Return first day of the month in YYYY-MM-DD format
                        return f"{year_int:04d}-{month_int:02d}-01"
        except Exception as e:
            logger.warning(
                f"Could not extract date from Solomon Times URL '{page_url}': {e}"
            )

    # If no URL or URL extraction failed, try to parse date_str from article content
    if date_str and date_str.strip():
        try:
            import pandas as pd

            # Use pandas "mixed" format like the original scraper
            parsed_date = pd.to_datetime(date_str, format="mixed")
            return parsed_date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Could not parse Solomon Times date '{date_str}': {e}")
            # Fallback to handle_mixed_dates function
            return handle_mixed_dates(date_str)

    # If we still don't have a date and we have a page URL, try to extract from any URL
    if page_url:
        try:
            # Try to extract date from any URL pattern
            path_parts = page_url.rstrip("/").split("/")
            for i in range(len(path_parts) - 1):
                year = path_parts[i]
                month = path_parts[i + 1]

                if year.isdigit() and month.isdigit():
                    year_int = int(year)
                    month_int = int(month)

                    if 2000 <= year_int <= 2030 and 1 <= month_int <= 12:
                        return f"{year_int:04d}-{month_int:02d}-01"
        except Exception as e:
            logger.debug(
                f"Could not extract date from any URL pattern '{page_url}': {e}"
            )

    return ""


@register_cleaner
def clean_solomon_times_content(content_element) -> str:
    """
    Clean Solomon Times article content.

    Extracts and cleans text from article body elements, similar to the original scraper
    which extracted content from "article-body" selectors.

    Args:
        content_element: BeautifulSoup element containing article content

    Returns:
        Cleaned content string
    """
    if not content_element:
        return ""

    try:
        if hasattr(content_element, "get_text"):
            # Extract all text from the element
            text = content_element.get_text(separator=" ", strip=True)
            return clean_html_text(text)
        elif hasattr(content_element, "find_all"):
            # If it's a container, extract text from paragraphs
            paragraphs = content_element.find_all(["p", "div"])
            if paragraphs:
                content_parts = [
                    p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                ]
                return " ".join(content_parts)
            else:
                # Fallback to getting all text
                text = content_element.get_text(separator=" ", strip=True)
                return clean_html_text(text)
        else:
            # If it's already text, clean it
            return clean_html_text(str(content_element))
    except Exception as e:
        logger.error(f"Error cleaning Solomon Times content: {e}")
        return clean_html_text(str(content_element))


@register_cleaner
def clean_solomon_times_tags(tags_element) -> str:
    """
    Clean Solomon Times tags/categories.

    Extracts and joins tag text from tag elements, similar to the original scraper
    which processed "tags" selectors.

    Args:
        tags_element: BeautifulSoup element containing tag links

    Returns:
        Comma-separated tags string
    """
    if not tags_element:
        return ""

    try:
        if hasattr(tags_element, "find_all"):
            # Look for links within the tags element
            links = tags_element.find_all("a")
            if links:
                # Join link text with commas, filtering out empty tags
                tag_parts = [
                    link.get_text(strip=True)
                    for link in links
                    if link.get_text(strip=True)
                ]
                return ", ".join(tag_parts)
            else:
                # If no links, try to get text directly
                text = tags_element.get_text(strip=True)
                return clean_html_text(text) if text else ""
        else:
            # If it's already text, return cleaned version
            return clean_html_text(str(tags_element))
    except Exception as e:
        logger.error(f"Error cleaning Solomon Times tags: {e}")
        return clean_html_text(str(tags_element))
