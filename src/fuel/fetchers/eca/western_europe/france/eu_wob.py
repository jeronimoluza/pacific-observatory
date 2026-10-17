"""Canonical wrapper for the EU Weekly Oil Bulletin in France."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_fr

fetch_eu_wob_fr.__module__ = __name__

__all__ = ["fetch_eu_wob_fr"]
