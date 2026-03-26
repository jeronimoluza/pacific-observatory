"""Shared helpers for fuel source inventory outputs."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path
from typing import Any, Iterable

from .constants import STAGED_DATA_DIR
from .fetchers import FETCHER_REGISTRY

_FETCHER_MODULES = [
    "src.cpi.fuel_prices.fetchers.australia",
    "src.cpi.fuel_prices.fetchers.cambodia",
    "src.cpi.fuel_prices.fetchers.fiji",
    "src.cpi.fuel_prices.fetchers.global_commodities",
    "src.cpi.fuel_prices.fetchers.imf_weo_gdp",
    "src.cpi.fuel_prices.fetchers.indonesia",
    "src.cpi.fuel_prices.fetchers.japan",
    "src.cpi.fuel_prices.fetchers.korea",
    "src.cpi.fuel_prices.fetchers.lao",
    "src.cpi.fuel_prices.fetchers.malaysia",
    "src.cpi.fuel_prices.fetchers.mongolia",
    "src.cpi.fuel_prices.fetchers.myanmar",
    "src.cpi.fuel_prices.fetchers.new_zealand",
    "src.cpi.fuel_prices.fetchers.pacific_islands",
    "src.cpi.fuel_prices.fetchers.philippines",
    "src.cpi.fuel_prices.fetchers.thailand",
    "src.cpi.fuel_prices.fetchers.timor_leste",
    "src.cpi.fuel_prices.fetchers.vietnam",
    "src.cpi.fuel_prices.fetchers.world_bank_population",
]

DEFAULT_ENRICHED_CSV = STAGED_DATA_DIR / "enrich" / "retail_series_enriched.csv"
SOURCE_INVENTORY_COLUMNS = [
    "source_key",
    "source_url",
    "n_observations",
    "n_products",
    "start_date",
    "end_date",
    "cadence",
    "objective",
]

_OBJECTIVE_VALUES = {
    "country fuel prices",
    "commodity prices",
    "ancillary data",
}

_OBJECTIVE_OVERRIDES = {
    "global_investing_daily": "commodity prices",
    "au_aip_tgp_weekly": "ancillary data",
    "pw_ops_fuel_prices_quarterly": "ancillary data",
}

_GPP_SOURCE_URL = "https://www.globalpetrolprices.com/"


def collect_all_meta(
    fetcher_modules: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Import fetcher modules and collect SOURCE_META entries."""
    modules = list(fetcher_modules or _FETCHER_MODULES)
    all_entries: list[dict[str, Any]] = []
    for mod_name in modules:
        try:
            mod = importlib.import_module(mod_name)
            meta = getattr(mod, "SOURCE_META", None)
            if meta is None:
                print(f"  [sources] WARNING: no SOURCE_META in {mod_name}")
                continue
            for entry in meta:
                entry.setdefault("_module", mod_name.split(".")[-1])
            all_entries.extend(meta)
        except Exception as exc:
            print(f"  [sources] ERROR importing {mod_name}: {exc}")
    return all_entries


def build_source_key_metadata(
    fetcher_registry: dict[str, Any] | None = None,
    meta_entries: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, str]]:
    """Flatten metadata into a source_key-indexed map."""
    registry = fetcher_registry if fetcher_registry is not None else FETCHER_REGISTRY
    entries = meta_entries if meta_entries is not None else collect_all_meta()

    metadata: dict[str, dict[str, str]] = {}

    for entry in entries:
        source_keys = entry.get("source_keys", [])
        if isinstance(source_keys, str):
            source_keys = [source_keys]
        for source_key in source_keys:
            metadata.setdefault(str(source_key), {})
            if entry.get("url"):
                metadata[str(source_key)]["source_url"] = str(entry["url"])
            if entry.get("source_name"):
                metadata[str(source_key)]["source_name"] = str(entry["source_name"])
            if entry.get("country"):
                metadata[str(source_key)]["country"] = str(entry["country"])

    for source_key, cfg in registry.items():
        row = metadata.setdefault(source_key, {})
        row["source_url"] = str(getattr(cfg, "homepage", "") or "")
        row["cadence"] = str(getattr(cfg, "cadence", "") or "")
        row["source_name"] = str(getattr(cfg, "source_name", "") or "")
        row["country"] = str(getattr(cfg, "country", "") or "")

    for source_key, row in metadata.items():
        if source_key.startswith("gpp_"):
            row.setdefault("source_url", _GPP_SOURCE_URL)
            row.setdefault("cadence", _infer_cadence_from_source_key(source_key))

    return metadata


def classify_source_objective(source_key: str) -> str:
    """Return the workbook objective label for a source key."""
    if source_key.startswith("gpp_"):
        return "ancillary data"
    objective = _OBJECTIVE_OVERRIDES.get(source_key, "country fuel prices")
    if objective not in _OBJECTIVE_VALUES:
        raise ValueError(f"Unsupported objective for {source_key}: {objective}")
    return objective


def build_source_inventory_rows(
    enriched_csv_path: Path | None = None,
    metadata_by_key: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Assemble workbook rows from the enriched retail dataset."""
    csv_path = enriched_csv_path or DEFAULT_ENRICHED_CSV
    metadata = (
        metadata_by_key if metadata_by_key is not None else build_source_key_metadata()
    )

    stats: dict[str, dict[str, Any]] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            source_key = str(record.get("source_key") or "").strip()
            if not source_key:
                continue
            row = stats.setdefault(
                source_key,
                {
                    "n_observations": 0,
                    "products": set(),
                    "start_date": None,
                    "end_date": None,
                },
            )
            row["n_observations"] += 1

            fuel_product = str(record.get("fuel_product") or "").strip()
            if fuel_product:
                row["products"].add(fuel_product)

            observation_date = str(record.get("observation_date") or "").strip()
            if observation_date:
                if row["start_date"] is None or observation_date < row["start_date"]:
                    row["start_date"] = observation_date
                if row["end_date"] is None or observation_date > row["end_date"]:
                    row["end_date"] = observation_date

    rows: list[dict[str, Any]] = []
    for source_key in sorted(stats):
        source_stats = stats[source_key]
        meta = metadata.get(source_key, {})
        rows.append(
            {
                "source_key": source_key,
                "source_url": str(meta.get("source_url", "") or ""),
                "n_observations": int(source_stats["n_observations"]),
                "n_products": len(source_stats["products"]),
                "start_date": source_stats["start_date"] or "",
                "end_date": source_stats["end_date"] or "",
                "cadence": str(meta.get("cadence", "") or ""),
                "objective": classify_source_objective(source_key),
            }
        )
    return rows


def _infer_cadence_from_source_key(source_key: str) -> str:
    suffixes = ("daily", "weekly", "monthly", "quarterly", "manual", "irregular")
    for suffix in suffixes:
        if source_key.endswith(f"_{suffix}"):
            return suffix
    return ""


__all__ = [
    "DEFAULT_ENRICHED_CSV",
    "SOURCE_INVENTORY_COLUMNS",
    "build_source_inventory_rows",
    "build_source_key_metadata",
    "classify_source_objective",
    "collect_all_meta",
]
