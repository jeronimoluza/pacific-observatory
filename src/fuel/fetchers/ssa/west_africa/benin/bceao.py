"""Canonical wrapper for BCEAO end-of-month pump prices in Benin."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_bj

fetch_bceao_bj.__module__ = __name__

__all__ = ["fetch_bceao_bj"]
