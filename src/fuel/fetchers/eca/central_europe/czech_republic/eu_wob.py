"""Canonical wrapper for the EU Weekly Oil Bulletin in Czech Republic."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_cz

fetch_eu_wob_cz.__module__ = __name__

__all__ = ["fetch_eu_wob_cz"]
