"""Canonical wrapper for BCEAO end-of-month pump prices in Mali."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_ml

fetch_bceao_ml.__module__ = __name__

__all__ = ["fetch_bceao_ml"]
