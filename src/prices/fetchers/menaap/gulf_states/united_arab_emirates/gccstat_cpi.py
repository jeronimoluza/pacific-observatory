"""Canonical wrapper for GCC-Stat Consumer Prices in the United Arab Emirates."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_ae_gccstat_cpi

fetch_ae_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_ae_gccstat_cpi"]
