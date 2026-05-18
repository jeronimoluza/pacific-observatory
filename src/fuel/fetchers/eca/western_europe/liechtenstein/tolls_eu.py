"""Canonical wrapper for tolls.eu in Liechtenstein."""

from fuel.fetchers._shared.eca.tolls_eu import fetch_tolls_li

fetch_tolls_li.__module__ = __name__

__all__ = ["fetch_tolls_li"]
