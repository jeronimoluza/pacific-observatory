"""Canonical wrapper for BCEAO end-of-month pump prices in Senegal."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_sn

fetch_bceao_sn.__module__ = __name__

__all__ = ["fetch_bceao_sn"]
