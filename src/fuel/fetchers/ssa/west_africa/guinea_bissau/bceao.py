"""Canonical wrapper for BCEAO end-of-month pump prices in Guinea-Bissau."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_gw

fetch_bceao_gw.__module__ = __name__

__all__ = ["fetch_bceao_gw"]
