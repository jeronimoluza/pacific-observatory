"""Canonical wrapper for BCEAO end-of-month pump prices in Togo."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_tg

fetch_bceao_tg.__module__ = __name__

__all__ = ["fetch_bceao_tg"]
