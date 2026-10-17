"""Canonical wrapper for BCEAO end-of-month pump prices in Niger."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_ne

fetch_bceao_ne.__module__ = __name__

__all__ = ["fetch_bceao_ne"]
