"""Typed pattern records for the tier-a regex tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnitEmit:
    """Per-pattern unit-emit metadata.

    basis: pricing_basis enum  ("mass" | "volume" | "length" | "count" | "item")
    su:    standard_unit enum  ("kg" | "lt" | "mt" | "unit" | "item")
    mul:   factor that converts the matched value into su.
    """

    basis: str
    su: str
    mul: float


@dataclass(frozen=True)
class PackPattern:
    id: str
    regex: re.Pattern[str]
    groups: tuple[str, ...]
    pricing_basis_emit: str | None = None
    suppress_window: int | None = None
    lang: str = "any"
    role: str = "canonicalization"  # "canonicalization" | "extract"
    fixed_count: int | None = None
    unit_emit: UnitEmit | None = None


@dataclass(frozen=True)
class CountryPatch:
    additions: tuple[PackPattern, ...] = field(default_factory=tuple)
    removals: tuple[str, ...] = field(default_factory=tuple)
    replacements: tuple[PackPattern, ...] = field(default_factory=tuple)
