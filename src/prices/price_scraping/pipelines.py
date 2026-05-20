"""
Item pipelines for processing and storing scraped data.
"""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import TextIO

from scrapy.exceptions import DropItem as ScrapyDropItem

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
            raise ScrapyDropItem(f"Duplicate URL: {item['url']}")

        self.seen_urls.add(url_hash)
        return item


def _require_attr(spider, name: str) -> str:
    value = getattr(spider, name, None)
    if not isinstance(value, str) or not value:
        raise RuntimeError(
            f"Spider {getattr(spider, 'name', '<unknown>')} missing required "
            f"attribute '{name}'. Pass it via process.crawl(spider, "
            f"{name}=...) from the prices collect CLI."
        )
    return value


class JsonWriterPipeline:
    """Writes items under data/prices/{region}/{sub}/{country}/{source}/raw_items/."""

    def __init__(self):
        self.file: TextIO | None = None
        self.file_path: Path | None = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        region = _require_attr(spider, "prices_region")
        subregion = _require_attr(spider, "prices_subregion")
        country = _require_attr(spider, "prices_country")
        source = _require_attr(spider, "prices_source")
        data_root = _require_attr(spider, "prices_data_root")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_dir = (
            Path(data_root)
            / "prices"
            / region
            / subregion
            / country
            / source
            / "raw_items"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = out_dir / f"{source}_{timestamp}.jsonl"
        self.file = open(filename, "w", encoding="utf-8")
        self.file_path = filename
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
        if self.file is None:
            raise RuntimeError("Output file is not open")

        if "scraped_at_utc" not in item:
            item["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()

        file_handle = self.file

        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        file_handle.write(line)
        file_handle.flush()
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
