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

import time
import random

from .selectors import get_selectors, extract_with_fallback

logger = logging.getLogger(__name__)


class WaybackScraper:
    """Scrapes historical product data from Wayback Machine archives."""
    
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
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
    
    def _get_existing_url_hashes(self, country: str) -> set:
        """
        Get set of URL hashes that already have saved wayback data.
        
        Args:
            country: Country code for directory structure
            
        Returns:
            Set of existing URL hashes
        """
        wayback_dir = self.output_dir / country / self.spider_name / "wayback_machine_data"
        existing_hashes = set()
        
        if wayback_dir.exists():
            for json_file in wayback_dir.glob("*.json"):
                # Extract hash from filename (e.g., "b9f46c47a99e6b42b9cf70700e05b8f5.json")
                url_hash = json_file.stem
                existing_hashes.add(url_hash)
        
        return existing_hashes
    
    def _extract_data_from_html(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract product data from HTML using spider selectors with fallback support.
        
        Args:
            html_content: HTML content to parse
            url: Original URL for error logging
            
        Returns:
            Dictionary with extracted data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        extracted = {}
        
        for field, selector_list in self.selectors.items():
            value = extract_with_fallback(soup, selector_list)
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
            response = requests.get(wayback_url, timeout=120, headers={'User-Agent': self.USER_AGENT})
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
        
        # Get existing URL hashes to skip
        existing_hashes = self._get_existing_url_hashes(country)
        items_to_scrape = [(url, url_hash) for url, url_hash in unique_items if url_hash not in existing_hashes]
        
        logger.info(f"Processing {len(unique_items)} unique URLs from {len(items)} total items")
        logger.info(f"Skipping {len(unique_items) - len(items_to_scrape)} URLs that already have saved data")
        logger.info(f"Scraping {len(items_to_scrape)} new URLs")
        
        stats = {
            "total_items": len(items),
            "unique_urls": len(unique_items),
            "skipped_urls": len(unique_items) - len(items_to_scrape),
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_snapshots": 0,
        }
        
        # Scrape wayback data for each unique URL
        for url, url_hash in tqdm(items_to_scrape, desc="Scraping wayback machine"):
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
            
            time.sleep(random.uniform(2.5, 5.0))
        
        return stats
