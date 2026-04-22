"""Canonical wrapper for Egypt Petroleum official prices."""

from fuel.fetchers.menaap.egypt_petroleum import fetch_eg_petroleum

fetch_eg_petroleum.__module__ = __name__

__all__ = ["fetch_eg_petroleum"]
