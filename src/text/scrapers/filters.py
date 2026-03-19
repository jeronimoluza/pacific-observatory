"""Declarative URL filtering for scraper configs.

This module provides a small, config-driven filter DSL that can be applied to
thumbnail discovery and pending article scraping.

The DSL lives at `listing.filters` in a newspaper config.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional
from urllib.parse import urlparse


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _normalize_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()
    if domain.startswith("http://") or domain.startswith("https://"):
        parsed = urlparse(domain)
        domain = parsed.netloc or domain
    # Strip port if present.
    if ":" in domain:
        domain = domain.split(":", 1)[0]
    return domain


@dataclass(frozen=True)
class ListingFilters:
    """Compiled filter rules for a scraper run."""

    allow_domains: Optional[frozenset[str]]
    deny_domains: frozenset[str]
    deny_path_prefixes: tuple[str, ...]
    deny_path_regex: tuple[re.Pattern[str], ...]
    deny_url_regex: tuple[re.Pattern[str], ...]

    @classmethod
    def from_config(cls, config: Optional[dict[str, Any]]) -> "ListingFilters":
        config = config or {}

        allow_domains_raw = [
            _normalize_domain(d) for d in _to_str_list(config.get("allow_domains"))
        ]
        allow_domains = frozenset([d for d in allow_domains_raw if d]) or None

        deny_domains = frozenset(
            d
            for d in (
                _normalize_domain(x) for x in _to_str_list(config.get("deny_domains"))
            )
            if d
        )

        deny_path_prefixes = tuple(
            p.strip()
            for p in _to_str_list(config.get("deny_path_prefixes"))
            if str(p).strip()
        )

        deny_path_regex = tuple(
            re.compile(pattern)
            for pattern in _to_str_list(config.get("deny_path_regex"))
            if str(pattern).strip()
        )

        deny_url_regex = tuple(
            re.compile(pattern)
            for pattern in _to_str_list(config.get("deny_url_regex"))
            if str(pattern).strip()
        )

        return cls(
            allow_domains=allow_domains,
            deny_domains=deny_domains,
            deny_path_prefixes=deny_path_prefixes,
            deny_path_regex=deny_path_regex,
            deny_url_regex=deny_url_regex,
        )

    @property
    def enabled(self) -> bool:
        return bool(
            self.allow_domains
            or self.deny_domains
            or self.deny_path_prefixes
            or self.deny_path_regex
            or self.deny_url_regex
        )

    def is_allowed(self, url: str) -> bool:
        """Return True if the URL passes allow/deny rules.

        Semantics:
        - Allow rules (if present) must match first.
        - Deny rules always win.
        """
        if not self.enabled:
            return True

        url_str = str(url)
        parsed = urlparse(url_str)
        domain = _normalize_domain(parsed.netloc)
        path = parsed.path or ""

        # Allow rules
        if self.allow_domains is not None and domain not in self.allow_domains:
            return False

        # Deny rules
        if domain in self.deny_domains:
            return False

        for prefix in self.deny_path_prefixes:
            if path.startswith(prefix):
                return False

        for rx in self.deny_path_regex:
            if rx.search(path):
                return False

        for rx in self.deny_url_regex:
            if rx.search(url_str):
                return False

        return True


def compile_listing_filters(listing_config: Optional[dict[str, Any]]) -> ListingFilters:
    """Convenience wrapper to compile filters from a `listing` config block."""

    filters_config = (listing_config or {}).get("filters") or {}
    if not isinstance(filters_config, dict):
        filters_config = {}
    return ListingFilters.from_config(filters_config)
