"""Triage the storefront candidates a columnar-index scan turned up.

A candidate from :mod:`prices.cc_table` is only a domain with product-looking
paths. Before it is worth a manifest, three things have to be true: Common
Crawl actually holds the page body, the body still parses, and a price comes
out. All three are answered by fetching a handful of the candidate's archived
pages — the scan already carried the WARC pointers, so no index lookup is
needed — and running the spider-independent extractors over them.

Nothing here needs a spider. ``rows_from_jsonld`` / ``row_from_meta`` read
schema.org and OpenGraph markup, which is a per-storefront template decision:
a site either emits it on every product page or on none. That makes three
samples a reliable read on the whole domain.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests

from .cc_table import duckdb_binary, hits_glob, work_dir
from .price_scraping.archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

CC_DATA_BASE = "https://data.commoncrawl.org"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_warc_record(filename: str, offset: int, length: int) -> Optional[bytes]:
    """HTTP Range fetch of one gzipped WARC record."""
    url = f"{CC_DATA_BASE}/{filename}"
    headers = {
        "User-Agent": USER_AGENT,
        "Range": f"bytes={offset}-{offset + length - 1}",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=120)
            if r.status_code in (200, 206):
                return r.content
            logger.debug(f"WARC HTTP {r.status_code} for {url} (try {attempt + 1}/3)")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"WARC fetch try {attempt + 1}/3 failed: {exc}")
    return None


def html_from_record(raw: bytes) -> Optional[str]:
    """Strip the WARC envelope and HTTP headers off a record, return the body."""
    try:
        decompressed = gzip.decompress(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"gunzip failed ({len(raw)} bytes): {exc}")
        return None
    sep = decompressed.find(b"\r\n\r\n")
    if sep < 0:
        return None
    http_block = decompressed[sep + 4 :]
    sep2 = http_block.find(b"\r\n\r\n")
    if sep2 < 0:
        return None
    return http_block[sep2 + 4 :].decode("utf-8", errors="replace")


def cctld_to_country() -> Dict[str, str]:
    """``ar`` -> ``argentina``, built from Babel's territory names.

    Matched on the English territory name against ``countries.yaml`` rather
    than on any code, because that file carries ISO-3 while a ccTLD is ISO-2
    and the two do not share a prefix reliably (``.ch``/``CHE`` vs ``.cl``/
    ``CHL``). Territories with no matching slug are simply absent — a
    candidate then reports no country rather than a guessed one.
    """
    from babel import Locale

    from core.config import load_countries

    countries = load_countries()

    def norm(value: str) -> str:
        return re.sub(r"[^a-z]", "", value.lower())

    by_name = {norm(v["name"]): slug for slug, v in countries.items()}
    mapping: Dict[str, str] = {}
    for code, name in Locale("en").territories.items():
        if not re.match(r"^[A-Z]{2}$", code):
            continue
        key = norm(name)
        slug = by_name.get(key)
        if slug is None:
            slug = next((s for n, s in by_name.items() if n.startswith(key)), None)
        if slug:
            mapping[code.lower()] = slug
    return mapping


def _query(sql: str) -> List[Dict[str, Any]]:
    result = subprocess.run(
        [duckdb_binary(), "-json", "-c", sql],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"duckdb query failed: {result.stderr[:400]}")
    text = result.stdout.strip()
    return json.loads(text) if text else []


def load_candidates(index: str, top: int, min_paths: int) -> List[Dict[str, Any]]:
    path = work_dir() / index / "candidates.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run `prices cc-table candidates --index {index}` first"
        )
    return _query(
        f"SELECT domain, tld, n_terms, n_paths, n_rows FROM read_parquet('{path}') "
        f"WHERE n_paths >= {min_paths} "
        f"ORDER BY n_terms DESC, n_paths DESC LIMIT {top};"
    )


def collect_pointers(
    index: str, domains: Sequence[str], samples: int
) -> Dict[str, List[Dict[str, Any]]]:
    """WARC pointers per domain, straight from the discovery hits on disk.

    The discover scan projects the WARC triple, so triage reads Common Crawl's
    index not at all — only the archived records themselves. Re-scanning the
    parts here is what stalled the 2026-08-18 run: the index objects had gone
    cold and 503'd on every retry, after the discovery pass had already paid
    for them once. Deepest paths win the sample, since a long path is more
    often a product page than a category listing.
    """
    if not domains:
        return {}
    quoted = ", ".join("'" + d.replace("'", "''") + "'" for d in domains)
    try:
        rows = _query(
            "SELECT domain, url_host_name, url_path, warc_filename, "
            "warc_record_offset, warc_record_length FROM ("
            "  SELECT url_host_registered_domain AS domain, url_host_name, url_path, "
            "warc_filename, warc_record_offset, warc_record_length, "
            "row_number() OVER (PARTITION BY url_host_registered_domain "
            "ORDER BY length(url_path) DESC, url_path) AS rn "
            f"  FROM read_parquet('{hits_glob(index)}') "
            f"  WHERE url_host_registered_domain IN ({quoted}) "
            "    AND warc_filename IS NOT NULL"
            f") WHERE rn <= {samples};"
        )
    except RuntimeError as exc:
        if "warc_filename" in str(exc):
            raise RuntimeError(
                f"{index} discovery hits predate the WARC-pointer projection — "
                f"rerun `prices cc-table scan --index {index} --mode discover`"
            ) from exc
        raise

    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)
    return by_domain


def probe_domain(domain: str, records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Fetch and parse a few of one candidate's archived pages."""
    out: Dict[str, Any] = {
        "domain": domain,
        "n_sampled": len(records),
        "n_fetched": 0,
        "n_parsed": 0,
        "method": None,
        "currency": None,
        "sample_name": None,
        "sample_price": None,
        "prefix_hint": None,
    }
    paths: List[str] = []
    for rec in records:
        url = f"https://{rec['url_host_name']}{rec['url_path']}"
        paths.append(rec["url_path"])
        raw = fetch_warc_record(
            rec["warc_filename"], rec["warc_record_offset"], rec["warc_record_length"]
        )
        if not raw:
            continue
        html = html_from_record(raw)
        if not html:
            continue
        out["n_fetched"] += 1

        rows = rows_from_jsonld(html, url)
        method = "jsonld"
        if not rows:
            row = row_from_meta(html, url)
            rows = [row] if row else []
            method = "meta"
        rows = [r for r in rows if r and r.get("price") is not None]
        if not rows:
            continue
        out["n_parsed"] += 1
        if out["method"] is None:
            out["method"] = method
            out["currency"] = rows[0].get("currency")
            out["sample_name"] = rows[0].get("product_name")
            out["sample_price"] = rows[0].get("price")
    out["prefix_hint"] = _common_prefix(paths)
    return out


def _common_prefix(paths: Sequence[str]) -> Optional[str]:
    """Longest shared leading path segment across the sampled URLs.

    A starting point for ``archive_prefix``, not a finished one — two samples
    can agree on a segment the rest of the catalogue does not use.
    """
    segments = [p.strip("/").split("/") for p in paths if p]
    if not segments:
        return None
    shared: List[str] = []
    for parts in zip(*segments):
        if len({p.lower() for p in parts}) != 1:
            break
        shared.append(parts[0])
    return "/".join(shared) if shared else None


def is_live(domain: str, timeout: int = 15) -> Optional[bool]:
    """Does this domain still answer today? ``None`` when the check itself fails.

    Separates the two things keyword mining turns up: a dead storefront, good
    only for its archived pages, and a live one nobody had put on our list,
    which the normal collector can scrape going forward. Never let a slow or
    hostile host decide the run — a failure here is unknown, not dead.
    """
    for scheme in ("https", "http"):
        try:
            r = requests.head(
                f"{scheme}://{domain}/",
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
            )
            if r.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def triage_index(
    index: str,
    top: int = 200,
    min_paths: int = 3,
    samples: int = 3,
    progress=None,
) -> Path:
    """Probe the top candidates and write a triage table."""
    candidates = load_candidates(index, top, min_paths)
    tld_map = cctld_to_country()
    pointers = collect_pointers(index, [c["domain"] for c in candidates], samples)
    results = []
    for cand in candidates:
        records = pointers.get(cand["domain"], [])
        try:
            if not records:
                raise RuntimeError("no WARC pointers recovered for this domain")
            probe = probe_domain(cand["domain"], records)
        except Exception as exc:  # noqa: BLE001
            # A Common Crawl 503 on one domain's index block must not end the
            # run, and must not be recorded as "no price found" either — that
            # would quietly demote a good candidate on an infrastructure fault.
            logger.warning(f"{cand['domain']}: probe failed — {exc}")
            probe = {
                "domain": cand["domain"],
                "n_sampled": 0,
                "n_fetched": 0,
                "n_parsed": 0,
                "method": None,
                "currency": None,
                "sample_name": None,
                "sample_price": None,
                "prefix_hint": None,
                "error": str(exc)[:200],
            }
        probe.update(
            {
                "live": is_live(cand["domain"]),
                "tld": cand["tld"],
                "n_terms": cand["n_terms"],
                "n_paths": cand["n_paths"],
                "n_rows": cand["n_rows"],
                "country": tld_map.get((cand["tld"] or "").lower()),
                "usable": probe["n_parsed"] > 0,
                "errored": bool(probe.get("error")),
            }
        )
        results.append(probe)
        if progress:
            progress(cand["domain"], probe["n_parsed"])

    out_path = work_dir() / index / "triage.jsonl"
    with out_path.open("w") as fh:
        for row in results:
            fh.write(json.dumps(row) + "\n")
    return out_path


def write_manifest_drafts(index: str, min_parsed: int = 1) -> Path:
    """Draft a YAML manifest per usable candidate, into a staging directory.

    Staged rather than written straight into ``src/prices/configs/`` because a
    draft carries a guessed prefix and, for a ``.com`` domain, no country at
    all — both need a human before they become part of the corpus.
    """
    triage_path = work_dir() / index / "triage.jsonl"
    if not triage_path.exists():
        raise FileNotFoundError(f"{triage_path} missing — run the triage step first")

    out_dir = work_dir() / index / "manifest_drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for line in triage_path.read_text().splitlines():
        row = json.loads(line)
        if row.get("n_parsed", 0) < min_parsed:
            continue
        domain = row["domain"]
        slug = re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_")
        prefix = domain + "/" + (row["prefix_hint"] + "/" if row["prefix_hint"] else "")
        # A live host is a source the normal collector can take over; a dead one
        # is only ever its archive. `None` means the liveness check itself
        # failed, so it stays with the cautious archive-only default.
        #
        # The value matters operationally: `collect.py` dispatches on exactly
        # `spider` and `fetcher`, so anything else is skipped by `prices
        # collect` — correct for a dead source, silently wrong for a live one.
        live = row.get("live") is True
        body = {
            "scaffolding": "spider" if live else "archive_only",
            # Required by PriceSourceConfig and not guessable from a URL path.
            # Left null so the manifest fails loudly on a human's desk rather
            # than carrying an invented channel into the corpus.
            "channel": None,
            "extraction_pattern": "archived_html",
            "analytical_role": "retailer_sku",
            "coicop_classification": "classifier",
            "url": f"https://{domain}/",
            "cadence": "weekly" if live else "none",
            "archive_prefix": prefix,
            "notes": (
                f"Discovered by Common Crawl keyword mining on {index}; never "
                f"scraped by us. Host answers today: "
                f"{ {True: 'yes', False: 'no'}.get(row.get('live'), 'unknown') }. "
                f"{row['n_parsed']}/{row['n_sampled']} sampled archived pages "
                f"yielded a price via {row['method']}. Country from ccTLD "
                f"({row.get('country') or 'UNRESOLVED — set before use'}). "
                f"archive_prefix is a draft from the sampled paths; widen or narrow it "
                f"against the full candidate path list before collecting."
            ),
        }
        # Only a live source is dispatched by `prices collect`, and only then
        # does a spider name mean anything.
        if live:
            body["spider"] = slug
        if row.get("country"):
            body["country"] = row["country"]
        if row.get("currency"):
            body["currency"] = row["currency"]

        import yaml

        (out_dir / f"{slug}.yaml").write_text(
            yaml.safe_dump(body, sort_keys=False, allow_unicode=True)
        )
        written += 1
    logger.info(f"wrote {written} manifest drafts to {out_dir}")
    return out_dir
