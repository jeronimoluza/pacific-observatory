"""Canonical wrapper for GCC-Stat Consumer Prices in Bahrain."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_bh_gccstat_cpi

fetch_bh_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_bh_gccstat_cpi"]
