"""Canonical wrapper for the EU Weekly Oil Bulletin in Romania."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_ro

fetch_eu_wob_ro.__module__ = __name__

__all__ = ["fetch_eu_wob_ro"]
