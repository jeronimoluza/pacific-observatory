"""Concatenate raw price artifacts into outputs/prices/raw/raw_prices.csv.

Walks data/prices/<region>/<subregion>/<country>/<source>/ for three on-disk
shapes and emits one CSV per source dir, then concatenates them into
raw_prices.csv. A sidecar tracks per-source (max_mtime, file_count) so
unchanged sources are skipped on re-runs.

Shapes handled:
  - raw_items/*.jsonl                  (Scrapy)
  - wayback_items/*.jsonl              (Wayback Machine)
  - common_crawl_data/items/*.json     (Common Crawl, one product per file)

Output schema (12 cols, raw-only — no enrichment-derived columns):
  url_hash, product_name, price, currency, country, source, date,
  product_url, product_id, region, subregion, wayback

product_name_original is NOT emitted here — prepare derives it. Currency for
Common Crawl rows (which often lack a currency field) is back-filled with the
modal currency observed in the same source's jsonl rows; rows with no
resolvable currency are dropped.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from prices.enrich import config

logger = logging.getLogger(__name__)

DATA_PRICES_ROOT = config.REPO_ROOT / "data" / "prices"
RAW_OUT_DIR = config.REPO_ROOT / "outputs" / "prices" / "raw"
PER_SOURCE_DIR = RAW_OUT_DIR / "_per_source"
RAW_CSV = RAW_OUT_DIR / "raw_prices.csv"
STATE_FILE = RAW_OUT_DIR / ".state.json"

OUTPUT_COLS = [
    "url_hash",
    "product_name",
    "price",
    "currency",
    "country",
    "source",
    "date",
    "product_url",
    "product_id",
    "region",
    "subregion",
    "wayback",
]


def _url_hash(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _emit_jsonl(path: Path, wayback: bool) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield {
                "product_name": obj.get("product_name"),
                "price": obj.get("price"),
                "currency": obj.get("currency"),
                "date": obj.get("scraped_at_utc") or obj.get("scraped_at"),
                "product_url": obj.get("url"),
                "product_id": obj.get("product_id"),
                "url_hash": obj.get("url_hash") or _url_hash(obj.get("url")),
                "wayback": wayback,
            }


def _emit_cc(path: Path) -> Iterable[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    yield {
        "product_name": obj.get("product_name"),
        "price": obj.get("price"),
        "currency": obj.get("currency"),
        "date": obj.get("cc_timestamp") or obj.get("scraped_at"),
        "product_url": obj.get("url"),
        "product_id": obj.get("product_id"),
        "url_hash": _url_hash(obj.get("url")),
        "wayback": False,
    }


def _iter_source_files(source_dir: Path) -> list[tuple[str, Path]]:
    """Return [(shape, path), ...] for all raw artifacts under a source dir."""
    out: list[tuple[str, Path]] = []
    raw = source_dir / "raw_items"
    if raw.is_dir():
        out.extend(("jsonl", p) for p in raw.glob("*.jsonl"))
    wb = source_dir / "wayback_items"
    if wb.is_dir():
        out.extend(("wayback", p) for p in wb.glob("*.jsonl"))
    cc = source_dir / "common_crawl_data" / "items"
    if cc.is_dir():
        out.extend(("cc", p) for p in cc.glob("*.json"))
    return out


def _signature(files: list[tuple[str, Path]]) -> tuple[float, int]:
    if not files:
        return (0.0, 0)
    mtimes = [p.stat().st_mtime for _, p in files]
    return (max(mtimes), len(files))


def _load_source(
    source_dir: Path,
    region: str,
    subregion: str,
    country: str,
    source: str,
) -> Optional[pd.DataFrame]:
    files = _iter_source_files(source_dir)
    if not files:
        return None
    rows: list[dict] = []
    for shape, path in files:
        if shape == "jsonl":
            rows.extend(_emit_jsonl(path, wayback=False))
        elif shape == "wayback":
            rows.extend(_emit_jsonl(path, wayback=True))
        elif shape == "cc":
            rows.extend(_emit_cc(path))
    if not rows:
        return None
    df = pd.DataFrame(rows)

    # Back-fill currency for rows that lack it, using the modal currency
    # observed in this source's other rows.
    if "currency" in df.columns:
        present = df["currency"].dropna()
        present = present[present.astype(str).str.len() > 0]
        if not present.empty:
            modal = Counter(present.astype(str)).most_common(1)[0][0]
            df["currency"] = df["currency"].where(
                df["currency"].notna() & (df["currency"].astype(str).str.len() > 0),
                modal,
            )

    df["country"] = country
    df["source"] = source
    df["region"] = region
    df["subregion"] = subregion

    required = ["product_name", "price", "currency", "country"]
    before = len(df)
    df = df.dropna(subset=required)
    df = df[df["product_name"].astype(str).str.len() > 0]
    dropped = before - len(df)
    if dropped:
        logger.debug(
            "[%s/%s] dropped %d rows missing required fields", country, source, dropped
        )
    if df.empty:
        return None

    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[OUTPUT_COLS]


def _walk_sources(root: Path):
    """Yield (region, subregion, country, source, source_dir) tuples."""
    for region_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")
    ):
        for sub_dir in sorted(p for p in region_dir.iterdir() if p.is_dir()):
            for country_dir in sorted(p for p in sub_dir.iterdir() if p.is_dir()):
                for source_dir in sorted(
                    p for p in country_dir.iterdir() if p.is_dir()
                ):
                    yield (
                        region_dir.name,
                        sub_dir.name,
                        country_dir.name,
                        source_dir.name,
                        source_dir,
                    )


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            logger.warning("state file %s is corrupt; ignoring", STATE_FILE)
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def run(force: bool = False) -> Path:
    if not DATA_PRICES_ROOT.is_dir():
        raise FileNotFoundError(f"{DATA_PRICES_ROOT} not found")
    PER_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    new_state: dict = {}

    n_total = n_refreshed = n_skipped = 0
    for region, subregion, country, source, source_dir in _walk_sources(
        DATA_PRICES_ROOT
    ):
        key = f"{region}/{subregion}/{country}/{source}"
        files = _iter_source_files(source_dir)
        if not files:
            continue
        n_total += 1
        sig = _signature(files)
        per_source_csv = PER_SOURCE_DIR / region / subregion / country / f"{source}.csv"

        prev = state.get(key)
        if not force and prev == list(sig) and per_source_csv.exists():
            new_state[key] = list(sig)
            n_skipped += 1
            continue

        df = _load_source(source_dir, region, subregion, country, source)
        if df is None:
            continue
        per_source_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(per_source_csv, index=False)
        new_state[key] = list(sig)
        n_refreshed += 1
        logger.info("[concatenate] %s: %d rows", key, len(df))

    logger.info(
        "[concatenate] sources: %d total, %d refreshed, %d unchanged",
        n_total,
        n_refreshed,
        n_skipped,
    )

    # Final concat pass — always rebuild raw_prices.csv even when all sources
    # were skipped (so a stale monolith is impossible).
    parts: list[pd.DataFrame] = []
    for csv in sorted(PER_SOURCE_DIR.rglob("*.csv")):
        parts.append(pd.read_csv(csv, low_memory=False))
    if not parts:
        raise RuntimeError("no per-source CSVs produced — check data/prices/ layout")
    full = pd.concat(parts, ignore_index=True)
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(RAW_CSV, index=False)
    logger.info(
        "[concatenate] wrote %s (%d rows from %d sources)",
        RAW_CSV,
        len(full),
        len(parts),
    )

    _save_state(new_state)
    return RAW_CSV


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()
