"""Canonical wrapper for tolls.eu in Monaco."""

from fuel.fetchers._shared.eca.tolls_eu import fetch_tolls_mc

fetch_tolls_mc.__module__ = __name__

__all__ = ["fetch_tolls_mc"]
