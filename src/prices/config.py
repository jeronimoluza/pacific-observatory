"""Price source configuration: Pydantic model + manifest loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from core.config import parse_config_path

_PRICES_CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


class PriceSourceConfig(BaseModel):
    """One supermarket / retailer source, loaded from a YAML manifest.

    Region, subregion, country, and source are resolved from the YAML file's
    path and never appear in the YAML body itself.
    """

    model_config = ConfigDict(extra="ignore")

    spider: str
    language: str | None = None
    active: bool = True
    max_items: int | None = None
    start_urls: list[str] | None = None
    spider_kwargs: dict[str, Any] = {}
    scrapy_settings: dict[str, Any] = {}
    notes: str = ""

    region: str = ""
    subregion: str = ""
    country: str = ""
    source: str = ""
    config_path: str = ""

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
