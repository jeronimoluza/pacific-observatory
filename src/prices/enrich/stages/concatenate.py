"""Concatenate raw price artifacts into outputs/prices/raw/raw_prices.csv.

Walks data/prices/<region>/<subregion>/<country>/<source>/ for three on-disk
shapes and emits one CSV per source dir, then concatenates them into
raw_prices.csv. A sidecar tracks per-source (max_mtime, file_count) so
unchanged sources are skipped on re-runs.

Shapes handled:
  - raw_items/*.jsonl                  (Scrapy)
  - wayback_items/*.jsonl              (Wayback Machine)
  - common_crawl_data/items/*.json     (Common Crawl, one product per file)

Output schema (15 cols, raw-only — no enrichment-derived columns):
  url_hash, product_name, price, currency, country, source, date,
  product_url, product_id, region, subregion, wayback, channel, category,
  details

`channel` is per-row, looked up from the source YAML's `channel:` field at
startup. `category` is the per-item breadcrumb captured by Scrapy spiders
(`ProductItem.category`). `details` is the per-item size/pack string some
spiders capture separately from the name (e.g. pickaroo "~500 g"); it carries
the quantity the product_name omits and is consulted by the structural
extractor as a fallback. All default to "" when absent.

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
import yaml

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
    "channel",
    "category",
    "details",
]

# The coicop_classification value that routes a fetcher manifest's rows into
# the classifier corpus (see _build_classifier_csv_map). Shared here so a
# future rename of the marker only needs one edit.
CLASSIFIER_MARKER = "classifier"


_CHANNEL_MAP_CACHE: Optional[dict[tuple[str, str], str]] = None


def _build_source_channel_map() -> dict[tuple[str, str], str]:
    """Walk per-source YAMLs and return {(country, source): channel}. Missing
    or invalid channels are omitted; callers default to ``""``."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:  # malformed YAML or schema mismatch — skip silently
            continue
        if cfg.channel:
            out[(cfg.country, cfg.source)] = cfg.channel
    return out


_CLASSIFIER_CSV_MAP_CACHE: Optional[dict[tuple[str, str], str]] = None


def _build_classifier_csv_map() -> dict[tuple[str, str], str]:
    """Return {(country, source): channel} for ``scaffolding: fetcher`` sources
    whose COICOP is ``classifier`` — the fetcher price_observations.csv rows
    that belong in the classifier corpus (e.g. wholesale live-animals). Keyed by
    the config's path components (country dir, filename stem) to match the data
    walk. Read via raw YAML because PriceSourceConfig rejects fetcher manifests."""
    out: dict[tuple[str, str], str] = {}
    cfg_root = config.REPO_ROOT / "src" / "prices" / "configs"
    if not cfg_root.is_dir():
        return out
    for path in cfg_root.rglob("*.yaml"):
        try:
            y = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # malformed YAML — skip silently
            continue
        if not isinstance(y, dict):
            continue
        if (
            y.get("coicop_classification") == CLASSIFIER_MARKER
            and y.get("scaffolding") == "fetcher"
        ):
            out[(path.parent.name, path.stem)] = y.get("channel") or ""
    return out


def _classifier_csv_map() -> dict[tuple[str, str], str]:
    global _CLASSIFIER_CSV_MAP_CACHE
    if _CLASSIFIER_CSV_MAP_CACHE is None:
        _CLASSIFIER_CSV_MAP_CACHE = _build_classifier_csv_map()
    return _CLASSIFIER_CSV_MAP_CACHE


def _channel_for(country: str, source: str) -> str:
    global _CHANNEL_MAP_CACHE
    if _CHANNEL_MAP_CACHE is None:
        _CHANNEL_MAP_CACHE = _build_source_channel_map()
    ch = _CHANNEL_MAP_CACHE.get((country, source))
    if ch:
        return ch
    return _classifier_csv_map().get((country, source), "")


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
                "category": obj.get("category") or "",
                "details": obj.get("details") or "",
            }


def _emit_cc(path: Path) -> Iterable[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    yield _cc_row(obj)


def _emit_cc_jsonl(path: Path) -> Iterable[dict]:
    from prices.cc_storage import iter_jsonl

    for obj in iter_jsonl(path):
        yield _cc_row(obj)


def _cc_row(obj: dict) -> dict:
    return {
        "product_name": obj.get("product_name"),
        "price": obj.get("price"),
        "currency": obj.get("currency"),
        "date": obj.get("cc_timestamp") or obj.get("scraped_at"),
        "product_url": obj.get("url"),
        "product_id": obj.get("product_id"),
        "url_hash": _url_hash(obj.get("url")),
        "wayback": False,
        "category": obj.get("category") or "",
        "details": obj.get("details") or "",
    }


def _emit_price_obs(path: Path) -> Iterable[dict]:
    """Map a fetcher price_observations.csv row to the corpus schema. The item
    name is the product; the observation hash gives a stable url_hash."""
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception:  # noqa: BLE001 — unreadable CSV
        return
    for r in df.to_dict("records"):
        name = r.get("item_name")
        if not isinstance(name, str) or not name.strip():
            continue
        yield {
            "product_name": name,
            "price": r.get("price_local"),
            "currency": r.get("currency"),
            "date": r.get("observation_date"),
            "product_url": r.get("source_url"),
            "product_id": None,
            "url_hash": r.get("observation_hash") or _url_hash(r.get("source_url")),
            "wayback": False,
            "category": "",
        }


def _iter_source_files(
    source_dir: Path, country: Optional[str] = None, source: Optional[str] = None
) -> list[tuple[str, Path]]:
    """Return [(shape, path), ...] for all raw artifacts under a source dir.

    A fetcher's ``price_observations.csv`` is included only for sources declared
    ``classifier`` (see ``_classifier_csv_map``); tariff/fuel/telco fetchers
    are source-curated and must not enter the div-01 classifier corpus."""
    out: list[tuple[str, Path]] = []
    raw = source_dir / "raw_items"
    if raw.is_dir():
        out.extend(("jsonl", p) for p in raw.glob("*.jsonl"))
    wb = source_dir / "wayback_items"
    if wb.is_dir():
        out.extend(("wayback", p) for p in wb.glob("*.jsonl"))
    cc = source_dir / "common_crawl_data" / "items"
    if cc.is_dir():
        # Both layouts: one JSON per record (pre-compaction) and one JSONL per
        # crawl. A corpus captured before the change is still read in place.
        out.extend(("cc", p) for p in cc.glob("*.json"))
        out.extend(("cc_jsonl", p) for p in cc.glob("*.jsonl"))
    obs = source_dir / "price_observations.csv"
    if obs.is_file() and (country, source) in _classifier_csv_map():
        out.append(("price_obs", obs))
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
    files = _iter_source_files(source_dir, country, source)
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
        elif shape == "cc_jsonl":
            rows.extend(_emit_cc_jsonl(path))
        elif shape == "price_obs":
            rows.extend(_emit_price_obs(path))
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
    df["channel"] = _channel_for(country, source)
    if "category" not in df.columns:
        df["category"] = ""
    else:
        df["category"] = df["category"].fillna("").astype(str)
    if "details" not in df.columns:
        df["details"] = ""
    else:
        df["details"] = df["details"].fillna("").astype(str)

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
        files = _iter_source_files(source_dir, country, source)
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
