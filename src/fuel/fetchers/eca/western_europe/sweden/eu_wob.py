"""Canonical wrapper for the EU Weekly Oil Bulletin in Sweden."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_se

fetch_eu_wob_se.__module__ = __name__

__all__ = ["fetch_eu_wob_se"]
