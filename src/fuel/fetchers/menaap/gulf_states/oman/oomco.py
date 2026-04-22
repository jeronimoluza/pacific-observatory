"""Canonical wrapper for OOMCO in Oman."""

from fuel.fetchers.menaap.oomco import fetch_oomco

fetch_oomco.__module__ = __name__

__all__ = ["fetch_oomco"]
