"""Canonical wrapper for the EU Weekly Oil Bulletin in Denmark."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_dk

fetch_eu_wob_dk.__module__ = __name__

__all__ = ["fetch_eu_wob_dk"]
