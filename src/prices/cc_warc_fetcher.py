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
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import click
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .cc_config import DEFAULT_CC_INDEXES, SPIDER_CC_CONFIG
from .price_scraping.selectors import extract_with_fallback, get_selectors

logger = logging.getLogger(__name__)

CC_INDEX_API = "https://index.commoncrawl.org"
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

    # Safety cap: max pages per index (prevents runaway loops if CC misbehaves).
    # cc_limit=5000 × MAX_PAGES_PER_INDEX=40 = 200k records ceiling per (spider, index).
    MAX_PAGES_PER_INDEX = 40

    def _fetch_index_page(
        self, index: str, from_urlkey: Optional[str] = None
    ) -> Optional[str]:
        """Single CC index API call. Returns raw stdout (JSONL) or None on failure."""
        api = (
            f"{CC_INDEX_API}/{index}-index"
            f"?url={self.url_prefix}&matchType=prefix"
            f"&output=json&limit={self.cc_limit}"
        )
        if from_urlkey:
            # CC index uses urlkey ordering; `from=` is inclusive.
            api += f"&from={from_urlkey}"
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
            logger.warning(f"CC index timeout for {index} (from={from_urlkey})")
            return None
        if result.returncode != 0:
            logger.warning(f"CC index query failed for {index}: {result.stderr[:200]}")
            return None
        return result.stdout

    def _query_index(self, index: str) -> List[Dict[str, Any]]:
        """Query the CC index API for this spider's URL prefix.

        Pages through all results via the ``from=<urlkey>`` cursor. Returns
        records that have ``status=200`` AND match the product-path regex.
        """
        records: List[Dict[str, Any]] = []
        # dedupe across page boundaries (`from=` is inclusive)
        seen_urlkeys: set = set()
        from_urlkey: Optional[str] = None
        page = 0

        for page in range(self.MAX_PAGES_PER_INDEX):
            stdout = self._fetch_index_page(index, from_urlkey=from_urlkey)
            if stdout is None:
                break

            raw_rows = 0
            last_urlkey: Optional[str] = None
            page_kept = 0

            for line in stdout.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                raw_rows += 1
                urlkey = d.get("urlkey")
                if urlkey:
                    last_urlkey = urlkey
                    if urlkey in seen_urlkeys:
                        continue
                    seen_urlkeys.add(urlkey)
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
                page_kept += 1

            logger.info(
                f"{index} page {page + 1}: {raw_rows} raw rows, "
                f"+{page_kept} product records (running total {len(records)})"
            )

            if raw_rows < self.cc_limit:
                break
            if last_urlkey is None:
                logger.warning(
                    f"{index}: page {page + 1} hit limit but had no urlkey to advance; stopping"
                )
                break
            if last_urlkey == from_urlkey:
                logger.warning(
                    f"{index}: page {page + 1} returned same boundary urlkey ({last_urlkey}); stopping"
                )
                break
            from_urlkey = last_urlkey
        else:
            logger.warning(
                f"{index}: hit MAX_PAGES_PER_INDEX={self.MAX_PAGES_PER_INDEX} — "
                f"more records may exist beyond {len(records)} kept"
            )

        logger.info(
            f"{index}: {len(records)} total product-page records across {page + 1} page(s) "
            f"(prefix={self.url_prefix}, path_re={self.path_re.pattern})"
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

    # -- save --

    def _save_item(
        self,
        url: str,
        timestamp: str,
        cc_index: str,
        extracted: Dict[str, Any],
        location: Tuple[str, str, str],
    ) -> Path:
        rec_hash = self._record_hash(url, timestamp)
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
        extracted = self._extract_data_from_html(html)
        if not extracted:
            return "no_extract"
        try:
            self._save_item(rec["url"], rec["timestamp"], cc_index, extracted, location)
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


# ── CLI ─────────────────────────────────────────────────────────────


@click.command("common-crawl")
@click.option(
    "--spider",
    "-s",
    "spider_name",
    default=None,
    help="Spider name (e.g. mh_online). Required unless --dry-run.",
)
@click.option(
    "--country",
    "-c",
    default=None,
    help="Country slug to attribute the records to (resolves region + subregion via regions.yaml).",
)
@click.option(
    "--index",
    "indexes",
    multiple=True,
    help=(
        "CC index name like 'CC-MAIN-2024-51'. Repeatable. "
        "Defaults to the recent-crawl set in cc_config.DEFAULT_CC_INDEXES when omitted."
    ),
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=8,
    show_default=True,
    help="WARC fetch concurrency.",
)
@click.option(
    "--limit",
    type=int,
    default=5000,
    show_default=True,
    help="CC index page size (cc_limit).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List configured spiders with prefix + path_re, then exit.",
)
def common_crawl_command(
    spider_name: Optional[str],
    country: Optional[str],
    indexes: Tuple[str, ...],
    workers: int,
    limit: int,
    dry_run: bool,
) -> None:
    """Fetch historical product data from Common Crawl WARC archives."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
    )

    if dry_run:
        target = (
            {spider_name: SPIDER_CC_CONFIG[spider_name]}
            if spider_name
            else SPIDER_CC_CONFIG
        )
        if spider_name and spider_name not in SPIDER_CC_CONFIG:
            raise click.BadParameter(
                f"unknown spider '{spider_name}'. Available: {sorted(SPIDER_CC_CONFIG)}"
            )
        click.echo(f"{'SPIDER':<22} {'PREFIX':<48} PATH_RE")
        click.echo("-" * 100)
        for name, cfg in sorted(target.items()):
            click.echo(f"{name:<22} {cfg['prefix']:<48} {cfg['path_re']}")
        return

    if not spider_name:
        raise click.UsageError("--spider is required (or use --dry-run)")
    if not country:
        raise click.UsageError(
            "--country is required to place output under data/prices/<region>/<sub>/<country>/"
        )
    if not indexes:
        indexes = tuple(DEFAULT_CC_INDEXES)
        click.echo(f"No --index given; using default set: {', '.join(indexes)}")

    from core.config import get_country_path  # local import to keep startup cheap

    try:
        region, subregion, _ = get_country_path(country)
    except ValueError as exc:
        raise click.BadParameter(str(exc))

    output_dir = get_prices_data_root()
    scraper = CommonCrawlScraper(
        spider_name=spider_name,
        output_dir=output_dir,
        indexes=list(indexes),
        cc_limit=limit,
    )
    stats = scraper.run_scrape_cc((region, subregion, country), num_workers=workers)

    click.echo()
    click.echo(f"Run stats for {spider_name} ({region}/{subregion}/{country}):")
    for k, v in stats.items():
        click.echo(f"  {k:<14} {v}")


if __name__ == "__main__":
    common_crawl_command()
