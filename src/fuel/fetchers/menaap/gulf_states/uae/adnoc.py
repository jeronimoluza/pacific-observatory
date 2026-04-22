"""Canonical wrapper for ADNOC in the UAE."""

from fuel.fetchers.menaap.adnoc import fetch_adnoc

fetch_adnoc.__module__ = __name__

__all__ = ["fetch_adnoc"]
