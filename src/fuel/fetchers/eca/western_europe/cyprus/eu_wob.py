"""Canonical wrapper for the EU Weekly Oil Bulletin in Cyprus."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_cy

fetch_eu_wob_cy.__module__ = __name__

__all__ = ["fetch_eu_wob_cy"]
