"""Canonical wrapper for the EU Weekly Oil Bulletin in Malta."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_mt

fetch_eu_wob_mt.__module__ = __name__

__all__ = ["fetch_eu_wob_mt"]
