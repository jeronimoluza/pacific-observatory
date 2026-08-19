"""Canonical wrapper for GCC-Stat Consumer Prices in Kuwait."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_kw_gccstat_cpi

fetch_kw_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_kw_gccstat_cpi"]
