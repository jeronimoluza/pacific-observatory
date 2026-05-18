"""Canonical wrapper for tolls.eu in San Marino."""

from fuel.fetchers._shared.eca.tolls_eu import fetch_tolls_sm

fetch_tolls_sm.__module__ = __name__

__all__ = ["fetch_tolls_sm"]
