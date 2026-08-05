from typing import Literal
from pydantic import BaseModel, Field

# Value definitions and discriminating tests: src/prices/docs/GLOSSARY.md
# (authoritative). The grouping comments below are a reading aid only.
Channel = Literal[
    # Food-dominant retail
    "supermarket",
    "hypermarket",
    "convenience",
    "fresh-market",
    "specialty-food",
    # Cross-division retail
    "marketplace",
    "dept-store",
    # Specialty non-food
    "pharmacy",
    "cosmetics",
    "electronics",
    "home-improvement",
    "fashion",
    "pet",
    # Non-retail outlets
    "wholesale",
    "fuel-station",
    "real-estate",
    # Pressure valve — accumulation is the signal to add a value
    "other",
]


class Dimension(BaseModel):
    value: float
    unit: Literal["mm", "cm", "m", "in", "ft"]
    axis: Literal["length", "width", "height", "diameter", "depth", "unspecified"]


class Flags(BaseModel):
    is_promotion: bool
    is_bundle: bool
    is_multipack: bool
    promo_reason: str | None = None


class ProductEnrichment(BaseModel):
    pricing_basis: Literal["mass", "volume", "length", "count", "item"]
    amount_value: float | None
    standard_unit: Literal["kg", "lt", "mt", "unit", "item"]
    count: int | None
    multiplier: int | None
    dimensions: list[Dimension] = Field(default_factory=list)
    coicop_code: str
    flags: Flags
    confidence: float = Field(ge=0.0, le=1.0)
    state: Literal["narrow_source", "classified", "rejected", "flagged_basis"]


class EnrichmentBatch(BaseModel):
    products: list[ProductEnrichment]
