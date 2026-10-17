"""Canonical wrapper for the EU Weekly Oil Bulletin in Belgium."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_be

fetch_eu_wob_be.__module__ = __name__

__all__ = ["fetch_eu_wob_be"]
