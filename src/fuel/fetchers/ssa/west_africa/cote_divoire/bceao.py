"""Canonical wrapper for BCEAO end-of-month pump prices in Cote d'Ivoire."""

from fuel.fetchers._shared.ssa.bceao import fetch_bceao_ci

fetch_bceao_ci.__module__ = __name__

__all__ = ["fetch_bceao_ci"]
