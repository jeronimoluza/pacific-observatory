"""Price source configuration: Pydantic model + manifest loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from core.config import parse_config_path
from prices.enrich.schemas import Channel

_PRICES_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


class PriceSourceConfig(BaseModel):
    """One price-data source, loaded from a YAML manifest.

    Supports two scaffolding shapes:
    - ``scaffolding: spider`` → Scrapy spider keyed by ``spider:`` name
    - ``scaffolding: fetcher`` → plain-Python ``module:`` + ``function:`` pair

    Region, subregion, country, and source are resolved from the YAML file's
    path and never appear in the YAML body itself.
    """

    model_config = ConfigDict(extra="forbid")

    scaffolding: str | None = None
    spider: str | None = None
    module: str | None = None
    function: str | None = None
    source_key: str | None = None
    fallback_date: date | None = None
    analytical_role: str | None = None

    language: str | None = None

    # Declared on manifests and read by tooling outside the model. Kept as
    # model fields so `extra="forbid"` cannot silently drop them.
    url: str | None = None
    extraction_pattern: str | None = None

    # Web-archive scope, shared by the Wayback backfill and the Common Crawl
    # fetcher. `archive_prefix` is the narrowest host+path prefix that still
    # covers every product detail page; `archive_path_re` filters listing,
    # category, and static pages that live under the same prefix.
    archive_prefix: str | None = None
    archive_path_re: str | None = None
    coicop_classification: str | None = None
    currency: str | None = None
    inactive_reason: str | None = None

    # Declared in prices, enforced only in the `fuel` pipeline
    # (cpi/fuel_prices/collect/pipeline.py). Prices has no cadence-skip logic;
    # the field documents intended refresh rate and nothing more.
    cadence: str | None = None

    # `channel` is required: every YAML must set it (use `null` for non-retail
    # sources where analytical_role is cpi_benchmark / official_avg / tariff /
    # aggregate_proxy). Backfill applied 2026-06-11 covers all 302 manifests.
    channel: Channel | None
    coicop_codes: list[str] | None = None
    active: bool = True
    max_items: int | None = None
    timeout: int | None = None
    # Sources sharing one CDN edge (e.g. the AS Watson storefronts) are capped
    # as a family so they cannot exhaust each other's connection budget.
    throttle_group: str | None = None
    start_urls: list[str] | None = None
    spider_kwargs: dict[str, Any] = {}
    scrapy_settings: dict[str, Any] = {}
    notes: str = ""

    region: str = ""
    subregion: str = ""
    country: str = ""
    source: str = ""
    config_path: str = ""

    @model_validator(mode="after")
    def _resolve_scaffolding(self) -> "PriceSourceConfig":
        if self.scaffolding is None:
            self.scaffolding = "fetcher" if self.module else "spider"
        if self.scaffolding == "spider" and not self.spider:
            raise ValueError(f"{self.source}: scaffolding=spider requires `spider:`")
        if self.scaffolding == "fetcher" and not (self.module and self.function):
            raise ValueError(
                f"{self.source}: scaffolding=fetcher requires `module:` and `function:`"
            )
        return self

    @classmethod
    def load(
        cls, path: Path, base_dir: Path = _PRICES_CONFIGS_DIR
    ) -> "PriceSourceConfig":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"Manifest {path} is not a YAML mapping")

        region, subregion, country = parse_config_path(path, base_dir)
        raw["region"] = region
        raw["subregion"] = subregion
        raw["country"] = country
        raw["source"] = path.stem
        raw["config_path"] = str(path)
        return cls.model_validate(raw)


def discover_prices_configs(
    region: str | None = None,
    subregion: str | None = None,
    country: str | None = None,
    base_dir: Path = _PRICES_CONFIGS_DIR,
) -> list[Path]:
    """List manifest paths under base_dir matching the optional filters."""
    from core.config import discover_pipeline_configs

    return discover_pipeline_configs(
        base_dir, region=region, subregion=subregion, country=country
    )
