"""Canonical wrapper for the EU Weekly Oil Bulletin in Slovak Republic."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_sk

fetch_eu_wob_sk.__module__ = __name__

__all__ = ["fetch_eu_wob_sk"]
