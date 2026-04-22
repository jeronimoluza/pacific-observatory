"""Canonical wrapper for PSO in Pakistan."""

from fuel.fetchers.menaap.pso import fetch_pk_pso

fetch_pk_pso.__module__ = __name__

__all__ = ["fetch_pk_pso"]
