"""Canonical wrapper for GCC-Stat Consumer Prices in Oman."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_om_gccstat_cpi

fetch_om_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_om_gccstat_cpi"]
