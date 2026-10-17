"""Canonical wrapper for the EU Weekly Oil Bulletin in Luxembourg."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_lu

fetch_eu_wob_lu.__module__ = __name__

__all__ = ["fetch_eu_wob_lu"]
