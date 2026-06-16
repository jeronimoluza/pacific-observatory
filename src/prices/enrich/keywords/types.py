"""Typed records for the COICOP keyword tree."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExcludeRef:
    code: str
    label: str
    lang: str = "en"


@dataclass(frozen=True)
class SubLabel:
    id: str
    label: str
    keywords_by_lang: dict[str, tuple[str, ...]] = field(default_factory=dict)
    allowed_bases: frozenset[str] | None = None
    role: str = "synonym"
    numeric_id: str | None = None


@dataclass(frozen=True)
class Leaf:
    code: str
    label: str
    keywords_by_lang: dict[str, tuple[str, ...]] = field(default_factory=dict)
    excludes: tuple[ExcludeRef, ...] = field(default_factory=tuple)
    sub_labels: tuple[SubLabel, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Subgroup:
    code: str
    label: str
    leaves: tuple[Leaf, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Group:
    code: str
    label: str
    subgroups: tuple[Subgroup, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class COICOPClass:
    code: str
    label: str
    groups: tuple[Group, ...] = field(default_factory=tuple)
