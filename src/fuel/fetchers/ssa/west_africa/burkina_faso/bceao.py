"""Canonical wrapper for BCEAO end-of-month pump prices in Burkina Faso."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_bf

fetch_bceao_bf.__module__ = __name__

__all__ = ["fetch_bceao_bf"]
