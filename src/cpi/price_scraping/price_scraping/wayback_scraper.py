"""
Wayback Machine scraper for historical product data.
Fetches archived versions of product URLs and extracts data using spider selectors.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import hashlib

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from waybackpy import WaybackMachineCDXServerAPI

from .selectors import get_selectors

logger = logging.getLogger(__name__)


class WaybackScraper:
    """Scrapes historical product data from Wayback Machine archives."""
    
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def __init__(self, spider_name: str, output_dir: Path, from_date: str):
        """
        Initialize Wayback Machine scraper.
        
        Args:
            spider_name: Name of the spider (e.g., 'rbpatel')
            output_dir: Base output directory for scraped data
            from_date: End timestamp for wayback snapshots (YYYY-MM-DD format)
        """
        self.spider_name = spider_name
        self.output_dir = Path(output_dir)
        self.from_date = from_date
        self.selectors = get_selectors(spider_name)
        self.scraped_at = datetime.now().isoformat()
        
    def _get_url_hash(self, url: str) -> str:
        """Generate hash for URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _extract_data_from_html(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract product data from HTML using spider selectors.
        
        Args:
            html_content: HTML content to parse
            url: Original URL for error logging
            
        Returns:
            Dictionary with extracted data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        extracted = {}
        
        for field, selector_list in self.selectors.items():
            value = None
            for selector in selector_list:
                try:
                    # Handle ::text and ::attr() pseudo-elements
                    if '::text' in selector:
                        clean_selector = selector.replace('::text', '')
                        elements = soup.select(clean_selector)
                        if elements:
                            texts = [el.get_text(strip=True) for el in elements]
                            value = texts[0] if texts else None
                            if value:
                                break
                    elif '::attr(' in selector:
                        attr_match = selector.split('::attr(')[1].rstrip(')')
                        clean_selector = selector.split('::attr(')[0]
                        elements = soup.select(clean_selector)
                        if elements:
                            value = elements[0].get(attr_match)
                            if value:
                                break
                    else:
                        # Regular CSS selector
                        elements = soup.select(selector)
                        if elements:
                            value = elements[0].get_text(strip=True)
                            if value:
                                break
                except Exception as e:
                    logger.debug(f"Error extracting {field} with selector {selector}: {e}")
                    continue
            
            if value:
                extracted[field] = value
        
        return extracted
    
    def _fetch_wayback_snapshots(self, url: str) -> List[str]:
        """
        Fetch all available Wayback Machine snapshots for a URL.
        
        Args:
            url: URL to fetch snapshots for
            
        Returns:
            List of wayback archive URLs
        """
        try:
            cdx = WaybackMachineCDXServerAPI(
                url,
                user_agent=self.USER_AGENT,
                end_timestamp=self.from_date
            )
            snapshots = []
            for snapshot in cdx.snapshots():
                snapshots.append(snapshot.archive_url)
            return snapshots
        except Exception as e:
            logger.warning(f"Failed to fetch snapshots for {url}: {e}")
            return []
    
    def _scrape_wayback_url(self, wayback_url: str) -> Optional[str]:
        """
        Fetch content from a Wayback Machine URL.
        
        Args:
            wayback_url: Wayback Machine archive URL
            
        Returns:
            HTML content or None if fetch fails
        """
        try:
            response = requests.get(wayback_url, timeout=10, headers={'User-Agent': self.USER_AGENT})
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug(f"Failed to fetch {wayback_url}: {e}")
            return None
    
    def _extract_timestamp_from_wayback_url(self, wayback_url: str) -> Optional[str]:
        """
        Extract timestamp from Wayback Machine URL.
        
        Args:
            wayback_url: Wayback Machine archive URL
            
        Returns:
            Timestamp in format YYYYMMDDHHMMSS or None
        """
        try:
            # Format: https://web.archive.org/web/20220928054939/https://...
            parts = wayback_url.split('/web/')
            if len(parts) > 1:
                timestamp = parts[1].split('/')[0]
                return timestamp
        except Exception as e:
            logger.debug(f"Failed to extract timestamp from {wayback_url}: {e}")
        return None
    
    def scrape_product_history(self, url: str, url_hash: str) -> List[Dict[str, Any]]:
        """
        Scrape historical data for a single product URL.
        
        Args:
            url: Product URL to scrape history for
            url_hash: Hash of the URL
            
        Returns:
            List of historical snapshots with extracted data
        """
        snapshots = self._fetch_wayback_snapshots(url)
        if not snapshots:
            logger.warning(f"No snapshots found for {url}")
            return []
        
        results = []
        for wayback_url in snapshots:
            html_content = self._scrape_wayback_url(wayback_url)
            if not html_content:
                continue
            
            timestamp = self._extract_timestamp_from_wayback_url(wayback_url)
            extracted_data = self._extract_data_from_html(html_content, url)
            
            # Flatten extracted data into result object
            result = {
                "wayback_url": wayback_url,
                "wayback_timestamp": timestamp,
                "url_hash": url_hash,
                "scraped_at": self.scraped_at,
            }
            # Add all extracted fields to the result
            result.update(extracted_data)
            results.append(result)
        
        return results
    
    def save_wayback_data(self, url_hash: str, data: List[Dict[str, Any]], country: str) -> Path:
        """
        Save wayback data to JSON file.
        
        Args:
            url_hash: Hash of the URL
            data: List of wayback snapshots with extracted data
            country: Country code for directory structure
            
        Returns:
            Path to saved file
        """
        # Create directory structure: data/cpi/price_scraping/{country}/{spider_name}/wayback_machine_data/
        wayback_dir = self.output_dir / country / self.spider_name / "wayback_machine_data"
        wayback_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = wayback_dir / f"{url_hash}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved wayback data to {output_file}")
        return output_file
    
    def run_scrape_wayback(self, items: List[Dict[str, Any]], country: str) -> Dict[str, Any]:
        """
        Run wayback machine scraping for all items.
        
        Args:
            items: List of product items with URLs
            country: Country code for directory structure
            
        Returns:
            Summary statistics
        """
        # Deduplicate items by url_hash
        seen_hashes = set()
        unique_items = []
        for item in items:
            url_hash = self._get_url_hash(item['url'])
            if url_hash not in seen_hashes:
                seen_hashes.add(url_hash)
                unique_items.append((item['url'], url_hash))
        
        logger.info(f"Processing {len(unique_items)} unique URLs from {len(items)} total items")
        
        stats = {
            "total_items": len(items),
            "unique_urls": len(unique_items),
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_snapshots": 0,
        }
        
        # Scrape wayback data for each unique URL
        for url, url_hash in tqdm(unique_items, desc="Scraping wayback machine"):
            try:
                wayback_data = self.scrape_product_history(url, url_hash)
                if wayback_data:
                    self.save_wayback_data(url_hash, wayback_data, country)
                    stats["successful_scrapes"] += 1
                    stats["total_snapshots"] += len(wayback_data)
                else:
                    stats["failed_scrapes"] += 1
            except Exception as e:
                logger.error(f"Error scraping wayback data for {url}: {e}")
                stats["failed_scrapes"] += 1
        
        return stats
