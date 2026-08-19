"""Common Crawl WARC fetcher for historical product data.

Queries the CC index API for a spider's product URL prefix, fetches matching
WARC records via HTTP Range, and runs spider selectors over the archived HTML.

Output layout matches the rest of the prices pipeline:
    data/prices/{region}/{sub}/{country}/{spider}/common_crawl_data/items/<hash>.json

Dependency-free WARC parsing — each CC byte-range fetch returns a single
gzip member containing one WARC response record.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .cc_config import all_cc_configs
from .cc_index import query_prefix
from .backfill import _load_spider_parse_html
from .price_scraping.archived import row_from_meta, rows_from_jsonld
from .price_scraping.selectors import extract_with_fallback, get_selectors

logger = logging.getLogger(__name__)

CC_DATA_BASE = "https://data.commoncrawl.org"


def get_prices_data_root(project_root: Optional[Path] = None) -> Path:
    """Return the root directory for the 4-level prices data tree."""
    if project_root is None:
        # src/prices/cc_warc_fetcher.py → project_root is three parents up.
        project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "prices"


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
    ):
        configs = all_cc_configs()
        if spider_name not in configs:
            raise KeyError(
                f"No archive scope for {spider_name}. Set `archive_prefix:` "
                f"(and `archive_path_re:`) on its YAML manifest. "
                f"Available: {sorted(configs)}"
            )
        self.spider_name = spider_name
        self.output_dir = Path(output_dir)
        self.indexes = indexes
        cfg = configs[spider_name]
        self.url_prefix: str = cfg["prefix"]
        self.path_re = re.compile(cfg["path_re"] or "")
        self.parse_html_fn = _load_spider_parse_html(spider_name)
        # Platform-base spiders (Woo/Shopify/VTEX/...) scrape JSON APIs and have
        # no CSS selectors; their `parse_html` hook is the only archived-HTML
        # parser they have. Only demand selectors when there is no hook.
        # A spider with neither a hook nor selectors used to raise here, which
        # closed the archived-parse path to every such source rather than
        # letting the generic JSON-LD/meta tiers try.
        if self.parse_html_fn:
            self.selectors = {}
        else:
            try:
                self.selectors = get_selectors(spider_name)
            except KeyError:
                self.selectors = {}
        self.scraped_at = datetime.now().isoformat()
        self._file_lock = threading.Lock()

    # -- helpers --

    def _record_hash(self, url: str, timestamp: str) -> str:
        return hashlib.md5(f"{url}#{timestamp}".encode()).hexdigest()

    def _items_dir(self, location: Tuple[str, str, str]) -> Path:
        """Return ``<output_dir>/<region>/<sub>/<country>/<spider>/common_crawl_data/items``."""
        region, subregion, country = location
        return (
            self.output_dir
            / region
            / subregion
            / country
            / self.spider_name
            / "common_crawl_data"
            / "items"
        )

    def _existing_hashes(self, location: Tuple[str, str, str]) -> set:
        d = self._items_dir(location)
        if not d.exists():
            return set()
        return {f.stem for f in d.glob("*.json")}

    # -- index step --

    def _query_index(self, index: str) -> List[Dict[str, Any]]:
        """Records for this spider's URL prefix in one CC collection."""
        return query_prefix(index, self.url_prefix, self.path_re)

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
        """Decompress a single CC WARC record and return the HTML response body."""
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

        for enc in ("utf-8", "latin-1"):
            try:
                return body.decode(enc, errors="replace")
            except Exception:
                continue
        return None

    # Spiders that embed product data in ld+json rather than CSS-accessible elements.
    _LDJSON_SPIDERS = {"cosmed", "fairprice", "carrefour_tw"}

    # Spiders that embed price/name in __NEXT_DATA__ JSON (Next.js SPA, no meta price tag).
    _NEXTDATA_SPIDERS = {"tiki"}

    def _extract_ldjson_fallback(self, html: str, out: Dict[str, Any]) -> None:
        m = re.search(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not m:
            return
        raw = m.group(1).strip()
        d = None
        for candidate in (raw, raw.rstrip().rstrip("}")):
            try:
                d = json.loads(candidate)
                break
            except Exception:
                continue
        if d is None:
            return
        if d.get("@type") != "Product":
            return
        if "product_name" not in out:
            name = d.get("name", "")
            if name:
                out["product_name"] = name
        if "price" not in out:
            offers = d.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price")
            if price is not None:
                out["price"] = str(price)
        if "category" not in out:
            cat_m = re.search(r'"ShopCategory_ShowName"\s*:\s*"([^"]+)"', html)
            if cat_m:
                out["category"] = cat_m.group(1)

    def _extract_nextdata_fallback(
        self, soup: "BeautifulSoup", out: Dict[str, Any]
    ) -> None:
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return
        try:
            d = json.loads(tag.string)
        except Exception:
            return
        try:
            data = d["props"]["initialState"]["productv2"]["productData"]["response"][
                "data"
            ]
        except (KeyError, TypeError):
            return
        if not isinstance(data, dict):
            return
        if "product_name" not in out:
            name = data.get("name", "")
            if name:
                out["product_name"] = str(name)
        if "price" not in out:
            price = data.get("price")
            if price is not None:
                out["price"] = str(price)
        if "product_id" not in out:
            pid = data.get("id") or data.get("sku")
            if pid:
                out["product_id"] = str(pid)

    def _extract_data_from_html(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        out: Dict[str, Any] = {}
        for field, selector_list in self.selectors.items():
            v = extract_with_fallback(soup, selector_list)
            if v:
                out[field] = v
        if self.spider_name in self._LDJSON_SPIDERS:
            self._extract_ldjson_fallback(html, out)
        if self.spider_name in self._NEXTDATA_SPIDERS:
            self._extract_nextdata_fallback(soup, out)
        return out

    def _parse_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Rows for one archived page: the spider's hook, else the selectors.

        A `parse_html` hook may yield several rows per page (product variants,
        SKUs); the selector path always yields at most one.
        """
        if self.parse_html_fn is not None:
            try:
                return [r for r in self.parse_html_fn(html, url) if r]
            except Exception:
                logger.debug(f"parse_html failed for {url}", exc_info=True)
                return []
        extracted = self._extract_data_from_html(html)
        if extracted:
            return [extracted]
        if not self.selectors:
            # Neither a hook nor selectors — try the spider-independent
            # schema.org/OpenGraph surfaces before giving up on the page.
            rows = rows_from_jsonld(html, url)
            if rows:
                return rows
            row = row_from_meta(html, url)
            return [row] if row else []
        return []

    # -- save --

    def _save_item(
        self,
        url: str,
        timestamp: str,
        cc_index: str,
        extracted: Dict[str, Any],
        location: Tuple[str, str, str],
        seq: int = 0,
    ) -> Path:
        rec_hash = self._record_hash(url, timestamp)
        if seq:
            rec_hash = f"{rec_hash}_{seq}"
        out_dir = self._items_dir(location)
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

    def _process_one(
        self,
        rec: Dict[str, Any],
        location: Tuple[str, str, str],
        cc_index: str,
    ) -> str:
        """Fetch + parse one WARC record.

        Returns ``parsed`` / ``fetch_failed`` / ``parse_failed`` /
        ``no_extract`` / ``save_failed``.
        """
        raw = self._fetch_warc_record(rec)
        if raw is None:
            return "fetch_failed"
        html = self._extract_html_from_record(raw)
        if html is None:
            return "parse_failed"
        rows = self._parse_rows(html, rec["url"])
        if not rows:
            return "no_extract"
        try:
            for i, row in enumerate(rows):
                self._save_item(
                    rec["url"], rec["timestamp"], cc_index, row, location, seq=i
                )
            return "parsed"
        except Exception as e:
            logger.debug(f"Save failed: {e}")
            return "save_failed"

    def run_scrape_cc(
        self, location: Tuple[str, str, str], num_workers: int = 8
    ) -> Dict[str, Any]:
        """Iterate over ``self.indexes`` and fetch/parse each new record.

        ``location`` is ``(region, subregion, country)``. Existing record
        hashes (URL + timestamp) are skipped — safe to interrupt and resume.
        """
        stats: Dict[str, Any] = {
            "indexes": len(self.indexes),
            "indexes_failed": 0,
            "queried": 0,
            "skipped": 0,
            "parsed": 0,
            "fetch_failed": 0,
            "parse_failed": 0,
            "no_extract": 0,
            "save_failed": 0,
        }
        existing = self._existing_hashes(location)
        logger.info(
            f"Found {len(existing)} existing CC items for "
            f"{self.spider_name}/{location[2]}"
        )

        for index in self.indexes:
            try:
                records = self._query_index(index)
            except Exception as e:
                logger.warning(f"{index}: query failed, skipping this crawl: {e}")
                stats["indexes_failed"] += 1
                continue
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
                    ex.submit(self._process_one, r, location, index): r for r in todo
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
