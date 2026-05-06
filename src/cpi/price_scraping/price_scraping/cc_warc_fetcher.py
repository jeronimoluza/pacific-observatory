"""
Common Crawl WARC fetcher for historical product data.
Queries the CC index API for a spider's product URL prefix, fetches matching
WARC records via HTTP Range, and runs spider selectors over the archived HTML.

Mirrors the data layout used by wayback_scraper.py:
  <output_dir>/<country>/<spider>/common_crawl_data/items/<hash>.json

Dependency-free WARC parsing — each CC byte-range fetch returns a single
gzip member containing one WARC response record.
"""

import gzip
import hashlib
import json
import logging
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .selectors import extract_with_fallback, get_selectors

logger = logging.getLogger(__name__)

CC_INDEX_API = "https://index.commoncrawl.org"
CC_DATA_BASE = "https://data.commoncrawl.org"

# Per-spider CC config:
#   prefix  — URL prefix to feed CC index (matchType=prefix). Pick the narrowest
#             prefix that still covers all product detail pages.
#   path_re — regex applied to URL path to keep only product detail pages
#             (filters out homepage / category / static assets that share the prefix).
SPIDER_CC_CONFIG: Dict[str, Dict[str, str]] = {
    "guardian_sg": {"prefix": "www.guardian.com.sg/", "path_re": r"/[^/]+/p/\d+"},
    "mannings": {"prefix": "www.mannings.com.hk/", "path_re": r"/[^/]+/p/\d+"},
    "guardian_my": {"prefix": "www.guardian.com.my/", "path_re": r"/[^/]+/p/\d+"},
    "cosmed": {
        "prefix": "shop.cosmed.com.tw/SalePage/",
        "path_re": r"/SalePage/Index/",
    },
    "boots_th": {
        "prefix": "store.boots.co.th/ecommerce/",
        "path_re": r"/ecommerce/\d+",
    },
}


class CommonCrawlScraper:
    """Scrapes historical product data from Common Crawl WARC archives."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        spider_name: str,
        output_dir: Path,
        indexes: List[str],
        cc_limit: int = 5000,
    ):
        if spider_name not in SPIDER_CC_CONFIG:
            raise KeyError(
                f"No CC config for {spider_name}. "
                f"Add an entry in SPIDER_CC_CONFIG. "
                f"Available: {list(SPIDER_CC_CONFIG.keys())}"
            )
        self.spider_name = spider_name
        self.output_dir = Path(output_dir)
        self.indexes = indexes
        self.cc_limit = cc_limit
        cfg = SPIDER_CC_CONFIG[spider_name]
        self.url_prefix: str = cfg["prefix"]
        self.path_re = re.compile(cfg["path_re"])
        self.selectors = get_selectors(spider_name)
        self.scraped_at = datetime.now().isoformat()
        self._file_lock = threading.Lock()

    # -- helpers --

    def _record_hash(self, url: str, timestamp: str) -> str:
        return hashlib.md5(f"{url}#{timestamp}".encode()).hexdigest()

    def _items_dir(self, country: str) -> Path:
        return (
            self.output_dir / country / self.spider_name / "common_crawl_data" / "items"
        )

    def _existing_hashes(self, country: str) -> set:
        d = self._items_dir(country)
        if not d.exists():
            return set()
        return {f.stem for f in d.glob("*.json")}

    # -- index step --

    def _query_index(self, index: str) -> List[Dict[str, Any]]:
        """
        Query the CC index API for this spider's URL prefix.
        Returns records that have status=200 AND match the product-path regex.
        """
        api = (
            f"{CC_INDEX_API}/{index}-index"
            f"?url={self.url_prefix}&matchType=prefix"
            f"&output=json&limit={self.cc_limit}"
        )
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-s",
                    "--connect-timeout",
                    "60",
                    "--max-time",
                    "180",
                    "--retry",
                    "5",
                    "--retry-delay",
                    "10",
                    "--retry-all-errors",
                    api,
                ],
                capture_output=True,
                text=True,
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"CC index timeout for {index}")
            return []

        if result.returncode != 0:
            logger.warning(f"CC index query failed for {index}: {result.stderr[:200]}")
            return []

        records: List[Dict[str, Any]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("status") != "200":
                continue
            url = d.get("url", "")
            try:
                if not self.path_re.search(urlparse(url).path):
                    continue
            except Exception:
                continue
            try:
                offset = int(d["offset"])
                length = int(d["length"])
            except (KeyError, ValueError):
                continue
            records.append(
                {
                    "url": url,
                    "timestamp": d.get("timestamp", ""),
                    "filename": d.get("filename", ""),
                    "offset": offset,
                    "length": length,
                    "digest": d.get("digest", ""),
                }
            )
        logger.info(
            f"{index}: {len(records)} product-page records "
            f"(prefix={self.url_prefix}, path_re={self.path_re.pattern})"
        )
        if len(records) >= self.cc_limit:
            logger.warning(
                f"{index}: hit cc_limit={self.cc_limit} — there may be more records. "
                f"Consider paging with &from=<urlkey> or narrowing the prefix."
            )
        return records

    # -- WARC fetch + parse --

    def _fetch_warc_record(self, rec: Dict[str, Any]) -> Optional[bytes]:
        """HTTP Range fetch of a single gzipped WARC record."""
        url = f"{CC_DATA_BASE}/{rec['filename']}"
        end = rec["offset"] + rec["length"] - 1
        headers = {
            "User-Agent": self.USER_AGENT,
            "Range": f"bytes={rec['offset']}-{end}",
        }
        for attempt in range(3):
            try:
                r = requests.get(url, headers=headers, timeout=120)
                if r.status_code in (200, 206):
                    return r.content
                logger.debug(
                    f"WARC fetch HTTP {r.status_code} for {url} "
                    f"(attempt {attempt + 1}/3)"
                )
            except Exception as e:
                logger.debug(f"WARC fetch attempt {attempt + 1}/3 failed: {e}")
        return None

    def _extract_html_from_record(self, raw: bytes) -> Optional[str]:
        """
        Decompress a single CC WARC record (gzip) and return the HTML response body.

        WARC layout (after gunzip):
          WARC/1.0\\r\\n
          WARC-Type: response\\r\\n
          ...WARC headers...\\r\\n
          \\r\\n
          HTTP/1.1 200 OK\\r\\n
          ...HTTP headers...\\r\\n
          \\r\\n
          <html>...</html>
        """
        try:
            decompressed = gzip.decompress(raw)
        except Exception as e:
            logger.debug(f"gunzip failed ({len(raw)} bytes): {e}")
            return None

        # Skip WARC envelope.
        sep = decompressed.find(b"\r\n\r\n")
        if sep < 0:
            return None
        http_block = decompressed[sep + 4 :]

        # Skip HTTP response headers.
        sep2 = http_block.find(b"\r\n\r\n")
        if sep2 < 0:
            return None
        body = http_block[sep2 + 4 :]

        # CC may store responses with arbitrary encoding. Try utf-8 then fall back.
        for enc in ("utf-8", "latin-1"):
            try:
                return body.decode(enc, errors="replace")
            except Exception:
                continue
        return None

    def _extract_data_from_html(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        out: Dict[str, Any] = {}
        for field, selector_list in self.selectors.items():
            v = extract_with_fallback(soup, selector_list)
            if v:
                out[field] = v
        return out

    # -- save --

    def _save_item(
        self,
        url: str,
        timestamp: str,
        cc_index: str,
        extracted: Dict[str, Any],
        country: str,
    ) -> Path:
        rec_hash = self._record_hash(url, timestamp)
        out_dir = self._items_dir(country)
        with self._file_lock:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{rec_hash}.json"
            payload = {
                "url": url,
                "cc_timestamp": timestamp,
                "cc_index": cc_index,
                "scraped_at": self.scraped_at,
                **extracted,
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return out_file

    # -- orchestrator --

    def _process_one(self, rec: Dict[str, Any], country: str, cc_index: str) -> str:
        """Fetch + parse one WARC record. Returns 'parsed' / 'fetch_failed' / 'parse_failed' / 'no_extract'."""
        raw = self._fetch_warc_record(rec)
        if raw is None:
            return "fetch_failed"
        html = self._extract_html_from_record(raw)
        if html is None:
            return "parse_failed"
        extracted = self._extract_data_from_html(html)
        if not extracted:
            return "no_extract"
        try:
            self._save_item(rec["url"], rec["timestamp"], cc_index, extracted, country)
            return "parsed"
        except Exception as e:
            logger.debug(f"Save failed: {e}")
            return "save_failed"

    def run_scrape_cc(self, country: str, num_workers: int = 8) -> Dict[str, Any]:
        """
        Iterate over self.indexes, query each, fetch+parse each new record.
        Existing hashes (URL + timestamp) are skipped — safe to interrupt and resume.
        """
        stats: Dict[str, Any] = {
            "indexes": len(self.indexes),
            "queried": 0,
            "skipped": 0,
            "parsed": 0,
            "fetch_failed": 0,
            "parse_failed": 0,
            "no_extract": 0,
            "save_failed": 0,
        }
        existing = self._existing_hashes(country)
        logger.info(
            f"Found {len(existing)} existing CC items for {self.spider_name}/{country}"
        )

        for index in self.indexes:
            records = self._query_index(index)
            stats["queried"] += len(records)
            todo = [
                r
                for r in records
                if self._record_hash(r["url"], r["timestamp"]) not in existing
            ]
            stats["skipped"] += len(records) - len(todo)
            if not todo:
                logger.info(f"{index}: nothing new to fetch")
                continue

            pbar = tqdm(total=len(todo), desc=f"{index} fetch+parse")
            with ThreadPoolExecutor(max_workers=num_workers) as ex:
                futures = {
                    ex.submit(self._process_one, r, country, index): r for r in todo
                }
                for fut in as_completed(futures):
                    outcome = fut.result()
                    stats[outcome] = stats.get(outcome, 0) + 1
                    if outcome == "parsed":
                        existing.add(
                            self._record_hash(
                                futures[fut]["url"], futures[fut]["timestamp"]
                            )
                        )
                    pbar.update(1)
            pbar.close()

        return stats
