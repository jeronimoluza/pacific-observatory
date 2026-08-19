"""Canonical wrapper for GCC-Stat Consumer Prices in Saudi Arabia."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_sa_gccstat_cpi

fetch_sa_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_sa_gccstat_cpi"]
