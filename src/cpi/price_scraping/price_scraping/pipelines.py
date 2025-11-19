"""
Item pipelines for processing and storing scraped data.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DuplicationPipeline:
    """
    Removes duplicate items based on URL hash.
    """

    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item, spider):
        """
        Check for duplicate URLs and filter them out.
        """
        url_hash = hashlib.md5(item.get("url", "").encode()).hexdigest()
        item["url_hash"] = url_hash

        if url_hash in self.seen_urls:
            raise scrapy.exceptions.DropItem(f"Duplicate URL: {item['url']}")

        self.seen_urls.add(url_hash)
        return item


class JsonWriterPipeline:
    """
    Writes items to a JSON file with timestamp.
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "data"))

    def open_spider(self, spider):
        """
        Open output file when spider starts.
        Organizes data by country: data/{country}/raw_items/
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        country = getattr(spider, "country", "unknown")
        spider_name = getattr(spider, "name", "unknown")
        country_dir = self.output_dir / country / spider_name / "raw_items"
        country_dir.mkdir(parents=True, exist_ok=True)
        filename = country_dir / f"{spider_name}_{timestamp}.jsonl"
        self.file = open(filename, "w", encoding="utf-8")
        logger.info(f"Opened output file: {filename}")

    def close_spider(self, spider):
        """
        Close output file when spider finishes.
        """
        if self.file:
            self.file.close()
            logger.info("Closed output file")

    def process_item(self, item, spider):
        """
        Write item to JSON file.
        """
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(line)
        self.file.flush()
        return item


class LoggingPipeline:
    """
    Logs item processing statistics.
    """

    def __init__(self):
        self.item_count = 0

    def process_item(self, item, spider):
        """
        Log item processing.
        """
        self.item_count += 1
        if self.item_count % 10 == 0:
            logger.info(f"Processed {self.item_count} items")
        return item

    def close_spider(self, spider):
        """
        Log final statistics.
        """
        logger.info(f"Spider finished. Total items processed: {self.item_count}")
