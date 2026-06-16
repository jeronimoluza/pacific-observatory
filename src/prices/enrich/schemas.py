from typing import Literal
from pydantic import BaseModel, Field

Channel = Literal[
    "supermarket",
    "pharmacy",
    "fuel-station",
    "dept-store",
    "electronics",
    "home-improvement",
    "cosmetics",
    "pet",
    "fashion",
    "aggregator",
    "hypermarket",
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
    sub_label_id: str  # non-null; "_other" if no leaf entry fits
    flags: Flags
    confidence: float = Field(ge=0.0, le=1.0)
    state: Literal["resolved", "ambiguous", "unusable"]


class EnrichmentBatch(BaseModel):
    products: list[ProductEnrichment]


class SubcategoryEntry(BaseModel):
    id: str  # kebab-case
    label: str
    synonyms: list[str] = Field(default_factory=list)


class LeafSubcategories(BaseModel):
    entries: list[SubcategoryEntry]
