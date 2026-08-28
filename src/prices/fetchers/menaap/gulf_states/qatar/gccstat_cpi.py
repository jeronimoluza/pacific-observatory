"""Canonical wrapper for GCC-Stat Consumer Prices in Qatar."""

from prices.fetchers._shared.menaap.gccstat_cpi import fetch_qa_gccstat_cpi

fetch_qa_gccstat_cpi.__module__ = __name__
__all__ = ["fetch_qa_gccstat_cpi"]
