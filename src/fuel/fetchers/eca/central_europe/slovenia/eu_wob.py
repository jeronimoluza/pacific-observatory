"""Canonical wrapper for the EU Weekly Oil Bulletin in Slovenia."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_si

fetch_eu_wob_si.__module__ = __name__

__all__ = ["fetch_eu_wob_si"]
