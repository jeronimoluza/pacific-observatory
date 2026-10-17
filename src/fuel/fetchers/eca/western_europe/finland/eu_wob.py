"""Canonical wrapper for the EU Weekly Oil Bulletin in Finland."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_fi

fetch_eu_wob_fi.__module__ = __name__

__all__ = ["fetch_eu_wob_fi"]
