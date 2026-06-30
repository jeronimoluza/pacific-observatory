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
    # Bucket-routing for the dict_view composer. Explicit on the record so adding
    # a pattern is a one-file edit instead of a two-file trap (module + a separate
    # ID-order tuple). distinct from `role` (which only splits canonicalization vs
    # extract). A pattern with kind="unrouted" is declared but deliberately not fed
    # to any consumed bucket (e.g. cjk_numeral_version, dropped 2026-06-16).
    kind: str = "canon"  # canon | extra_unit | extra_count | multi_pack | pricing_basis_marker | unrouted
    # Morphology bucket — the human/monitoring axis (per_unit_marker |
    # single_measure | multipack | count_pack | _unrouted). Distinct from `kind`
    # (which drives composition): several count_pack sub-modules all tag
    # bucket="count_pack" while their files are split purely as the ordering lever.
    bucket: str | None = None
    # Script family — set ONLY for patterns that lived under script/<family>/
    # (cjk | latin). shared/* and lang/<lang>/* patterns carry script=None even
    # when they contain CJK/Latin characters. Drives load_for membership.
    script: str | None = None


@dataclass(frozen=True)
class CountryPatch:
    additions: tuple[PackPattern, ...] = field(default_factory=tuple)
    removals: tuple[str, ...] = field(default_factory=tuple)
    replacements: tuple[PackPattern, ...] = field(default_factory=tuple)
